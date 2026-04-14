"""
vibehack/cli.py — CLI entry point for Vibe_Hack v1.7

Primary UX: run `vibehack` with no arguments → opens interactive REPL
            (like Claude Code / Gemini CLI, but for offensive security)

Secondary UX: `vibehack start <target>` for quick one-shot sessions
"""
import asyncio
import os
import sys
from typing import Optional

import typer
from vibehack import __version__
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from vibehack.agent.loop import AgentLoop
from vibehack.config import cfg
from vibehack.memory.db import init_memory, get_memory_stats
from vibehack.repl import VibehackREPL
from vibehack.toolkit.discovery import discover_tools
from vibehack.toolkit.manager import BIN_DIR, VIBEHACK_HOME
from vibehack.toolkit.provisioner import get_install_hint
from vibehack.core.discovery import (
    get_gemini_info, get_claude_info, get_codex_info, 
    get_github_info, get_opencode_info
)
from vibehack.core.auth import manual_google_login


def safe_run(coro):
    """Safely run an async coroutine from a synchronous context, handling existing loops."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


load_dotenv()

app = typer.Typer(
    help=f"🔥 Vibe_Hack v{__version__} — The Intelligence & Optimization Release",
    no_args_is_help=False,  # Allow bare `vibehack` to open REPL
    invoke_without_command=True,
)
console = Console()


from vibehack.core.wizard import _setup_wizard

def _get_api_key() -> str:
    key = cfg.API_KEY
    if not key:
        return _setup_wizard()
    return key


def _check_os_safety():
    """Warns user if not running on Linux/WSL."""
    if sys.platform != "linux":
        console.print("\n[bold yellow]⚠️  ENVIRONMENT WARNING[/bold yellow]")
        console.print(f"VibeHack detected platform: [bold cyan]{sys.platform}[/bold cyan]")
        console.print("This engine is highly optimized for [bold green]Linux / WSL2[/bold green].")
        console.print("Running on other platforms may cause tool discovery and sandbox failures.")
        
        if sys.platform == "win32":
            console.print("\n[bold cyan]💡 RECOMMENDATION (Windows):[/bold cyan]")
            console.print("Please install [bold]WSL2[/bold] to run VibeHack. Simply run this in PowerShell:")
            console.print("  [white]wsl --install[/white]")
        elif sys.platform == "darwin":
            console.print("\n[bold cyan]💡 RECOMMENDATION (macOS):[/bold cyan]")
            console.print("Please use a [bold]Linux Docker container[/bold] or [bold]UTM/Multipass[/bold] VM.")
        
        console.print("\n[dim]Continuing anyway in 3 seconds...[/dim]")
        import time
        time.sleep(3)


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    op_mode: str = typer.Option("agent", "--op-mode", help="Operation mode: agent | ask"),
    persona: str = typer.Option("dev-safe", "--persona", "-p", help="Persona: dev-safe | pro"),
    unchained: bool = typer.Option(False, "--unchained", help="Bypass regex guardrails (requires waiver)"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Disable Long-Term Memory"),
    sandbox: bool = typer.Option(False, "--sandbox", help="Run LLM shell commands inside a Docker container"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model (e.g. openai/gpt-4o)"),
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Pre-load target URL/IP"),
):
    """
    🔥 Interactive hacking REPL — like Claude Code, but for offensive security.

    Run with no arguments to open the AI hacking assistant.
    Type naturally: 'scan localhost:3000', 'fuzz the API', 'check for SQLi'.
    Use /help inside the REPL for slash commands.

    Examples:
      vibehack
      vibehack --target http://localhost:3000
      vibehack --persona pro --target http://10.0.0.5
      vibehack --op-mode ask
      vibehack --unchained
    """
    _check_os_safety()
    if ctx.invoked_subcommand is not None:
        return  # Let the subcommand handle it

    if model:
        os.environ["VH_MODEL"] = model
        cfg.MODEL = model

    if sandbox:
        cfg.SANDBOX_ENABLED = True
        from vibehack.core.sandbox import start_sandbox
        start_sandbox()

    api_key = _get_api_key()

    if not no_memory:
        init_memory()

    repl = VibehackREPL(
        target=target,
        op_mode=op_mode,
        persona=persona,
        unchained=unchained,
        no_memory=no_memory,
        api_key=api_key,
    )
    safe_run(repl.run())


@app.command()
def auth():
    """Reconfigure AI provider and API keys interactively."""
    from vibehack.core.wizard import _setup_wizard
    from vibehack.config import load_config_env
    _setup_wizard()
    load_config_env()
    cfg.load()
    console.print("[bold green]✓ Authentication updated.[/bold green]")


@app.command()
def start(
    target: str = typer.Argument(..., help="Target URL or IP"),
    persona: str = typer.Option("dev-safe", "--persona", "-p", help="Persona: dev-safe | pro"),
    unchained: bool = typer.Option(False, "--unchained", help="Bypass regex guardrails"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Disable Long-Term Memory"),
    sandbox: bool = typer.Option(False, "--sandbox", help="Run LLM shell commands inside a Docker container"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
):
    """Start a quick session directly against a target (non-REPL mode)."""
    if model:
        os.environ["VH_MODEL"] = model
        cfg.MODEL = model

    if sandbox:
        cfg.SANDBOX_ENABLED = True
        from vibehack.core.sandbox import start_sandbox
        start_sandbox()

    api_key = _get_api_key()
    if not no_memory:
        init_memory()

    loop = AgentLoop(
        target=target,
        api_key=api_key,
        persona=persona,
        unchained=unchained,
        no_memory=no_memory,
    )
    safe_run(loop.run())


@app.command()
def resume(
    session_id: str = typer.Argument(..., help="Session ID to resume"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
):
    """Resume a previous REPL session from disk."""
    from vibehack.session.persistence import load_session
    from vibehack.llm.provider import Finding

    api_key = _get_api_key()
    state = load_session(session_id)
    if not state:
        console.print(f"[bold red]Session '{session_id}' not found.[/bold red]")
        console.print("[dim]List saved sessions: vibehack sessions[/dim]")
        raise typer.Exit(code=1)

    if model:
        os.environ["VH_MODEL"] = model
        cfg.MODEL = model

    repl = VibehackREPL(
        target=state.get("target") or None,
        op_mode=state.get("op_mode", "agent"),
        persona=state.get("persona", state.get("mode", "dev-safe")), # fallback to mode for legacy
        unchained=state.get("unchained", False),
        api_key=api_key,
    )
    repl.session_id = session_id
    repl.history = state.get("history", [])
    repl.key_findings = [Finding(**f) for f in state.get("findings", [])]
    repl.auto_allow = state.get("auto_allow", False)
    repl._system_built = bool(repl.history and repl.history[0]["role"] == "system")

    console.print(f"[bold green]Resuming session:[/bold green] {session_id}")
    console.print(f"[dim]Target: {repl.target} | {len(repl.key_findings)} findings[/dim]\n")
    safe_run(repl.run())


@app.command()
def report(
    session_id: str = typer.Argument(..., help="Session ID to report"),
    format: str = typer.Option("pdf", "--format", help="Export format: pdf | md"),
):
    """Generate an audit report from a completed session."""
    from vibehack.session.persistence import load_session
    from vibehack.reporting.exporter import export_report
    from vibehack.llm.provider import Finding

    state = load_session(session_id)
    if not state:
        console.print(f"[bold red]Session '{session_id}' not found.[/bold red]")
        raise typer.Exit(code=1)

    findings = [Finding(**f) for f in state.get("findings", [])]
    path = export_report(state["target"], findings, state["history"], cfg.HOME / "reports", fmt=format.lower())
    console.print(f"[bold green]✅ Report saved:[/bold green] {path}")


@app.command()
def check(
    tool: Optional[str] = typer.Option(None, "--tool", help="Check for a specific tool instead of listing all"),
):
    """Health-check: tools discovered in $PATH + Long-Term Memory stats."""
    if tool:
        found = discover_tools()
        if tool in found:
            console.print(f"[bold green]✓ {tool} is installed.[/bold green]")
        else:
            console.print(f"[bold red]✗ {tool} is NOT found.[/bold red]")
        return

    console.print("[bold cyan]🛠  Vibe_Hack Health Check[/bold cyan]\n")

    # §6.2: Dynamic discovery — not a static list
    discovered = discover_tools()

    from rich.table import Table
    table = Table(title="Discovered Tools", show_lines=True)
    table.add_column("Tool", style="cyan", no_wrap=True)
    
    # Truncate for AI safety
    if len(discovered) > 50:
        for t in list(discovered)[:40]:
            table.add_row(t)
        table.add_row(f"... and {len(discovered) - 40} more")
    else:
        for t in discovered:
            table.add_row(t)

    console.print(table)

    # LTM stats
    try:
        init_memory()
        stats = get_memory_stats()
        console.print(
            f"\n[dim]🧠 Long-Term Memory: {stats['total']} experiences "
            f"({stats['successes']} ✅ / {stats['failures']} ❌)[/dim]"
        )
    except Exception:
        pass

    console.print(f"[dim]📁 Home: {VIBEHACK_HOME}[/dim]")
    console.print(f"[dim]🔍 Total tools discovered: {len(discovered)}[/dim]\n")






@app.command()
def sessions():
    """List all saved sessions with target, findings count, and timestamp."""
    from vibehack.session.persistence import list_sessions, load_session

    saved = list_sessions()
    if not saved:
        console.print("[dim]No saved sessions found.[/dim]")
        return

    table = Table(title="Saved Sessions", show_lines=True)
    table.add_column("Session ID", style="cyan", no_wrap=True)
    table.add_column("Target", style="white")
    table.add_column("Findings", style="yellow", justify="right")
    table.add_column("Saved At", style="dim")

    for s in sorted(saved, reverse=True):
        state = load_session(s)
        if state:
            tgt = state.get("target", "?")
            n = len(state.get("findings", []))
            ts = state.get("saved_at", "?")[:19]
        else:
            tgt, n, ts = "?", 0, "?"
        table.add_row(s, tgt, str(n), ts)

    console.print(table)
    
@app.command(name="check-update")
def check_update_cli():
    """Network-check for the latest version on GitHub."""
    from vibehack.core.repl.commands import _check_update_logic
    _check_update_logic(repl=None)


@app.command()
def update():
    """Self-update Vibe_Hack to the latest version from GitHub."""
    console.print("\n[bold yellow]📡 Checking for updates...[/bold yellow]")
    import sys
    import subprocess
    
    repo_url = "git+https://github.com/rasyiqi-code/VibeHack.git"
    
    try:
        with console.status("[bold cyan]Updating Vibe_Hack core...[/bold cyan]"):
            # We use sys.executable to ensure we update the current venv
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", repo_url],
                check=True,
                capture_output=True
            )
        console.print("[bold green]✅ Vibe_Hack successfully updated to the latest version![/bold green]")
        console.print("[dim]Restart vibehack to apply changes.[/dim]\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Update failed![/bold red]")
        console.print(f"[dim]{e.stderr.decode()}[/dim]")



@app.command()
def version():
    """Show version and build info."""
    console.print(f"[bold red]🔥 Vibe_Hack v{__version__}[/bold red]")
    console.print("[dim]The Autonomous Weapon Update — Multi-Provider Edition[/dim]")
    console.print(f"[dim]Home: {VIBEHACK_HOME}[/dim]")
    console.print(f"[dim]Default model: {cfg.MODEL}[/dim]")


if __name__ == "__main__":
    app()
