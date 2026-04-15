import sys
from vibehack import __version__
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.markdown import Markdown
from rich.tree import Tree

console = Console()
_CONN_CACHE = {"status": "Unknown", "last_check": 0}

def log_internal_error(error: Exception):
    """Write critical tracebacks to a local log file for debugging."""
    import traceback
    from datetime import datetime
    try:
        from vibehack.config import cfg
        log_file = cfg.HOME / "error.log"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[{now}] ERROR: {error}\n")
            f.write(traceback.format_exc())
            f.write("-" * 80 + "\n")
    except:
        pass

async def update_connectivity():
    """Background task to update connectivity status."""
    import requests
    import time
    import asyncio
    
    def _check():
        try:
            return requests.head("https://www.google.com", timeout=2)
        except:
            return None

    response = await asyncio.to_thread(_check)
    if response:
        _CONN_CACHE["status"] = "Ready" if response.status_code < 400 else "Offline"
    else:
        _CONN_CACHE["status"] = "Offline"
    _CONN_CACHE["last_check"] = time.time()

def get_masked_input(prompt_text: str) -> str:
    """Gets password input while printing '*' for each character. Works on Linux/UNIX."""
    import sys
    # If not a TTY, fallback to standard input
    if not sys.stdin.isatty():
        return Prompt.ask(prompt_text, password=True)

    import tty, termios
    console.print(prompt_text + " ", end="")
    sys.stdout.flush()
    
    buf = ""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            # Enter or Newline
            if ch in ('\n', '\r'):
                sys.stdout.write('\n\r')
                break
            # Backspace or Delete
            elif ch in ('\x7f', '\x08'):
                if len(buf) > 0:
                    buf = buf[:-1]
                    sys.stdout.write('\b \b')
            # Ctrl-C
            elif ch == '\x03':
                raise KeyboardInterrupt
            else:
                buf += ch
                sys.stdout.write('*')
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return buf

def display_banner(repl=None):
    """Redesigned banner with dynamic session status indicators."""
    from vibehack import __version__
    from vibehack.config import cfg
    import os
    
    # Construct a high-fidelity "VIBEHACK" ASCII logo
    logo_lines = [
        "[blue]█[/blue]     [blue]█[/blue]  [white]█[/white]  [red]█▀▀█[/red]  [yellow]█▀▀[/yellow]  [cyan]█  █[/cyan]  [magenta]█▀▀█[/magenta]  [green]█▀▀[/green]  [red]█ █[/red]",
        " [blue]█[/blue]   [blue]█[/blue]   [white]█[/white]  [red]█▀▀▄[/red]  [yellow]█▀▀[/yellow]  [cyan]█▀▀█[/cyan]  [magenta]█▄▄█[/magenta]  [green]█[/green]    [red]█▀▄[/red]",
        "  [blue]█[/blue] [blue]█[/blue]    [white]█[/white]  [red]█▄▄█[/red]  [yellow]█▄▄[/yellow]  [cyan]█  █[/cyan]  [magenta]█  █[/magenta]  [green]█▄▄[/green]  [red]█ █[/red]"
    ]
    
    logo_text = Text.from_markup("\n".join(logo_lines))

    # Vertical Separator Logic
    separator = Text.from_markup("[dim]|\n|\n|[/dim]")

    # ── Non-blocking Connectivity Test ──
    import time
    if time.time() - _CONN_CACHE["last_check"] > 60: # Check every 60s
        # If it's the first time or expired, we show cached or initiate (usually run in background)
        if _CONN_CACHE["status"] == "Unknown":
            llm_ready = "Checking..."
            llm_color = "yellow"
        else:
            llm_ready = f"{_CONN_CACHE['status']} (Cached)"
            llm_color = "green" if _CONN_CACHE["status"] == "Ready" else "red"
    else:
        llm_ready = _CONN_CACHE["status"]
        llm_color = "green" if llm_ready == "Ready" else "red"
    
    # Accurate token estimation from history
    hist_len = 0
    if repl and hasattr(repl, 'history'):
        hist_len = sum(len(m.get("content", "")) for m in repl.history) // 4
        
    # Get Mode & Status
    mode = getattr(repl, 'op_mode', 'AGENT').upper()
    # At the time of banner draw, we are usually waiting for input
    status = "LISTENING" if repl else "READY"
    
    # Tactical Info Block
    info_markup = (
        f" [dim]LLM:[/dim] [bold {llm_color}]{llm_ready}[/bold {llm_color}] ({hist_len} tokens)\n"
        f" [dim]STATUS:[/dim] [bold green]{status}...[/bold green]\n"
        f" [dim]MODE:[/dim] [bold cyan]{mode}[/bold cyan]"
    )
    info_text = Text.from_markup(info_markup)

    # Display side-by-side using a borderless table for guaranteed alignment
    table = Table.grid(padding=(0, 1))
    table.add_column("logo")
    table.add_column("sep")
    table.add_column("info")
    table.add_row(logo_text, separator, info_text)
    
def get_banner_text(repl=None):
    """Returns the banner as formatted text for prompt-toolkit."""
    from rich.console import Console
    from io import StringIO
    from prompt_toolkit.formatted_text import ANSI
    
    # We use a virtual console to capture rich output and convert to ANSI
    virt_console = Console(width=120, force_terminal=True, color_system="truecolor")
    with virt_console.capture() as capture:
        display_banner(repl)
    
    return ANSI(capture.get())

import os
import re
from datetime import datetime

def log_to_pane(repl, pane: str, message: str):
    """Helper to write to specific TUI buffers from anywhere. Strips Rich tags."""
    if not repl or not hasattr(repl, f"{pane}_buffer"):
        return
        
    buffer = getattr(repl, f"{pane}_buffer")
    
    # 1. Smarter Tag Stripping
    # Strip Rich tags ONLY if they look like formatting [bold], [red], [/]
    # Protect potential technical data like [127.0.0.1] or [DEBUG]
    keywords = r"bold|italic|underline|dim|blink|red|green|blue|yellow|magenta|cyan|white|grey|black|strike|reverse|link|#?[a-fA-F0-9]+|ansi[a-z0-9]+|class:[a-z.-]+"
    fmt_tags = rf"\[(?:/?(?:{keywords})(?:\s+(?:{keywords}))*|/)\s*\]"
    clean_msg = re.sub(fmt_tags, "", message, flags=re.IGNORECASE)
    
    # Strip HTML-style tags often used in prompt-toolkit HTML
    clean_msg = re.sub(r"<(?:ansicyan|ansired|ansiyellow|ansigreen|ansiblue|ansimagenta|ansigray|b|u|i|/b|/u|/i)>", "", clean_msg)
    
    # CRITICAL: Strip raw ANSI escape codes that corrupt prompt-toolkit layout engine
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_msg = ansi_escape.sub('', clean_msg)
    
    now = datetime.now()
    if pane == "logs":
        timestamp = now.strftime("%b %d %H:%M:%S")
        pid = os.getpid()
        tag = f"{timestamp} [{pid}]: "
    else:
        tag = ""
    
    # We append using buffer text to stay simple, but we avoid excessive resets
    new_text = tag + clean_msg
    if not new_text.endswith("\n"):
        new_text += "\n"
        
    buffer.text += new_text
    
    # 2. Buffer capping (Memory Protection)
    # Prevent infinite growth. If buffer > 1500 lines, keep only last 1000.
    lines = buffer.text.splitlines()
    if len(lines) > 1500:
        buffer.text = "\n".join(lines[-1000:]) + "\n"
        
    # Auto-scroll to bottom
    buffer.cursor_position = len(buffer.text)
    
    # Force UI redraw to ensure immediate visibility of updates
    # Throttled to prevent flickering from rapid-fire logs
    if repl and hasattr(repl, "app"):
        import time
        now_ts = time.time()
        last_ts = getattr(repl, "_last_invalidate", 0)
        if now_ts - last_ts > 0.1:  # Max 10 redraws per second
            repl._last_invalidate = now_ts
            repl.app.invalidate()

def pop_last_line_from_pane(repl, pane: str):
    """Removes the last line from a buffer. Useful for clearing 'Thinking...' status."""
    if not repl or not hasattr(repl, f"{pane}_buffer"):
        return
    buffer = getattr(repl, f"{pane}_pane" if hasattr(repl, f"{pane}_pane") else f"{pane}_buffer")
    lines = buffer.text.rstrip().splitlines()
    if lines:
        buffer.text = "\n".join(lines[:-1]) + "\n"
        buffer.cursor_position = len(buffer.text)

def display_notice(message: str, title: str = "SECURITY ADVISORY"):
    """Gemini-style yellow boxed notice. Mirrors the screenshot layout."""
    from rich.rule import Rule
    console.print(Rule(title, style="yellow"))
    console.print(Panel(message, border_style="yellow", expand=True, padding=(0, 1)))
    console.print("")

def display_thought(thought: str, repl=None):
    summary = thought.split('\n')[0][:120]
    if len(thought) > len(summary):
        summary += "..."
    msg = f"🧠 AI THOUGHT: {summary}"
    if repl:
        log_to_pane(repl, "history", msg)
    else:
        console.print(f"[dim]{msg}[/dim]")

def display_command(command: str, repl=None):
    if repl:
        log_to_pane(repl, "logs", f"⚙️ SUGGESTED: {command}")
    else:
        syntax = Syntax(command, "bash", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, title="⚙️ Suggested Command", border_style="yellow"))

def display_education(education: str, repl=None):
    if education:
        if repl:
            log_to_pane(repl, "history", f"📖 INTEL: {education}")
        else:
            console.print(Panel(education, title="📚 Education", border_style="green", subtitle="Dev-Safe Mode"))

def display_finding(severity: str, title: str, description: str, repl=None):
    color = "red" if severity.lower() in ["critical", "high"] else "yellow"
    msg = f"🚨 FINDING: [{severity.upper()}] {title} - {description}"
    if repl:
        log_to_pane(repl, "logs", msg)
    else:
        console.print(Panel(f"[bold]{title}[/bold]\n{description}", title=f"🚨 Finding: {severity.upper()}", border_style=color))

def display_knowledge_update(ports: list, technologies: list, endpoints: list, repl=None):
    """Prints a brief intelligence dashboard update."""
    lines = []
    if ports:
        lines.append(f"🔌 Ports: {', '.join(map(str, ports))}")
    if technologies:
        lines.append(f"⚙️ Tech: {', '.join(technologies)}")
    if endpoints:
        lines.append(f"🌐 Endpoints: {len(endpoints)} mapped")
        
    if lines:
        msg = "📡 INTEL UPDATE:\n" + "\n".join(lines)
        if repl:
            log_to_pane(repl, "logs", msg)
        else:
            console.print(Panel("\n".join(lines), title="[bold]📡 New Intel Gathered[/bold]", border_style="cyan"))

async def ask_approval(repl=None) -> str:
    """The Ultimate Firewall: HitL Approval Matrix. REPL-aware to avoid UI corruption."""
    from prompt_toolkit.shortcuts import button_dialog
    
    def _run_dialog():
        return button_dialog(
            title='⚠️ Security Gate: HitL Required',
            text='Execute this shell command?',
            buttons=[
                ('Yes', 'y'),
                ('No', 'n'),
                ('Auto-Allow', 'a'),
            ],
        ).run()

    if repl and hasattr(repl, 'app'):
        # Suspend the main TUI application to show the dialog cleanly
        from prompt_toolkit.application import run_in_terminal
        result = await run_in_terminal(_run_dialog)
        return result or "n"
    else:
        # Normal CLI fallback
        from prompt_toolkit.shortcuts import button_dialog
        result = await button_dialog(
            title='⚠️ Security Gate: HitL Required',
            text='Execute this shell command?',
            buttons=[
                ('Yes', 'y'),
                ('No', 'n'),
                ('Auto-Allow', 'a'),
            ],
        ).run_async()
        return result or "n"

def display_output(output: str, is_error: bool = False, repl=None):
    if repl:
        prefix = "🚨 " if is_error else "📝 "
        log_to_pane(repl, "output", f"{prefix}TERMINAL OUTPUT:\n{output}")
    else:
        style = "red" if is_error else "dim white"
        if output:
            console.print(Panel(output, title="📝 Terminal Output", border_style=style, expand=True))

def ask_waiver() -> bool:
    """Liability waiver for Unchained mode."""
    console.print("\n[bold red on white]  ⚠  UNCHAINED MODE DETECTED  ⚠  [/bold red on white]")
    console.print("[red]This mode DISABLES the Regex Blacklist guardrail entirely.[/red]")
    console.print("[red]The AI has unrestricted raw shell access. Risk of host compromise is HIGH.[/red]")
    console.print("[red]Run as non-root. You are solely responsible for all actions executed.[/red]")

    expected_text = "I ACCEPT THE RISKS OF HOST COMPROMISE"
    console.print(f"\nType this exact phrase to continue:\n[bold cyan]{expected_text}[/bold cyan]")

    user_input = Prompt.ask("Verify")
    if user_input.strip() == expected_text:
        console.print("[bold green]Waiver accepted. Safety locks disengaged.[/bold green]")
        return True
    else:
        console.print("[bold red]Waiver text mismatch. Session aborted.[/bold red]")
        return False

def display_session_info(target: str, mode: str, unchained: bool, session_id: str, tools_count: int):
    """Displays a startup summary panel."""
    from vibehack.config import cfg
    mode_label = f"[bold green]{mode.upper()}[/bold green]" if mode == "dev-safe" else f"[bold red]{mode.upper()}[/bold red]"
    unchained_label = "[bold red]UNCHAINED 🔓[/bold red]" if unchained else "[green]GUARDED 🔒[/green]"
    sandbox_label = "[bold blue]ACTIVE 📦[/bold blue]" if cfg.SANDBOX_ENABLED else "[dim]INACTIVE[/dim]"
    content = (
        f"[bold]Target:[/bold]     {target}\n"
        f"[bold]Mode:[/bold]       {mode_label}\n"
        f"[bold]Guardrails:[/bold] {unchained_label}\n"
        f"[bold]Sandbox:[/bold]    {sandbox_label}\n"
        f"[bold]Tools:[/bold]      {tools_count} available in PATH\n"
        f"[bold]Session:[/bold]    {session_id}"
    )
    console.print(Panel(content, title="[bold]🎯 Session Initialised[/bold]", border_style="cyan"))

def display_map(target: str, knowledge_state: dict):
    """
    God-Level Visualization: Attack Surface Map v3.0
    Visualises the entire mission hierarchy as a vibrant tree.
    """
    tree = Tree(f"🎯 [bold white on cyan] TARGET: {target} [/bold white on cyan]")
    
    # ── Services & Connectivity ──
    if knowledge_state.get("open_ports"):
        svc = tree.add("🔌 [bold cyan]Services & Ports[/bold cyan]")
        for port in sorted(knowledge_state["open_ports"]):
            svc.add(f"[cyan]Port {port}[/cyan] [dim]→ Listening[/dim]")
            
    # ── Application Stack ──
    if knowledge_state.get("technologies"):
        stack = tree.add("⚙️ [bold magenta]Technology Stack[/bold magenta]")
        for tech in sorted(knowledge_state["technologies"]):
            stack.add(f"[magenta]{tech.upper()}[/magenta]")
            
    # ── Discovery (Endpoints/URLs) ──
    if knowledge_state.get("endpoints"):
        surface = tree.add("🗺️ [bold green]Mapped Attack Surface[/bold green]")
        for ep in knowledge_state["endpoints"][:10]:
            surface.add(f"[green]{ep}[/green]")
        if len(knowledge_state["endpoints"]) > 10:
            surface.add(f"[dim]... {len(knowledge_state['endpoints']) - 10} more endpoints[/dim]")
            
    # ── Critical Findings & Intel ──
    intel_data = knowledge_state.get("notes") or []
    credentials = knowledge_state.get("credentials") or []
    
    if intel_data or credentials:
        intel = tree.add("🔥 [bold red]Compromise & Intel[/bold red]")
        
        if credentials:
            cred_node = intel.add(f"🔑 [bold yellow]{len(credentials)} Credentials Found[/bold yellow]")
            for c in credentials[:3]:
                cred_node.add(f"[yellow]{c}[/yellow]")

        for note in intel_data[-8:]:
            # Style based on keywords
            style = "dim"
            if "Finding [" in note: style = "bold red"
            elif "Finding recorded" in note: style = "bold yellow"
            intel.add(f"[{style}]{note}[/{style}]")

    console.print("")
    console.print(Panel(tree, border_style="cyan", title="[bold white]📡 REAL-TIME ATTACK MAP[/bold white]", expand=False))
    console.print("")

def display_mission(goals: list, repl=None):
    """Displays the active mission objectives."""
    if not goals:
        return
    
    msg = "🏁 MISSION PLAN:\n" + "\n".join([f"  - {g}" for g in goals])
    if repl:
        log_to_pane(repl, "logs", msg)
    else:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Objective", style="dim")
        table.add_column("Status", justify="right")
        
        for goal in goals:
            if "[DONE]" in goal.upper():
                status = "[bold green]COMPLETE[/bold green]"
                color = "dim green"
            else:
                status = "[bold yellow]RUNNING[/bold yellow]"
                color = "white"
                
            clean_goal = goal.replace("[DONE]", "").replace("[IN_PROGRESS]", "").strip()
            table.add_row(f"[{color}]{clean_goal}[/{color}]", status)
            
        console.print(Panel(table, title="🏁 Active Mission Plan", border_style="magenta", expand=False))

def display_ask_response(raw_resp: str, repl=None):
    """Render the AI response beautifully, handling both JSON and Markdown."""
    import json
    
    # Try parsing as JSON first
    try:
        clean_json = raw_resp.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        
        data = json.loads(clean_json.strip())
        thought = data.get("thought", "")
        education = data.get("education", "")
        command = data.get("raw_command", "")
        answer = data.get("answer", "") or thought # Fill answer if missing
        
        if repl:
            if thought: log_to_pane(repl, "history", f"🧠 THOUGHT: {thought}")
            if education: log_to_pane(repl, "history", f"📖 INTEL: {education}")
            if command: log_to_pane(repl, "logs", f"⚙️ CMD: {command}")
            log_to_pane(repl, "history", f"📡 RESPONSE: {answer}")
        else:
            if thought:
                console.print(Panel(Markdown(thought), title="🤖 AI Thought", border_style="magenta"))
            if education:
                display_education(education)
            if command:
                display_command(command)
            
    except (json.JSONDecodeError, TypeError, AttributeError):
        if repl:
            log_to_pane(repl, "history", f"📡 RESPONSE: {raw_resp}")
        else:
            console.print(Panel(Markdown(raw_resp), title="🤖 VibeHack Answer", border_style="cyan"))
