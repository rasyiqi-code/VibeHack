"""
vibehack/cli.py — CLI entry point for Vibe_Hack v1.7

Primary UX: run `vibehack` with no arguments → opens interactive REPL
            (like official security CLIs, but for offensive security)

Secondary UX: `vibehack start <target>` for quick one-shot sessions
"""
import asyncio
import os
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
from vibehack.toolkit.provisioner import DOWNLOADABLE_TOOLS, APT_TOOLS, get_install_hint
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
    help="🔥 Vibe_Hack v2.6.11 — The Autonomous Weapon (Universal Reconfig Release)",
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


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    op_mode: str = typer.Option("agent", "--op-mode", help="Operation mode: agent | ask"),
    persona: str = typer.Option("dev-safe", "--persona", "-p", help="Persona: dev-safe | pro"),
    unchained: bool = typer.Option(False, "--unchained", help="Bypass regex guardrails (requires waiver)"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Disable Long-Term Memory"),
    sandbox: bool = typer.Option(False, "--sandbox", help="Run LLM shell commands inside a Docker container"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model (e.g. model-provider/model-name)"),
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Pre-load target URL/IP"),
):
    """
    🔥 Interactive hacking REPL — an advanced co-pilot for offensive security.

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
    if ctx.invoked_subcommand is not None:
        return  # Let the subcommand handle it

    # Force hard clear immediately for clean transition
    os.system('clear' if os.name == 'posix' else 'cls')

    if model:
        os.environ["VH_MODEL"] = model
        cfg.MODEL = model

    if sandbox:
        cfg.SANDBOX_ENABLED = True
        from vibehack.core.sandbox import start_sandbox
        start_sandbox()

    api_key = _get_api_key()
    console.clear()

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
    console.clear()
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
    console.clear()
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
def check():
    """Health-check: tools discovered in $PATH + Long-Term Memory stats."""
    console.print("[bold cyan]🛠  Vibe_Hack Health Check[/bold cyan]\n")

    # §6.2: Dynamic discovery — not a static list
    discovered = discover_tools()

    # Split into known-security vs LotL built-ins for display
    from vibehack.toolkit.provisioner import DOWNLOADABLE_TOOLS, APT_TOOLS
    all_managed = set(DOWNLOADABLE_TOOLS) | set(APT_TOOLS)
    security_tools = [t for t in discovered if t in all_managed]
    lotl_tools = [t for t in discovered if t not in all_managed]

    from rich.table import Table
    table = Table(title=f"Discovered Security Tools ({len(security_tools)} managed + {len(lotl_tools)} LotL)", show_lines=True)
    table.add_column("Tool", style="cyan", no_wrap=True)
    table.add_column("Type", style="dim")
    table.add_column("How to install (if missing)", style="dim")

    for tool in security_tools:
        table.add_row(tool, "[green]security[/green]", "[green]— installed[/green]")
    for tool in lotl_tools:
        table.add_row(tool, "[blue]LotL[/blue]", "[blue]— built-in[/blue]")

    # Show what's missing from managed list
    missing_dl = [t for t in DOWNLOADABLE_TOOLS if t not in discovered]

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

    if missing_dl:
        console.print(f"[yellow]⬇  {len(missing_dl)} security tools can be auto-installed:[/yellow]")
        for t in missing_dl[:8]:
            console.print(f"  vibehack install {t}")
        if len(missing_dl) > 8:
            console.print(f"  ... and {len(missing_dl) - 8} more")



@app.command(name="install")
def install_tool(
    tool: str = typer.Argument(..., help="Tool to install (e.g. nuclei, rustscan)"),
):
    """Download and install a security tool to ~/.vibehack/bin/."""
    from vibehack.toolkit.provisioner import download_tool

    if tool not in DOWNLOADABLE_TOOLS:
        console.print(f"[red]'{tool}' not in auto-provision registry.[/red]")
        console.print(f"[dim]Downloadable: {', '.join(DOWNLOADABLE_TOOLS.keys())}[/dim]")
        raise typer.Exit(code=1)
    safe_run(download_tool(tool))


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
