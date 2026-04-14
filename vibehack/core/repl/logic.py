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
    ask_approval, display_mission, log_to_pane, pop_last_line_from_pane
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
            log_to_pane(repl, "logs", f"✓ Target auto-detected: {detected}")
            repl._rebuild_system_prompt()

    if not repl._system_built:
        repl._rebuild_system_prompt()

    repl.history.append({"role": "user", "content": user_message})

    max_turns = cfg.MAX_TURN_MEMORY
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1
        try:
            if getattr(repl, "interrupted", False):
                # Refresh telemetry and status every second
                await asyncio.sleep(0.1)
                log_to_pane(repl, "logs", "🛑 Process stopped by user (ESC).")
                return

            repl._trim_history() # Safeguard context window
            if is_ask_mode:
                await _handle_ask_mode(repl)
                return

            # Loop Detection (Tactical)
            duplicate_cmd = detect_logic_loop(repl.history)
            if duplicate_cmd:
                log_to_pane(repl, "logs", f"LOOP_DETECTOR: detected repetitive pattern for '{duplicate_cmd}', injecting recovery protocol...")
                repl.history.append({"role": "user", "content": get_loop_recovery(f"Command '{duplicate_cmd}' repeated 3x")})

            # Update TUI status (Minimized)
            repl.app.invalidate()
            
            
            response: AgentResponse = await repl.handler.complete(repl.history)
            pop_last_line_from_pane(repl, "history")
        except Exception as e:
            pop_last_line_from_pane(repl, "history")
            err_msg = str(e)
            if "QUOTA_EXHAUSTED" in err_msg or "429" in err_msg:
                log_to_pane(repl, "logs", f"🛑 API Quota Exhausted: {err_msg}")
                log_to_pane(repl, "logs", f"Session {repl.session_id} has been saved.")
                log_to_pane(repl, "logs", f"Resume later: vibehack resume {repl.session_id}")
            else:
                log_to_pane(repl, "logs", f"🚨 LLM error: {e}")
            
            repl._persist()
            if repl.history and repl.history[-1]["role"] == "user":
                repl.history.pop()  # Rollback
            return

        repl.history.append({"role": "assistant", "content": response.model_dump_json()})

        # 2. Update tech hint from thought
        from vibehack.memory.ingestion import detect_technologies
        techs = detect_technologies(response.thought)
        for tech in techs:
            if tech != "unknown" and tech not in repl.knowledge.technologies:
                repl.knowledge.technologies.add(tech)
                repl._rebuild_system_prompt()

        display_thought(response.thought, repl=repl)

        if response.education and repl.persona == "dev-safe":
            display_education(response.education, repl=repl)

        if response.mission_goals:
            if set(repl.knowledge.mission_goals) != set(response.mission_goals):
                repl.knowledge.mission_goals = response.mission_goals
                display_mission(repl.knowledge.mission_goals, repl=repl)

        # 1. Process Finding if present
        if response.finding:
            display_finding(response.finding.severity, response.finding.title, response.finding.description, repl=repl)
            repl.key_findings.append(response.finding)
            repl.knowledge.tested_surfaces.add(response.finding.title)
            repl.history.append({"role": "user", "content": get_finding_note(response.finding.title)})
            repl._persist()
        
        # 2. Process Command if present
        if response.raw_command:
            await _execute_proposed_command(repl, response)
            repl._trim_history()
            repl._persist()
            continue  # Feedback received — let AI analyze result automatically

        # 3. If no command was executed, check if we just recorded a finding
        if response.finding:
            continue # Let AI propose the next move after the finding

        # If nothing left to do, break and let user steer
        log_to_pane(repl, "logs", "✓ Turn complete. Awaiting further mission instructions.")
        break
    
    if turn_count >= max_turns:
        log_to_pane(repl, "logs", "⚠ Mission limit reached (10 turns). Stopping to prevent loop.")

async def _handle_ask_mode(repl):
    ask_instr = load_template("ask_mode")
    
    # Preserve original system prompt (which contains target/knowledge)
    # but append ask mode instructions to it.
    original_sys = repl.history[0]["content"] if repl.history and repl.history[0]["role"] == "system" else ""
    ask_sys = {"role": "system", "content": f"{original_sys}\n\n[ ASK MODE INSTRUCTIONS ]\n{ask_instr}"}
    
    messages = [ask_sys] + [m for m in repl.history if m["role"] != "system"]
    
    # Update status
    # Status update removed
    repl.app.invalidate()
    
    
    from vibehack.ui.tui import display_ask_response
    raw_resp = await repl.handler.complete_raw(messages)
    pop_last_line_from_pane(repl, "history")
    
    display_ask_response(raw_resp, repl=repl)
    repl.history.append({"role": "assistant", "content": raw_resp})
    repl._trim_history()
    repl._persist()
    # Status update removed
    repl.app.invalidate()

async def _execute_proposed_command(repl, response: AgentResponse):
    cmd = response.raw_command.strip()

    # 0. Shadow Critic Sidecar (v2.7) — Prevents logical loops and bad decisions
    critique = await repl.handler.critique(repl.history, cmd)
    if critique:
        log_to_pane(repl, "logs", f"🕵️ SHADOW CRITIC: {critique}")
        repl.history.append({"role": "user", "content": f"System (Shadow Critic): {critique}"})
        return

    block = check_command(cmd, repl.unchained)
    if block:
        log_to_pane(repl, "logs", f"🛡 BLOCKED: {block}")
        repl.history.append({"role": "user", "content": get_block_note(block)})
        return

    if cmd.startswith("vibehack-memory "):
        _handle_memory_tool(repl, cmd)
        return

    if cmd.startswith("vibehack-note "):
        _handle_note_tool(repl, cmd)
        return

    # System: Slash commands are prioritized as user-defined skills, not hardcoded installers.
    if cmd.startswith("/"):
        from vibehack.core.repl.commands import handle_slash_command
        await handle_slash_command(repl, cmd)
        return

    display_command(cmd, repl=repl)

    if response.is_destructive:
        log_to_pane(repl, "logs", "⚠ DESTRUCTIVE — manual approval required")
        approval = await ask_approval(repl=repl)
    elif repl.auto_allow:
        log_to_pane(repl, "logs", "⚡ Auto-Allowing command execution")
        approval = "y"
    else:
        approval = await ask_approval(repl=repl)

    if approval == "n":
        log_to_pane(repl, "logs", "🛑 User rejected command execution.")
        repl.history.append({"role": "user", "content": "System: USER REJECTED COMMAND."})
        return

    if approval == "a":
        repl.auto_allow = True
        log_to_pane(repl, "logs", "⚡ Auto-Allow enabled")

    # Execute and Stream
    def live_callback(text, is_stderr):
        # Stream directly to output pane
        log_to_pane(repl, "output", text)

    log_to_pane(repl, "logs", f"🚀 EXEC: {cmd}")
    result = await execute_shell(cmd, timeout=cfg.CMD_TIMEOUT, truncate_limit=cfg.TRUNCATE_LIMIT, env=repl.env, output_callback=live_callback, interrupter=lambda: getattr(repl, "interrupted", False))
    log_to_pane(repl, "logs", f"SH_RET: process exited with code {result.exit_code}")

    display_output(result.stdout, repl=repl)
    if result.stderr: display_output(result.stderr, is_error=True, repl=repl)

    # Knowledge Extraction
    old_k = (len(repl.knowledge.open_ports), len(repl.knowledge.technologies), len(repl.knowledge.endpoints))
    extract_knowledge(result.stdout, repl.knowledge)
    extract_knowledge(result.stderr or "", repl.knowledge)
    
    if (len(repl.knowledge.open_ports), len(repl.knowledge.technologies), len(repl.knowledge.endpoints)) != old_k:
        log_to_pane(repl, "logs", "INTEL: extracted new entities from command output, updating state...")
        display_knowledge_update(list(repl.knowledge.open_ports), list(repl.knowledge.technologies), repl.knowledge.endpoints, repl=repl)
        repl._rebuild_system_prompt()

    feedback = f"COMMAND: {cmd}\nEXIT_CODE: {result.exit_code}\nSTDOUT:\n{result.stdout}"
    if result.stderr: feedback += f"\nSTDERR:\n{result.stderr}"
    if result.truncated:
        feedback += get_truncation_note(cfg.TRUNCATE_LIMIT)
        log_to_pane(repl, "logs", f"ℹ Output truncated to {cfg.TRUNCATE_LIMIT} chars.")

    repl.history.append({"role": "user", "content": feedback})
    # Status update removed
    repl.app.invalidate()

def _handle_shell_intercept(repl, user_message: str):
    log_to_pane(repl, "logs", "ℹ Shell commands go outside the REPL.")

def _handle_memory_tool(repl, cmd: str):
    """Internal tool for AI to search past experiences."""
    from vibehack.memory.db import get_memory_context
    
    parts = cmd.strip().split()
    keyword = parts[2] if len(parts) > 2 else "web"
    
    log_to_pane(repl, "logs", f"🧠 BRAIN: searching long-term memory for '{keyword}'...")
    memory_ctx = get_memory_context(keyword)
    
    if memory_ctx:
        log_to_pane(repl, "logs", f"BRAIN: retrieval successful ({len(memory_ctx)} relevant matches found).")
    else:
        log_to_pane(repl, "logs", "BRAIN: no relevant historical context found for this keyword.")
    
    repl.history.append({"role": "user", "content": get_memory_feedback(keyword, memory_ctx)})
    repl._persist()

def _handle_note_tool(repl, cmd: str):
    """Internal tool for AI to manage its manual 'Buku Saku' notes."""
    parts = cmd.strip().split(maxsplit=2)
    action = parts[1].lower() if len(parts) > 1 else "list"
    content = parts[2] if len(parts) > 2 else ""

    if action == "add" and content:
        repl.knowledge.add_note(content)
        log_to_pane(repl, "logs", f"📝 NOTE SAVED: {content[:50]}...")
        msg = f"SUCCESS: Note added to your scratchpad."
    elif action == "clear":
        repl.knowledge.notes = []
        log_to_pane(repl, "logs", "📝 NOTES CLEARED.")
        msg = "SUCCESS: Scratchpad cleared."
    else:
        notes_str = "\n".join([f"{i}. {n}" for i, n in enumerate(repl.knowledge.notes)])
        msg = f"CURRENT NOTES:\n{notes_str or 'Empty.'}"

    repl.history.append({"role": "user", "content": f"SYSTEM (Notes): {msg}"})
    repl._rebuild_system_prompt()
    repl._persist()
