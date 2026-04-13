"""
vibehack/core/repl/logic.py — ReAct loop orchestration for VibeHack REPL.
Reason → Act → Observe.
"""
import asyncio
from rich.console import Console
from rich.prompt import Confirm, Prompt

from vibehack.agent.prompts import get_system_prompt, load_template
from vibehack.agent.prompts.tactical import (
    get_loop_recovery, get_truncation_note, get_block_note, 
    get_finding_note, get_memory_feedback, detect_logic_loop
)
from vibehack.llm.provider import AgentResponse
from vibehack.guardrails.regex_engine import check_command, check_target
from vibehack.toolkit.discovery import clear_discovery_cache
from vibehack.core.shell import execute_shell
from vibehack.config import cfg
from vibehack.agent.knowledge import extract_knowledge
from vibehack.ui.tui import (
    display_thought, display_command, display_education, 
    display_finding, display_output, display_knowledge_update, 
    ask_approval, display_mission
)

console = Console()

async def process_llm_turn(repl, user_message: str, force_ask: bool = False):
    """Execution logic for one ReAct turn."""
    is_ask_mode = force_ask or repl.op_mode == "ask"

    # Intercept shell commands
    if user_message.strip().startswith("vibehack "):
        _handle_shell_intercept(repl, user_message)
        return

    # Auto-detect target
    if not repl.target:
        detected = repl._extract_target_from_text(user_message)
        if detected and not check_target(detected):
            repl.target = detected
            console.print(f"[dim]✓ Target auto-detected: {detected}[/dim]")
            repl._rebuild_system_prompt()

    if not repl._system_built:
        repl._rebuild_system_prompt()

    repl.history.append({"role": "user", "content": user_message})

    while True:
        try:
            if getattr(repl, "interrupted", False):
                repl.interrupted = False
                console.print("\n[bold red]🛑 Process stopped by user (ESC).[/bold red]\n")
                return

            repl._trim_history() # Safeguard context window
            if is_ask_mode:
                await _handle_ask_mode(repl)
                return

            # Loop Detection (Tactical)
            duplicate_cmd = detect_logic_loop(repl.history)
            if duplicate_cmd:
                repl.history.append({"role": "user", "content": get_loop_recovery(f"Command '{duplicate_cmd}' repeated 3x")})

            with console.status("[bold green]🤖 AI is thinking...[/bold green]", spinner="dots"):
                response: AgentResponse = await repl.handler.complete(repl.history)
        except Exception as e:
            err_msg = str(e)
            if "QUOTA_EXHAUSTED" in err_msg or "429" in err_msg:
                console.print(f"\n[bold red]🛑 API Quota Exhausted:[/bold red] {err_msg}")
                console.print(f"[yellow]Session {repl.session_id} has been saved.[/yellow]")
                console.print(f"[cyan]You can resume this audit later with:[/cyan] [bold]vibehack resume {repl.session_id}[/bold]")
            else:
                console.print(f"[red]LLM error:[/red] {e}")
            
            repl._persist()
            if repl.history and repl.history[-1]["role"] == "user":
                repl.history.pop()  # Rollback
            return

        repl.history.append({"role": "assistant", "content": response.model_dump_json()})

        # Update tech hint from thought
        from vibehack.memory.ingestion import detect_technology
        tech = detect_technology(response.thought)
        if tech != "unknown":
            if tech not in repl.knowledge.technologies:
                repl.knowledge.technologies.add(tech)
                repl._rebuild_system_prompt()

        display_thought(response.thought)

        if response.education and repl.persona == "dev-safe":
            display_education(response.education)

        if response.mission_goals:
            if set(repl.knowledge.mission_goals) != set(response.mission_goals):
                repl.knowledge.mission_goals = response.mission_goals
                display_mission(repl.knowledge.mission_goals)

        if response.finding:
            display_finding(response.finding.severity, response.finding.title, response.finding.description)
            repl.key_findings.append(response.finding)
            repl.knowledge.tested_surfaces.add(response.finding.title)
            repl.history.append({"role": "user", "content": get_finding_note(response.finding.title)})
            repl._persist()
            continue  # Finding recorded — let AI propose next step automatically

        # Process Command
        if response.raw_command:
            if getattr(repl, "interrupted", False):
                repl.interrupted = False
                console.print("\n[bold red]🛑 Command execution cancelled by user (ESC).[/bold red]\n")
                return
            await _execute_proposed_command(repl, response)
            repl._trim_history()
            repl._persist()
            continue  # Feedback received — let AI analyze result automatically

        # If no command or finding was triggered, break and let user steer
        break

async def _handle_ask_mode(repl):
    from vibehack.agent.prompts import load_template
    ask_sys = {"role": "system", "content": load_template("ask_mode")}
    from vibehack.ui.tui import display_ask_response
    with console.status("[bold magenta]🤖 AI is formulating answer...[/bold magenta]", spinner="dots"):
        raw_resp = await repl.handler.complete_raw([ask_sys] + repl.history)
    
    display_ask_response(raw_resp)
    repl.history.append({"role": "assistant", "content": raw_resp})
    repl._trim_history()
    repl._persist()

async def _execute_proposed_command(repl, response: AgentResponse):
    cmd = response.raw_command.strip()
    block = check_command(cmd, repl.unchained)
    if block:
        console.print(f"\n[bold red]🛡 BLOCKED:[/bold red] {block}\n")
        repl.history.append({"role": "user", "content": get_block_note(block)})
        return

    if cmd.startswith("vibehack-memory "):
        _handle_memory_tool(repl, cmd)
        return

    display_command(cmd)

    if response.is_destructive:
        console.print("[bold red]⚠  DESTRUCTIVE — manual approval required[/bold red]")
        approval = await ask_approval()
    elif repl.auto_allow:
        approval, _ = "y", console.print("[dim]⚡ Auto-Allow[/dim]")
    else:
        approval = await ask_approval()

    if approval == "n":
        note = Prompt.ask("[dim]Hint for AI (optional)[/dim]", default="")
        repl.history.append({"role": "user", "content": f"System: USER REJECTED COMMAND. {note}"})
        return

    if approval == "a":
        repl.auto_allow = True
        console.print("[yellow]⚡ Auto-Allow enabled[/yellow]")

    # Execute and Stream
    from rich.live import Live
    from rich.panel import Panel
    output_lines = []
    def live_callback(text, is_stderr):
        output_lines.extend(text.splitlines(keepends=True))
        display_lines = "".join(output_lines[-15:])
        style = "red" if is_stderr else "dim white"
        _live.update(Panel(display_lines, title="📝 Streaming Output", border_style=style))

    with Live(Panel("Initializing...", title="📝 Streaming Output", border_style="dim white"), refresh_per_second=4, transient=True) as _live:
        result = await execute_shell(cmd, timeout=cfg.CMD_TIMEOUT, truncate_limit=cfg.TRUNCATE_LIMIT, env=repl.env, output_callback=live_callback, interrupter=lambda: getattr(repl, "interrupted", False))

    display_output(result.stdout)
    if result.stderr: display_output(result.stderr, is_error=True)

    # Knowledge Extraction
    old_k = (len(repl.knowledge.open_ports), len(repl.knowledge.technologies), len(repl.knowledge.endpoints))
    extract_knowledge(result.stdout, repl.knowledge)
    extract_knowledge(result.stderr or "", repl.knowledge)
    
    if (len(repl.knowledge.open_ports), len(repl.knowledge.technologies), len(repl.knowledge.endpoints)) != old_k:
        display_knowledge_update(list(repl.knowledge.open_ports), list(repl.knowledge.technologies), repl.knowledge.endpoints)
        repl._rebuild_system_prompt()

    feedback = f"COMMAND: {cmd}\nEXIT_CODE: {result.exit_code}\nSTDOUT:\n{result.stdout}"
    if result.stderr: feedback += f"\nSTDERR:\n{result.stderr}"
    if result.truncated:
        feedback += get_truncation_note(cfg.TRUNCATE_LIMIT)
        console.print(f"[dim]ℹ Output truncated to {cfg.TRUNCATE_LIMIT} chars to save tokens.[/dim]")

    repl.history.append({"role": "user", "content": feedback})

def _handle_shell_intercept(repl, user_message: str):
    parts = user_message.strip().split()
    if len(parts) > 2 and parts[1] == "install":
        tool_name = parts[2]
        console.print(f"\n[yellow]ℹ  Use:[/yellow] [cyan]/install {tool_name}[/cyan]\n")
    else:
        console.print(f"\n[yellow]ℹ  Shell commands go outside the REPL.[/yellow]\n")

def _handle_memory_tool(repl, cmd: str):
    """Internal tool for AI to search past experiences."""
    from vibehack.memory.db import get_memory_context
    
    parts = cmd.strip().split()
    keyword = parts[2] if len(parts) > 2 else "web"
    
    console.print(f"[dim]🧠 AI is searching Long-Term Memory for: [cyan]{keyword}[/cyan][/dim]")
    memory_ctx = get_memory_context(keyword)
    
    repl.history.append({"role": "user", "content": get_memory_feedback(keyword, memory_ctx)})
    repl._persist()
