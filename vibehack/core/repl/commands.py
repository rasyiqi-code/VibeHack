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
from vibehack import __version__
from vibehack.utils.version import get_remote_version

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
    "/install":   "Install a tool (/install nuclei)",
    "/findings":  "List confirmed findings",
    "/knowledge": "Show current knowledge state (ports, tech, endpoints)",
    "/map":       "Visualise attack surface as a tree",
    "/report":    "Generate Markdown audit report",
    "/clear":     "Clear conversation history (keeps knowledge & findings)",
    "/memory":    "Browse or search Long-Term Memory (/memory list | /memory search <tech>)",
    "/tokens":    "Manage token economy and context window (/tokens status | limit <n> | turns <n>)",
    "/tools":     "Show tools discovered in your PATH",
    "/check-update": "Check for newer versions on GitHub",
    "/version":   "Show build info and check for updates",
    "/update":    "Full sync/upgrade to latest VibeHack version",
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
        repl.log(Panel("\n".join(lines), title="Slash Commands", border_style="dim"))

    elif verb == "/target":
        if arg:
            err = check_target(arg)
            if err:
                repl.log(f"[red]Blocked:[/red] {err}")
            else:
                repl.target = arg
                repl.log(f"[green]✓ Target:[/green] {arg}")
                repl._rebuild_system_prompt()
        else:
            repl.log(f"Target: [cyan]{repl.target or 'not set'}[/cyan]")

    elif verb == "/mode":
        if arg in ("agent", "ask"):
            repl.op_mode = arg
            repl.log(f"[green]✓ Operation mode:[/green] {arg}")
        else:
            repl.log(f"Mode: {repl.op_mode} | Use: /mode agent  or  /mode ask")

    elif verb == "/persona":
        if arg in ("dev-safe", "pro"):
            repl.persona = arg
            repl.log(f"[green]✓ Persona:[/green] {arg}")
            repl._rebuild_system_prompt()
        else:
            repl.log(f"Persona: {repl.persona} | Use: /persona dev-safe  or  /persona pro")

    elif verb == "/auth":
        from vibehack.core.wizard import _setup_wizard
        from vibehack.config import load_config_env
        _setup_wizard()
        load_config_env()
        cfg.load()
        repl.handler = UniversalHandler(api_key=cfg.API_KEY, model=cfg.MODEL)
        repl.log("[bold green]✓ Authentication updated & AI engine re-initialized.[/bold green]")

    elif verb == "/switch":
        _handle_switch(repl, arg)

    elif verb == "/status":
        _display_status(repl)

    elif verb == "/unchained":
        if not repl.unchained:
            if verify_unchained_access(True):
                repl.unchained = True
                repl.log("[bold red]🔓 Unchained mode enabled.[/bold red]")
                repl._rebuild_system_prompt()
        else:
            repl.unchained = False
            repl.log("[green]🔒 Guardrails restored.[/green]")
            repl._rebuild_system_prompt()

    elif verb == "/install":
        if not arg:
            repl.log("[dim]Usage: /install <tool>[/dim]")
        else:
            from vibehack.toolkit.provisioner import DOWNLOADABLE_TOOLS
            if arg not in DOWNLOADABLE_TOOLS:
                repl.log(f"[red]'{arg}' not in registry.[/red]")
                repl.log(f"[dim]{', '.join(DOWNLOADABLE_TOOLS.keys())}[/dim]")
            else:
                return ("__install__", arg)

    elif verb == "/knowledge":
        _display_knowledge(repl)

    elif verb == "/map":
        if not repl.target:
            repl.log("[red]Set a target first using /target[/red]")
        else:
            display_map(repl.target, repl.knowledge.to_dict(), target_console=repl.target_console)

    elif verb == "/findings":
        _handle_findings(repl)

    elif verb == "/report":
        from vibehack.reporting.exporter import export_report
        path = export_report(repl.target or "unknown", repl.key_findings, repl.history, cfg.HOME / "reports")
        repl.log(f"[bold green]✅ Report:[/bold green] {path}")

    elif verb == "/clear":
        sys_msg = repl.history[0] if repl.history and repl.history[0]["role"] == "system" else None
        repl.history = [sys_msg] if sys_msg else []
        repl.log("[dim]History cleared. Knowledge and findings preserved.[/dim]")

    elif verb == "/memory":
        from vibehack.memory.db import search_experience, get_memory_stats
        from rich.table import Table

        if repl.no_memory:
            repl.log("[dim]LTM disabled.[/dim]")
            return True

        if not arg:
            s = get_memory_stats()
            repl.log(f"🧠 LTM: [bold]{s['total']}[/bold] experiences ([green]{s['successes']} ✅[/green] / [red]{s['failures']} ❌[/red])")
            repl.log("[dim]Use /memory list or /memory search <keyword> to browse.[/dim]")
        
        elif arg.startswith("list"):
            # Use '%' to search for everything
            results = search_experience("", limit=15) # empty string for tech matches all 'LIKE %%%'
            if not results:
                repl.log("[dim]No experiences in database yet.[/dim]")
            else:
                table = Table(title="🧠 Recent Experiences (LTM)")
                table.add_column("Target", style="cyan")
                table.add_column("Tech", style="yellow")
                table.add_column("Score", justify="center")
                table.add_column("Summary", style="white")
                
                for target, tech, payload, score, summary in results:
                    label = "[green]✅[/green]" if score > 0 else ("[red]❌[/red]" if score < 0 else "[dim]ℹ[/dim]")
                    table.add_row(target[:20], tech, label, summary)
                repl.log(table)
                
        elif arg.startswith("search "):
            keyword = arg[7:].strip()
            results = search_experience(keyword, limit=10)
            if not results:
                repl.log(f"[dim]No experiences found for '{keyword}'.[/dim]")
            else:
                table = Table(title=f"🔎 Memory search: '{keyword}'")
                table.add_column("Target", style="cyan")
                table.add_column("Tech", style="yellow")
                table.add_column("Score", justify="center")
                table.add_column("Summary", style="white")
                for target, tech, payload, score, summary in results:
                    label = "[green]✅[/green]" if score > 0 else ("[red]❌[/red]" if score < 0 else "[dim]ℹ[/dim]")
                    table.add_row(target[:20], tech, label, summary)
                repl.log(table)
        else:
            repl.log("[dim]Usage: /memory [list | search <keyword>][/dim]")

    elif verb == "/tokens":
        _handle_tokens_command(repl, arg)

    elif verb == "/tools":
        tools = repl._available_tools
        repl.log(f"[green]Discovered ({len(tools)}):[/green] {', '.join(tools) or 'none'}")
        repl.log("[dim]Scanned from $PATH + ~/.vibehack/bin/[/dim]")

    elif verb == "/check-update":
        _handle_check_update(repl)

    elif verb == "/version":
        repl.log(f"[bold red]🔥 VibeHack v{__version__}[/bold red]")
        repl.log("[dim]Checking for updates...[/dim]")
        remote_v = get_remote_version()
        if remote_v and remote_v != __version__:
            repl.log(f"[yellow]🚀 New version available: v{remote_v}[/yellow]")
            repl.log("[dim]Run /update to upgrade now.[/dim]")
        elif remote_v:
            repl.log("[green]✓ You are on the newest version.[/green]")

    elif verb == "/update":
        _handle_update(repl)

    elif verb in ("/exit", "/quit", "/q"):
        return False

    else:
        repl.log(f"[red]Unknown:[/red] {verb}. Type /help")

    return True

def _handle_switch(repl, arg: str):
    if not arg:
        repl.log("[dim]Usage: /switch <provider|model>[/dim]\n[dim]Examples: /switch openai, /switch claude, /switch gemini-1.5-pro[/dim]")
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
        repl.log(f"[red]Error: No API Key found for {new_provider or new_model}.[/red]\n[dim]Run /auth first.[/dim]")
    else:
        repl.handler.switch_model(model=new_model, api_key=new_key, provider=new_provider)
        repl.log(f"[bold green]✓ Seamless Switch:[/bold green] Brain swapped to [cyan]{new_model}[/cyan]")

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
    repl.log(Panel(table, border_style="dim"))

def _display_knowledge(repl):
    k = repl.knowledge
    if k.is_empty():
        repl.log("[dim]No knowledge accumulated yet. Start scanning.[/dim]")
        return
    if k.open_ports:
        repl.log(f"🔌 [bold]Open ports:[/bold] {', '.join(map(str, sorted(k.open_ports)))}")
    if k.technologies:
        repl.log(f"⚙  [bold]Technologies:[/bold] {', '.join(sorted(k.technologies))}")
    if k.endpoints:
        repl.log(f"🗺  [bold]Endpoints ({len(k.endpoints)}):[/bold] {', '.join(k.endpoints[:10])}{'...' if len(k.endpoints) > 10 else ''}")
    if k.credentials:
        repl.log(f"🔑 [bold]Credentials:[/bold] {len(k.credentials)} found")
    for note in k.notes[-5:]:
        repl.log(f"  • {note}")

def _handle_check_update(repl):
    repl.log("\n[bold yellow]📡 Checking for updates...[/bold yellow]")
    remote_v = get_remote_version()
    if not remote_v:
        repl.log("[bold red]Error:[/bold red] Could not reach GitHub.")
        return
    if remote_v == __version__:
        repl.log(f"[green]✓ You are running the latest version (v{__version__}).[/green]")
    else:
        repl.log(f"[bold cyan]Update Available! 🚀[/bold cyan]")
        repl.log(f"Local:  [bold yellow]v{__version__}[/bold yellow]")
        repl.log(f"Latest: [bold green]v{remote_v}[/bold green]")
        repl.log("[dim]Run /update to upgrade.[/dim]")

def _handle_findings(repl):
    if not repl.key_findings:
        repl.log("[dim]No confirmed findings yet.[/dim]")
    else:
        BADGES = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
        for i, f in enumerate(repl.key_findings, 1):
            repl.log(f"  {i}. {BADGES.get(f.severity.lower(), '?')} [{f.severity.upper()}] {f.title}")

def _handle_update(repl):
    repl.log("\n[bold yellow]📡 Syncing with GitHub...[/bold yellow]")
    remote_v = get_remote_version()
    
    if remote_v == __version__ and remote_v:
        repl.log("[green]✓ Already up to date.[/green]")
        return

    import sys
    import subprocess
    repo_url = "git+https://github.com/rasyiqi-code/VibeHack.git"
    
    try:
        repl.log(f"[bold cyan]Upgrading VibeHack to v{remote_v or 'latest'}...[/bold cyan]")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", repo_url],
            check=True,
            capture_output=True
        )
        repl.log(f"[bold green]✅ VibeHack successfully updated![/bold green]")
        repl.log("[bold yellow]Please restart VibeHack to apply changes.[/bold yellow]\n")
    except Exception as e:
        repl.log(f"[bold red]Update failed![/bold red] {e}")

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
        repl.log(Panel(table, border_style="cyan"))
        repl.log("[dim]Use: /tokens limit <n> or /tokens turns <n>[/dim]")

    elif arg.startswith("limit "):
        try:
            val = int(arg[6:].strip())
            cfg.TRUNCATE_LIMIT = val
            repl.log(f"[green]✓ Output truncation limit set to [bold]{val}[/bold] characters.[/green]")
        except ValueError:
            console.print("[red]Error: Limit must be an integer.[/red]")

    elif arg.startswith("turns "):
        try:
            val = int(arg[6:].strip())
            cfg.MAX_TURN_MEMORY = val
            repl.log(f"[green]✓ Sliding window set to [bold]{val}[/bold] turns.[/green]")
        except ValueError:
            repl.log("[red]Error: Turns must be an integer.[/red]")
    else:
        repl.log("[dim]Usage: /tokens [status | limit <n> | turns <n>][/dim]")
