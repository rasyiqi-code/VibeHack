"""
vibehack/core/repl/commands.py — Logic for slash commands in the REPL.
Separated to avoid bloat in repl.py.
"""
import os
from typing import Optional, Union, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from vibehack.config import cfg
from vibehack.llm.provider import UniversalHandler
from vibehack.agent.knowledge import KnowledgeState
from vibehack.guardrails.regex_engine import check_target
from vibehack.guardrails.waiver import verify_unchained_access
from vibehack.memory.db import get_memory_stats
from vibehack.ui.tui import (
    display_map, display_finding
)

console = Console()

SLASH_COMMANDS = {
    "/help":      "Show this help message",
    "/target":    "Set or show target (/target http://localhost:3000)",
    "/mode":      "Switch operational mode (/mode agent | /mode ask)",
    "/status":    "Show current session & system status",
    "/persona":   "Switch persona (/persona dev-safe | /persona pro)",
    "/ask":       "Ask a theory question without executing anything",
    "/auth":      "Reconfigure AI provider / API keys",
    "/switch":    "Seamlessly swap AI model without losing context",
    "/unchained": "Toggle unchained mode (disables regex guardrails)",
    "/findings":  "List confirmed findings",
    "/knowledge": "Show current knowledge state (ports, tech, endpoints)",
    "/map":       "Visualise attack surface as a tree",
    "/skills":    "List, install, edit or learn skills (/skills list | install <url> | edit <name> | learn <url>)",
    "/report":    "Generate Markdown audit report",
    "/clear":     "Clear conversation history (keeps knowledge & findings)",
    "/memory":    "Browse or search Long-Term Memory (/memory list | /memory search <tech>)",
    "/tokens":    "Manage token economy and context window (/tokens status | limit <n> | turns <n>)",
    "/tools":     "Show tools discovered in your PATH",
    "/check-update": "Check for the latest version on GitHub",
    "/sessions":  "List and resume previous sessions interactively",
    "/history":   "Show a clean summary of the session ReAct chain",
    "/exit":      "Save session and exit",
}

def handle_slash_command(repl, cmd: str) -> Union[bool, Tuple[str, str]]:
    """
    Process slash commands. 
    Returns:
      True  -> continue
      False -> exit
      ("__install__", tool_name) -> trigger tool installation
    """
    parts = cmd.strip().split(None, 1)
    verb = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if verb == "/help":
        lines = [f"  [cyan]{k}[/cyan]  [dim]{v}[/dim]" for k, v in SLASH_COMMANDS.items()]
        console.print(Panel("\n".join(lines), title="Slash Commands", border_style="dim"))

    elif verb == "/target":
        if arg:
            err = check_target(arg)
            if err:
                console.print(f"[red]Blocked:[/red] {err}")
            else:
                repl.target = arg
                console.print(f"[green]✓ Target:[/green] {arg}")
                repl._rebuild_system_prompt()
        else:
            console.print(f"Target: [cyan]{repl.target or 'not set'}[/cyan]")

    elif verb == "/mode":
        if arg in ("agent", "ask"):
            repl.op_mode = arg
            console.print(f"[green]✓ Operation mode:[/green] {arg}")
        else:
            console.print(f"Mode: {repl.op_mode} | Use: /mode agent  or  /mode ask")

    elif verb == "/persona":
        if arg in ("dev-safe", "pro"):
            repl.persona = arg
            console.print(f"[green]✓ Persona:[/green] {arg}")
            repl._rebuild_system_prompt()
        else:
            console.print(f"Persona: {repl.persona} | Use: /persona dev-safe  or  /persona pro")

    elif verb == "/auth":
        from vibehack.core.wizard import _setup_wizard
        from vibehack.config import load_config_env
        _setup_wizard()
        load_config_env()
        cfg.load()
        repl.handler = UniversalHandler(api_key=cfg.API_KEY, model=cfg.MODEL)
        console.print("[bold green]✓ Authentication updated & AI engine re-initialized.[/bold green]")

    elif verb == "/switch":
        _handle_switch(repl, arg)

    elif verb == "/status":
        _display_status(repl)

    elif verb == "/sessions":
        return _handle_sessions_interactively(repl)

    elif verb == "/unchained":
        if not repl.unchained:
            if verify_unchained_access(True):
                repl.unchained = True
                console.print("[bold red]🔓 Unchained mode enabled.[/bold red]")
                repl._rebuild_system_prompt()
        else:
            repl.unchained = False
            console.print("[green]🔒 Guardrails restored.[/green]")
            repl._rebuild_system_prompt()


    elif verb == "/knowledge":
        _display_knowledge(repl)

    elif verb == "/map":
        if not repl.target:
            console.print("[red]Set a target first using /target[/red]")
        else:
            display_map(repl.target, repl.knowledge.to_dict())

    elif verb == "/skills":
        _handle_skills_command(repl, arg)

    elif verb == "/findings":
        _display_findings(repl)

    elif verb == "/report":
        from vibehack.reporting.exporter import export_report
        path = export_report(repl.target or "unknown", repl.key_findings, repl.history, cfg.HOME / "reports")
        console.print(f"[bold green]✅ Report:[/bold green] {path}")

    elif verb == "/clear":
        sys_msg = repl.history[0] if repl.history and repl.history[0]["role"] == "system" else None
        repl.history = [sys_msg] if sys_msg else []
        console.print("[dim]History cleared. Knowledge and findings preserved.[/dim]")

    elif verb == "/memory":
        from vibehack.memory.db import search_experience, get_memory_stats
        from rich.table import Table

        if repl.no_memory:
            console.print("[dim]LTM disabled.[/dim]")
            return True

        if not arg:
            s = get_memory_stats()
            console.print(f"🧠 LTM: [bold]{s['total']}[/bold] experiences ([green]{s['successes']} ✅[/green] / [red]{s['failures']} ❌[/red])")
            console.print("[dim]Use /memory list or /memory search <keyword> to browse.[/dim]")
        
        elif arg.startswith("list"):
            # Use '%' to search for everything
            results = search_experience("", limit=15) # empty string for tech matches all 'LIKE %%%'
            if not results:
                console.print("[dim]No experiences in database yet.[/dim]")
            else:
                table = Table(title="🧠 Recent Experiences (LTM)")
                table.add_column("Target", style="cyan")
                table.add_column("Tech", style="yellow")
                table.add_column("Score", justify="center")
                table.add_column("Summary", style="white")
                
                for target, tech, payload, score, summary in results:
                    label = "[green]✅[/green]" if score > 0 else ("[red]❌[/red]" if score < 0 else "[dim]ℹ[/dim]")
                    table.add_row(target[:20], tech, label, summary)
                console.print(table)
                
        elif arg.startswith("search "):
            keyword = arg[7:].strip()
            results = search_experience(keyword, limit=10)
            if not results:
                console.print(f"[dim]No experiences found for '{keyword}'.[/dim]")
            else:
                table = Table(title=f"🔎 Memory search: '{keyword}'")
                table.add_column("Target", style="cyan")
                table.add_column("Tech", style="yellow")
                table.add_column("Score", justify="center")
                table.add_column("Summary", style="white")
                for target, tech, payload, score, summary in results:
                    label = "[green]✅[/green]" if score > 0 else ("[red]❌[/red]" if score < 0 else "[dim]ℹ[/dim]")
                    table.add_row(target[:20], tech, label, summary)
                console.print(table)
        else:
            console.print("[dim]Usage: /memory [list | search <keyword>][/dim]")

    elif verb == "/tokens":
        _handle_tokens_command(repl, arg)

    elif verb == "/tools":
        tools = repl._available_tools
        console.print(f"[green]Discovered ({len(tools)}):[/green] {', '.join(tools) or 'none'}")
        console.print("[dim]Scanned from $PATH + ~/.vibehack/bin/[/dim]")

    elif verb == "/check-update":
        _check_update_logic(repl)

    elif verb in ("/exit", "/quit", "/q"):
        return False

    elif verb == "/history":
        _display_history(repl)

    else:
        console.print(f"[red]Unknown:[/red] {verb}. Type /help")

    return True

def _handle_switch(repl, arg: str):
    if not arg:
        console.print("[dim]Usage: /switch <provider|model>[/dim]\n[dim]Examples: /switch openai, /switch claude, /switch gemini-1.5-pro[/dim]")
        return
    
    arg = arg.lower()
    new_provider, new_model, new_key = None, None, None
    
    if arg in ("openai", "gpt", "gpt4", "gpt-4o"):
        new_provider, new_model, new_key = "openai", "openai/gpt-4o", cfg.OPENAI_KEY
    elif arg in ("google", "gemini", "flash"):
        new_provider, new_model, new_key = "google", "gemini/gemini-1.5-flash-latest", cfg.GOOGLE_KEY
    elif arg in ("anthropic", "claude", "sonnet"):
        new_provider, new_model, new_key = "anthropic", "anthropic/claude-3-5-sonnet-20240620", cfg.ANTHROPIC_KEY
    elif arg in ("openrouter", "or"):
        new_provider, new_model, new_key = "openrouter", "openrouter/anthropic/claude-3.5-sonnet", cfg.OPENROUTER_KEY
    else:
        new_model = arg
        
    if not new_key and new_provider:
         env_map = {"openai": "OPENAI_API_KEY", "google": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
         new_key = os.getenv(env_map[new_provider])

    if new_provider and not new_key:
        console.print(f"[red]Error: No API Key found for {new_provider or new_model}.[/red]\n[dim]Run /auth first.[/dim]")
    else:
        repl.handler.switch_model(model=new_model, api_key=new_key, provider=new_provider)
        console.print(f"[bold green]✓ Seamless Switch:[/bold green] Brain swapped to [cyan]{new_model}[/cyan]")

def _display_status(repl):
    from rich.table import Table
    table = Table(title=f"🛸 VibeHack Session Status ({repl.session_id})", show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    table.add_row("Target", f"[bold white]{repl.target or '(not set)'}[/bold white]")
    table.add_row("AI Provider", f"[green]{repl.handler.provider.upper()}[/green]")
    table.add_row("AI Model", f"[green]{repl.handler.model}[/green]")
    table.add_row("Auth Type", f"[dim]{repl.handler.auth_type}[/dim]")
    table.add_row("Mode", f"[magenta]{repl.op_mode}[/magenta]")
    table.add_row("Persona", f"[yellow]{repl.persona}[/yellow]")
    table.add_row("Guardrails", "[red]UNCHAINED[/red]" if repl.unchained else "[green]Guarded[/green]")
    s = get_memory_stats()
    table.add_row("Knowledge", f"{len(repl.knowledge.open_ports)} ports, {len(repl.knowledge.technologies)} techniques")
    table.add_row("Findings", f"[bold yellow]{len(repl.key_findings)} confirmed findings[/bold yellow]")
    table.add_row("LTM Context", f"{s['total']} shared experiences")
    table.add_row("Tools", f"{len(repl._available_tools)} discovered in PATH")
    console.print(Panel(table, border_style="dim"))

def _display_knowledge(repl):
    k = repl.knowledge
    if k.is_empty():
        console.print("[dim]No knowledge accumulated yet. Start scanning.[/dim]")
        return
    if k.open_ports:
        console.print(f"🔌 [bold]Open ports:[/bold] {', '.join(map(str, sorted(k.open_ports)))}")
    if k.technologies:
        console.print(f"⚙  [bold]Technologies:[/bold] {', '.join(sorted(k.technologies))}")
    if k.endpoints:
        console.print(f"🗺  [bold]Endpoints ({len(k.endpoints)}):[/bold] {', '.join(k.endpoints[:10])}{'...' if len(k.endpoints) > 10 else ''}")
    if k.credentials:
        console.print(f"🔑 [bold]Credentials:[/bold] {len(k.credentials)} found")
    for note in k.notes[-5:]:
        console.print(f"  • {note}")

def _display_findings(repl):
    if not repl.key_findings:
        console.print("[dim]No confirmed findings yet.[/dim]")
    else:
        BADGES = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
        for i, f in enumerate(repl.key_findings, 1):
            console.print(f"  {i}. {BADGES.get(f.severity.lower(), '?')} [{f.severity.upper()}] {f.title}")

def _handle_tokens_command(repl, arg: str):
    """Handle /tokens sub-commands."""
    from rich.table import Table
    
    if not arg or arg == "status":
        table = Table(title="📉 Token Economy Status", show_header=False, box=None)
        # Check current history tokens approx (very rough)
        hist_len = len(repl.history)
        total_chars = sum(len(m["content"]) for m in repl.history)
        
        table.add_row("Conversation Turns", f"[bold]{hist_len}[/bold]")
        table.add_row("Context Window (Sliding)", f"{cfg.MAX_TURN_MEMORY} turns")
        table.add_row("Output Truncation", f"{cfg.TRUNCATE_LIMIT} chars")
        table.add_row("Est. Active Context", f"~{total_chars // 4} tokens")
        console.print(Panel(table, border_style="cyan"))
        console.print("[dim]Use: /tokens limit <n> or /tokens turns <n>[/dim]")

    elif arg.startswith("limit "):
        try:
            val = int(arg[6:].strip())
            cfg.TRUNCATE_LIMIT = val
            console.print(f"[green]✓ Output truncation limit set to [bold]{val}[/bold] characters.[/green]")
        except ValueError:
            console.print("[red]Error: Limit must be an integer.[/red]")

    elif arg.startswith("turns "):
        try:
            val = int(arg[6:].strip())
            cfg.MAX_TURN_MEMORY = val
            console.print(f"[green]✓ Sliding window set to [bold]{val}[/bold] turns.[/green]")
        except ValueError:
            console.print("[red]Error: Turns must be an integer.[/red]")
    else:
        console.print("[dim]Usage: /tokens [status | limit <n> | turns <n>][/dim]")

def _check_update_logic(repl):
    """Network-check for the latest version on GitHub."""
    import urllib.request
    import re
    from vibehack import __version__
    
    # We prefer checking pyproject.toml as it is the canonical source truth for versioning now
    url = "https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/pyproject.toml"
    console.print("[bold yellow]📡 Checking GitHub for updates...[/bold yellow]")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'VibeHack-Client'})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8')
            # Extract version = "..."
            match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            
            if not match:
                # Fallback to __init__.py if pyproject parsing fails (legacy support)
                fallback_url = "https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/vibehack/__init__.py"
                with urllib.request.urlopen(fallback_url, timeout=5) as fb_resp:
                    fb_content = fb_resp.read().decode('utf-8')
                    match = re.search(r'__version__\s*=\s*"([^"]+)"', fb_content)

            if not match:
                console.print("[red]Error: Could not parse remote version file.[/red]")
                return

            remote_version = match.group(1)
            
            from packaging import version
            
            local_v = version.parse(__version__)
            remote_v = version.parse(remote_version)

            if remote_v > local_v:
                console.print(Panel(
                    f"A new version of VibeHack is available: [bold green]{remote_version}[/bold green]\n"
                    f"You are currently running: [dim]{__version__}[/dim]\n\n"
                    "Run [cyan]vibehack update[/cyan] outside the REPL to upgrade.",
                    title="🚀 Update Available",
                    border_style="green"
                ))
            elif remote_v < local_v:
                console.print(f"[yellow]⚡ You are running a development version (v{__version__}) ahead of GitHub (v{remote_version}).[/yellow]")
            else:
                console.print(f"[green]✓ VibeHack is up to date (v{__version__}).[/green]")
                
    except Exception as e:
        console.print(f"[red]Update check failed:[/red] {e}")
        console.print("[dim]Ensure you have an active internet connection.[/dim]")

def _handle_sessions_interactively(repl):
    """Shows a dialog to pick and resume a session."""
    from prompt_toolkit.shortcuts import radiolist_dialog
    from vibehack.session.persistence import list_sessions, load_session
    from vibehack.llm.provider import Finding
    from vibehack.agent.knowledge import KnowledgeState

    sessions = list_sessions()
    if not sessions:
        console.print("[dim]No saved sessions found.[/dim]")
        return True

    # Build choices with metadata
    choices = []
    # Sort sessions by date (newest first)
    sessions.sort(reverse=True)
    
    for sid in sessions[:15]: # Limit to top 15 for UI
        data = load_session(sid)
        if data:
            target = data.get("target", "No Target")
            date = sid.split("_")[0] # Rough date from ID
            choices.append((sid, f"{sid} | {target}"))

    result = radiolist_dialog(
        title="📂 Resume Session",
        text="Pick a session to hot-swap into the current environment:",
        values=choices
    )
    
    selected_sid = result.run() if hasattr(result, "run") else result

    if selected_sid:
        state = load_session(selected_sid)
        if state:
            # HOT SWAP!
            repl.session_id = state["session_id"]
            repl.target = state.get("target")
            repl.op_mode = state.get("op_mode", "agent")
            repl.persona = state.get("persona", "dev-safe")
            repl.unchained = state.get("unchained", False)
            repl.auto_allow = state.get("auto_allow", False)
            
            # Reconstruct History
            repl.history = state.get("history", [])
            
            # Reconstruct Findings
            repl.key_findings = [Finding(**f) for f in state.get("findings", [])]
            
            # Reconstruct Knowledge
            k_data = state.get("knowledge", {})
            repl.knowledge = KnowledgeState()
            repl.knowledge.open_ports = set(k_data.get("open_ports", []))
            repl.knowledge.technologies = set(k_data.get("technologies", []))
            repl.knowledge.endpoints = k_data.get("endpoints", [])
            repl.knowledge.credentials = k_data.get("credentials", [])
            repl.knowledge.notes = k_data.get("notes", [])
            
            repl._rebuild_system_prompt()
            console.print(f"[bold green]✓ Hot-swapped to session: [cyan]{selected_sid}[/cyan][/bold green]")
            console.print(f"[dim]Target: {repl.target} | History: {len(repl.history)} turns loaded.[/dim]")
            
    return True

def _display_history(repl):
    """Prints a clean summary of the session turns."""
    from rich.table import Table
    import json
    
    if not repl.history:
        console.print("[dim]No history found for this session.[/dim]")
        return

    table = Table(title=f"📜 Session History ({repl.session_id})", box=None)
    table.add_column("Role", style="cyan")
    table.add_column("Content", style="white")

    for turn in repl.history:
        role = turn["role"]
        content = turn["content"]
        
        if role == "system":
            table.add_row("SYSTEM", "[dim]System Prompt Hidden[/dim]")
        elif role == "user":
            if content.startswith("COMMAND:"):
                cmd_line = content.split("\n")[0]
                table.add_row("OBSERVE", f"[yellow]{cmd_line}[/yellow]")
            else:
                table.add_row("USER", content[:80] + ("..." if len(content) > 80 else ""))
        elif role == "assistant":
            try:
                data = json.loads(content)
                thought = data.get("thought", "...")
                cmd = data.get("raw_command", "N/A")
                table.add_row("THOUGHT", f"[italic dim]{thought[:120]}...[/italic dim]")
                if cmd:
                    table.add_row("ACTION", f"[bold green]{cmd}[/bold green]")
            except:
                table.add_row("AI", content[:80] + ("..." if len(content) > 80 else ""))
        
        table.add_section()
        
    console.print(table)

def _handle_skills_command(repl, arg: str):
    """Handle /skills sub-commands: list, install <url>."""
    from pathlib import Path
    import urllib.request
    
    skill_dir = cfg.HOME / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    # Also check internal skills
    internal_skill_dir = Path(__file__).parent.parent.parent / "skills"

    if not arg or arg == "list":
        from rich.table import Table
        table = Table(title="🎯 Expert Security Skills", box=None)
        table.add_column("Source", style="dim")
        table.add_column("Skill Name", style="cyan")
        table.add_column("Trigger Keywords", style="yellow")
        
        # Check both internal and external
        for s_dir, label in [(internal_skill_dir, "Internal"), (skill_dir, "User")]:
            if s_dir.exists():
                for f in s_dir.glob("*.md"):
                    content = f.read_text()
                    first_line = content.split("\n")[0].replace("# Skill:", "").strip()
                    trigger_line = content.split("\n")[1].replace("# Trigger:", "").strip() if len(content.split("\n")) > 1 else "None"
                    table.add_row(label, first_line or f.stem, trigger_line)
        
        console.print(Panel(table, title="Knowledge Base", border_style="cyan"))

    elif arg.startswith("learn "):
        url = arg[6:].strip()
        if not url.startswith("http"):
            console.print("[red]Error: Invalid URL.[/red]")
            return

        console.print(f"[bold yellow]🧠 AI is learning from:[/bold yellow] [dim]{url}...[/dim]")
        
        # 1. Fetch content
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'VibeHack-Client'})
            with urllib.request.urlopen(req, timeout=15) as response:
                raw_html = response.read().decode('utf-8', errors='replace')
                
                # Simple HTML strip to avoid token bloat
                clean_text = re.sub(r'<script.*?</script>', '', raw_html, flags=re.DOTALL)
                clean_text = re.sub(r'<style.*?</style>', '', clean_text, flags=re.DOTALL)
                clean_text = re.sub(r'<.*?>', ' ', clean_text)
                clean_text = ' '.join(clean_text.split())[:8000] # Limit to 8k chars

                # 2. Ask AI to synthesize into Skill format
                learning_prompt = (
                    "You are the VibeHack Knowledge Ingestor.\n"
                    f"Read this content from {url} and extract actionable security techniques.\n"
                    "Convert it into the VibeHack Skill format:\n\n"
                    "# Skill: [Clear Descriptive Title]\n"
                    "# Trigger: [comma, separated, technical, keywords]\n\n"
                    "### [Phase 1: Description]\n...\n"
                    "### [Phase 2: Actionable Payloads/Commands]\n...\n\n"
                    "Output ONLY the markdown content for the skill file."
                )
                
                # Process via AI (Wait for it)
                import asyncio
                async def _learn():
                    return await repl.handler.raw_complete([
                        {"role": "system", "content": learning_prompt},
                        {"role": "user", "content": f"CONTENT FROM {url}:\n\n{clean_text}"}
                    ])
                
                skill_content = asyncio.run(_learn())
                
                # 3. Save as Skill
                # Extract filename from AI output
                match = re.search(r"^# Skill:\s*([a-zA-Z0-9_\-\s]+)", skill_content)
                filename = "learned_" + (match.group(1).strip().lower().replace(" ", "_") if match else "skill") + ".md"
                
                target_path = skill_dir / filename
                target_path.write_text(skill_content)
                
                console.print(Panel(
                    f"AI successfully learned and synthesized: [bold green]'{filename}'[/bold green]\n"
                    "This new knowledge is now part of the expert database.",
                    title="✅ Smart Learning Complete",
                    border_style="green"
                ))

        except Exception as e:
            console.print(f"[red]Learning failed:[/red] {e}")

    elif arg.startswith("edit "):
        name = arg[5:].strip()
        if not name.endswith(".md"): name += ".md"
        
        target_path = skill_dir / name
        if not target_path.exists():
            # Check internal skills too, but we copy to user dir if editing
            internal_path = internal_skill_dir / name
            if internal_path.exists():
                console.print(f"[dim]Note: Copying internal skill '{name}' to user directory for editing...[/dim]")
                target_path.write_text(internal_path.read_text())
            else:
                console.print(f"[red]Error: Skill '{name}' not found.[/red]")
                return

        editor = os.getenv("EDITOR") or os.getenv("VISUAL") or "nano"
        console.print(f"[bold yellow]📝 Opening editor ({editor}):[/bold yellow] [dim]{target_path.name}[/dim]")
        
        import subprocess
        try:
            # We use subprocess.run to allow the editor to take over the TTY
            subprocess.run([editor, str(target_path)])
            console.print(f"[bold green]✅ Skill '{name}' updated.[/bold green]")
        except Exception as e:
            console.print(f"[red]Failed to open editor:[/red] {e}")

    elif arg.startswith("install "):
        url = arg[8:].strip()
        if not url.startswith("http"):
            console.print("[red]Error: Invalid URL.[/red]")
            return

        console.print(f"[bold yellow]📡 Downloading skill from:[/bold yellow] [dim]{url}[/dim]")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'VibeHack-Client'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')
                
                # Auto-generate filename from title or URL
                filename = url.split("/")[-1]
                if not filename.endswith(".md"): filename += ".md"
                
                # Look for # Skill: ... to refine filename
                match = re.search(r"^# Skill:\s*([a-zA-Z0-9_\-\s]+)", content)
                if match:
                    filename = match.group(1).strip().lower().replace(" ", "_") + ".md"
                
                target_path = skill_dir / filename
                target_path.write_text(content)
                
                console.print(Panel(
                    f"Expert Skill [bold green]'{filename}'[/bold green] has been installed.\n"
                    "AI will now automatically use this knowledge when relevant patterns are detected.",
                    title="✅ Skill Installed",
                    border_style="green"
                ))
        except Exception as e:
            console.print(f"[red]Failed to install skill:[/red] {e}")
    else:
        console.print("[dim]Usage: /skills [list | install <url> | edit <name> | learn <url>][/dim]")
