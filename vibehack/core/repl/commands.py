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
    display_map, display_finding, display_banner, display_notice, log_to_pane
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
    "/open":      "Open the workspace folder in your OS file manager",
    "/exit":      "Save session and exit",
}

async def handle_slash_command(repl, cmd: str) -> Union[bool, Tuple[str, str]]:
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
        lines = [f"  {k:15}  {v}" for k, v in SLASH_COMMANDS.items()]
        help_text = "\n".join(lines)
        log_to_pane(repl, "history", f"\n[ SLASH COMMANDS ]\n{help_text}\n")

    elif verb == "/target":
        if arg:
            err = check_target(arg)
            if err:
                log_to_pane(repl, "logs", f"🚨 Blocked: {err}")
            else:
                repl.target = arg
                log_to_pane(repl, "logs", f"🎯 Target Set: {arg}")
                repl._rebuild_system_prompt()
        else:
            log_to_pane(repl, "history", f"Current Target: {repl.target or 'not set'}")

    elif verb == "/mode":
        if arg in ("agent", "ask"):
            repl.op_mode = arg
            log_to_pane(repl, "logs", f"⚙️ Operational Mode: {arg.upper()}")
        else:
            log_to_pane(repl, "history", f"Operational Mode: {repl.op_mode.upper()} | Use: /mode agent | ask")

    elif verb == "/persona":
        if arg in ("dev-safe", "pro"):
            repl.persona = arg
            log_to_pane(repl, "logs", f"🎭 Persona Set: {arg.upper()}")
            repl._rebuild_system_prompt()
        else:
            log_to_pane(repl, "history", f"Persona: {repl.persona.upper()} | Use: /persona dev-safe | pro")

    elif verb == "/auth":
        from vibehack.core.wizard import _setup_wizard
        from vibehack.config import load_config_env
        
        def _run_auth():
            _setup_wizard()
            load_config_env()
            cfg.load()
        
        if repl and hasattr(repl, "app"):
            from prompt_toolkit.application import run_in_terminal
            await run_in_terminal(_run_auth)
        else:
            _run_auth()
            
        repl.handler = UniversalHandler(api_key=cfg.API_KEY, model=cfg.MODEL)
        log_to_pane(repl, "logs", "✓ Authentication updated & AI engine re-initialized.")

    elif verb == "/switch":
        _handle_switch(repl, arg)

    elif verb == "/status":
        _display_status(repl)

    elif verb == "/sessions":
        return await _handle_sessions_interactively(repl)

    elif verb == "/unchained":
        if not repl.unchained:
            if verify_unchained_access(True):
                repl.unchained = True
                log_to_pane(repl, "logs", "🔓 UNCHAINED MODE ENABLED — Guardrails disabled.")
                repl._rebuild_system_prompt()
        else:
            repl.unchained = False
            log_to_pane(repl, "logs", "🔒 Guardrails restored.")
            repl._rebuild_system_prompt()

    elif verb == "/knowledge":
        _display_knowledge(repl)

    elif verb == "/map":
        if not repl.target:
            log_to_pane(repl, "history", "🚨 Set a target first using /target")
        else:
            # For complex trees, we just log a simplified list to the pane for now
            log_to_pane(repl, "history", "\n[ ATTACK SURFACE MAP ]")
            for port in sorted(repl.knowledge.open_ports):
                log_to_pane(repl, "history", f"  • Port {port}")
            for tech in sorted(repl.knowledge.technologies):
                log_to_pane(repl, "history", f"  • Tech: {tech}")
            for ep in repl.knowledge.endpoints[:10]:
                log_to_pane(repl, "history", f"  • Endpoint: {ep}")

    elif verb == "/skills":
        await _handle_skills_command(repl, arg)

    elif verb == "/findings":
        _display_findings(repl)

    elif verb == "/report":
        from vibehack.reporting.exporter import export_report
        path = export_report(repl.target or "unknown", repl.key_findings, repl.history, cfg.HOME / "reports")
        log_to_pane(repl, "logs", f"✅ Report Generated: {path}")

    elif verb == "/clear":
        sys_msg = repl.history[0] if repl.history and repl.history[0]["role"] == "system" else None
        repl.history = [sys_msg] if sys_msg else []
        repl.history_buffer.text = ""
        log_to_pane(repl, "history", "✓ Mission Timeline cleared. Knowledge and findings preserved.")

    elif verb == "/memory":
        from vibehack.memory.db import search_experience, get_memory_stats
        if repl.no_memory:
            log_to_pane(repl, "logs", "🧠 LTM disabled.")
            return True

        if not arg:
            s = get_memory_stats()
            log_to_pane(repl, "history", f"\n[ LONG-TERM MEMORY ]\n  • Experiences: {s['total']}\n  • Successes: {s['successes']}\n  • Failures: {s['failures']}\n")
        elif arg.startswith("list"):
            results = search_experience("", limit=15)
            if not results:
                log_to_pane(repl, "history", "🧠 No experiences in database yet.")
            else:
                log_to_pane(repl, "history", "\n[ RECENT EXPERIENCES ]")
                for target, tech, payload, score, summary in results:
                    label = "✅" if score > 0 else ("❌" if score < 0 else "ℹ")
                    log_to_pane(repl, "history", f"  {label} [{tech}] {target[:20]}: {summary}")
        elif arg.startswith("search "):
            keyword = arg[7:].strip()
            results = search_experience(keyword, limit=10)
            if not results:
                log_to_pane(repl, "history", f"🧠 No experiences found for '{keyword}'")
            else:
                log_to_pane(repl, "history", f"\n[ MEMORY SEARCH: {keyword} ]")
                for target, tech, payload, score, summary in results:
                    label = "✅" if score > 0 else ("❌" if score < 0 else "ℹ")
                    log_to_pane(repl, "history", f"  {label} [{tech}] {target[:20]}: {summary}")
        else:
            log_to_pane(repl, "history", "Usage: /memory [list | search <keyword>]")

    elif verb == "/tokens":
        if not arg or arg == "status":
            log_to_pane(repl, "history", f"\n[ TOKEN ECONOMY ]\n  • Limit: {cfg.TOKEN_LIMIT}\n  • Window: {cfg.CONTEXT_WINDOW} turns\n")
        elif arg.startswith("limit "):
            try:
                val = int(arg[6:].strip())
                cfg.TOKEN_LIMIT = val
                log_to_pane(repl, "logs", f"✓ Output truncation limit: {val}")
            except:
                log_to_pane(repl, "logs", "🚨 Error: Limit must be an integer.")
        elif arg.startswith("turns "):
            try:
                val = int(arg[6:].strip())
                cfg.CONTEXT_WINDOW = val
                log_to_pane(repl, "logs", f"✓ Context window: {val} turns")
            except:
                log_to_pane(repl, "logs", "🚨 Error: Turns must be an integer.")
        else:
            log_to_pane(repl, "history", "Usage: /tokens [status | limit <n> | turns <n>]")

    elif verb == "/tools":
        from vibehack.toolkit.discovery import discover_tools
        tools = discover_tools()
        log_to_pane(repl, "history", f"\n[ DISCOVERED TOOLS ]\n{', '.join(tools) or 'none'}\n")
        log_to_pane(repl, "logs", f"ℹ {len(tools)} tools available in path.")

    elif verb == "/check-update":
        _check_update_logic(repl)

    elif verb in ("/exit", "/quit", "/q"):
        return False

    elif verb == "/history":
        await _display_history(repl)

    elif verb == "/open":
        import platform
        import subprocess
        
        workspace_path = str(cfg.HOME / "workspace")
        if not os.path.exists(workspace_path):
            os.makedirs(workspace_path, exist_ok=True)
            
        log_to_pane(repl, "logs", f"📂 Opening workspace: {workspace_path}")
        
        try:
            if platform.system() == "Darwin":       # macOS
                subprocess.run(["open", workspace_path])
            elif platform.system() == "Windows":    # Windows
                os.startfile(workspace_path)
            else:                                   # Linux
                subprocess.run(["xdg-open", workspace_path])
        except Exception as e:
            log_to_pane(repl, "logs", f"🚨 Failed to open folder: {e}")

    else:
        log_to_pane(repl, "history", f"🚨 Unknown command: {verb}. Type /help for assistance.")

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
        log_to_pane(repl, "logs", f"🚨 Error: No API Key found for {new_provider or new_model}. Run /auth first.")
        return
        
    repl.handler = UniversalHandler(api_key=new_key, model=new_model)
    cfg.MODEL = new_model
    log_to_pane(repl, "logs", f"✓ Seamless Switch: Brain swapped to {new_model}")

def _display_status(repl):
    """Refined status for the dashboard pane."""
    m = getattr(repl, 'handler', None)
    model = m.model if m else "???"
    log_to_pane(repl, "history", f"\n[ SYSTEM STATUS ]\n  • Model: {model}\n  • Target: {repl.target or 'none'}\n  • Mode: {repl.op_mode.upper()}\n  • Findings: {len(repl.key_findings)}\n  • Session: {repl.session_id}\n")

def _display_knowledge(repl):
    k = repl.knowledge
    log_to_pane(repl, "history", "\n[ INTELLIGENCE BASE ]")
    if not k.open_ports and not k.technologies and not k.endpoints:
        log_to_pane(repl, "history", "  • No knowledge accumulated yet.")
    else:
        if k.open_ports: log_to_pane(repl, "history", f"  • Ports: {', '.join(map(str, sorted(k.open_ports)))}")
        if k.technologies: log_to_pane(repl, "history", f"  • Tech: {', '.join(sorted(k.technologies))}")
        if k.endpoints: log_to_pane(repl, "history", f"  • Endpoints ({len(k.endpoints)})")
        if k.credentials: log_to_pane(repl, "history", f"  • Credentials Found: {len(k.credentials)}")
    for note in k.notes[-5:]:
        log_to_pane(repl, "history", f"  • {note}")

def _display_findings(repl):
    if not repl.key_findings:
        log_to_pane(repl, "history", "🚨 No confirmed findings yet.")
    else:
        log_to_pane(repl, "history", "\n[ MISSION FINDINGS ]")
        for i, f in enumerate(repl.key_findings, 1):
            log_to_pane(repl, "history", f"  {i}. [{f.severity.upper()}] {f.title}")

def _check_update_logic(repl):
    """Network-check for the latest version on GitHub."""
    import urllib.request
    import re
    from vibehack import __version__
    log_to_pane(repl, "logs", "📡 Checking for updates...")
    try:
        url = "https://raw.githubusercontent.com/rasyiqi/VibeHack/main/vibehack/__init__.py"
        with urllib.request.urlopen(url, timeout=5) as r:
            content = r.read().decode()
            remote_version = re.search(r'__version__ = "([^"]+)"', content).group(1)
            if remote_version > __version__:
                log_to_pane(repl, "history", f"\n⚠️  UPDATE AVAILABLE: v{remote_version} (Current: v{__version__})\n  • Running: pip install --upgrade git+https://github.com/rasyiqi/VibeHack.git\n")
            else:
                log_to_pane(repl, "logs", f"✓ VibeHack is up to date (v{__version__}).")
    except Exception as e:
        log_to_pane(repl, "logs", f"🚨 Update check failed: {e}")

async def _handle_sessions_interactively(repl):
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

    dialog = radiolist_dialog(
        title="📂 Resume Session",
        text="Pick a session to hot-swap into the current environment:",
        values=choices
    )
    
    if repl and hasattr(repl, "app"):
        from prompt_toolkit.application import run_in_terminal
        selected_sid = await run_in_terminal(dialog.run)
    else:
        selected_sid = await dialog.run_async() if hasattr(dialog, "run_async") else dialog.run()

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

async def _display_history(repl):
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
        
    if repl and hasattr(repl, "app"):
        from prompt_toolkit.application import run_in_terminal
        await run_in_terminal(lambda: console.print(table))
    else:
        console.print(table)

async def _handle_skills_command(repl, arg: str):
    """Handle /skills sub-commands: list, install <url>."""
    from pathlib import Path
    import urllib.request
    
    skill_dir = cfg.HOME / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    # Also check internal skills
    internal_skill_dir = Path(__file__).parent.parent.parent / "skills"

    if not arg or arg == "list":
        log_to_pane(repl, "history", "\n[ EXPERT SECURITY SKILLS ]")
        for s_dir, label in [(internal_skill_dir, "Internal"), (skill_dir, "User")]:
            if s_dir.exists():
                for f in s_dir.glob("*.md"):
                    content = f.read_text()
                    first_line = content.split("\n")[0].replace("# Skill:", "").strip()
                    log_to_pane(repl, "history", f"  • {first_line or f.stem} ({label})")
        
    elif arg.startswith("learn "):
        url = arg[6:].strip()
        if not url.startswith("http"):
            log_to_pane(repl, "logs", "🚨 Error: Invalid URL.")
            return True

        log_to_pane(repl, "logs", f"🧠 AI is learning from: {url}")
        
        # 1. Fetch content (asynchronous fetch)
        try:
            import httpx
            async with httpx.AsyncClient(headers={'User-Agent': 'VibeHack-Client'}) as client:
                response = await client.get(url, timeout=15)
                raw_html = response.text
                
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
                skill_content = await repl.handler.raw_complete([
                    {"role": "system", "content": learning_prompt},
                    {"role": "user", "content": f"CONTENT FROM {url}:\n\n{clean_text}"}
                ])
                
                # 3. Save as Skill
                # Extract filename from AI output
                match = re.search(r"^# Skill:\s*([a-zA-Z0-9_\-\s]+)", skill_content)
                filename = "learned_" + (match.group(1).strip().lower().replace(" ", "_") if match else "skill") + ".md"
                
                target_path = skill_dir / filename
                target_path.write_text(skill_content)
                
                log_to_pane(repl, "history", f"\n✅ Smart Learning Complete: synthesized '{filename}'\n")

        except Exception as e:
            log_to_pane(repl, "logs", f"🚨 Learning failed: {e}")

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
            def _run_editor():
                subprocess.run([editor, str(target_path)])
                console.print(f"[bold green]✅ Skill '{name}' updated.[/bold green]")

            if repl and hasattr(repl, "app"):
                from prompt_toolkit.application import run_in_terminal
                await run_in_terminal(_run_editor)
            else:
                _run_editor()
        except Exception as e:
            console.print(f"[red]Failed to open editor:[/red] {e}")

    elif arg.startswith("install "):
        url = arg[8:].strip()
        if not url.startswith("http"):
            log_to_pane(repl, "logs", "🚨 Error: Invalid URL.")
            return True

        log_to_pane(repl, "logs", f"📡 Downloading skill from: {url}")
        try:
            import httpx
            async with httpx.AsyncClient(headers={'User-Agent': 'VibeHack-Client'}) as client:
                response = await client.get(url, timeout=10)
                content = response.text
                
                # Auto-generate filename from title or URL
                filename = url.split("/")[-1]
                if not filename.endswith(".md"): filename += ".md"
                
                # Look for # Skill: ... to refine filename
                match = re.search(r"^# Skill:\s*([a-zA-Z0-9_\-\s]+)", content)
                if match:
                    filename = match.group(1).strip().lower().replace(" ", "_") + ".md"
                
                target_path = skill_dir / filename
                target_path.write_text(content)
                
                log_to_pane(repl, "history", f"\n✅ Skill Installed: '{filename}'\n")
        except Exception as e:
            log_to_pane(repl, "logs", f"🚨 Installation failed: {e}")
    else:
        console.print("[dim]Usage: /skills [list | install <url> | edit <name> | learn <url>][/dim]")
