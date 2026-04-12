"""
vibehack/cli.py — CLI entry point for Vibe_Hack v1.7

Primary UX: run `vibehack` with no arguments → opens interactive REPL
            (like Claude Code / Gemini CLI, but for offensive security)

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
    find_gemini_key, find_claude_key, find_codex_key, 
    find_github_token, find_opencode_key
)


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
    help="🔥 Vibe_Hack v2.4 — The Autonomous Weapon (Multi-Provider Release)",
    no_args_is_help=False,  # Allow bare `vibehack` to open REPL
    invoke_without_command=True,
)
console = Console()


def _setup_wizard():
    """Interactive multi-provider setup wizard."""
    from rich.prompt import Prompt
    from vibehack.ui.tui import get_masked_input
    
    console.print("\n[bold yellow]🤖 Vibe_Hack Configuration Wizard[/bold yellow]")
    console.print("Choose your AI provider (Tiru OpenClaw Style)\n")
    
    providers = {
        "1": ("openrouter", "OpenRouter (Recommended)", "OPENROUTER_API_KEY", "openrouter/anthropic/claude-3.5-sonnet"),
        "2": ("google", "Google Gemini", "GEMINI_API_KEY", "gemini/gemini-1.5-pro-latest"),
        "3": ("anthropic", "Anthropic Claude", "ANTHROPIC_API_KEY", "anthropic/claude-3-5-sonnet-20240620"),
        "4": ("openai", "OpenAI / ChatGPT Codex", "OPENAI_API_KEY", "openai/gpt-4o"),
        "5": ("github", "GitHub Copilot", "GITHUB_TOKEN", "openai/gpt-4o"), # Litellm uses openai/gpt-4o for copilot usually
        "6": ("opencode", "OpenCode", "OPENCODE_API_KEY", "opencode/main"),
    }
    
    for k, v in providers.items():
        console.print(f"  [bold cyan]{k}.[/bold cyan] {v[1]}")
    
    choice = Prompt.ask("\n➤ Select provider", choices=list(providers.keys()), default="1")
    pid, p_name, p_env, p_model = providers[choice]
    
    # ── Auto Discovery ──────────────────────────────────────────────────
    found_key = None
    if pid == "google":
        found_key = find_gemini_key()
    elif pid == "anthropic":
        found_key = find_claude_key()
    elif pid == "openai":
        found_key = find_codex_key()
    elif pid == "github":
        found_key = find_github_token()
    elif pid == "opencode":
        found_key = find_opencode_key()
        
    final_key = None
    if found_key:
        masked = f"{found_key[:6]}...{found_key[-4:]}" if len(found_key) > 10 else "****"
        use_auto = Prompt.ask(
            f"\n[green]⚡ Found existing credentials from {p_name} CLI![/green]\n"
            f"Use found key ([cyan]{masked}[/cyan])?",
            choices=["y", "n"],
            default="y"
        )
        if use_auto == "y":
            final_key = found_key
            
    if not final_key:
        final_key = get_masked_input(f"[bold cyan]➤ Enter your {p_env}[/bold cyan]")
    
    if final_key:
        cfg.HOME.mkdir(parents=True, exist_ok=True)
        env_lines = [
            f"# VibeHack Configuration - Provider: {p_name}\n",
            f"VH_PROVIDER={pid}\n",
            f"VH_MODEL={p_model}\n",
            f"VH_API_KEY={final_key}\n",
            f"{p_env}={final_key}\n"
        ]
        
        with open(cfg.GLOBAL_ENV, "w") as f:
            f.writelines(env_lines)
            
        console.print(f"\n[bold green]✓ Configuration saved to {cfg.GLOBAL_ENV}[/bold green]")
        console.print(f"[dim]Restart VibeHack to apply changes.[/dim]\n")
        
        # Immediate update for current session
        cfg.API_KEY = final_key
        cfg.PROVIDER = pid
        cfg.MODEL = p_model
        return final_key
    else:
        console.print("[bold red]ERROR: API Key is required.[/bold red]")
        raise typer.Exit(code=1)

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
    if ctx.invoked_subcommand is not None:
        return  # Let the subcommand handle it

    if model:
        os.environ["VH_MODEL"] = model

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
