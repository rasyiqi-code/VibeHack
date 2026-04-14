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

    # Check LLM Readiness & Tokens
    from vibehack.config import cfg
    llm_ready = "Ready" if cfg.API_KEY else "Not Ready"
    llm_color = "green" if cfg.API_KEY else "red"
    
    # Estimate tokens from history
    hist_len = 0
    if repl and hasattr(repl, 'history'):
        hist_len = sum(len(m["content"]) for m in repl.history) // 4
        
    # Get Mode & Status
    mode = getattr(repl, 'op_mode', 'AGENT').upper()
    status = "RUNNING" if repl else "READY"
    
    # Tactical Info Block
    provider = os.getenv("VH_PROVIDER", "Google")
    
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
    
    console.print(table)
    console.print("")

def display_notice(message: str, title: str = "SECURITY ADVISORY"):
    """Gemini-style yellow boxed notice. Mirrors the screenshot layout."""
    from rich.rule import Rule
    console.print(Rule(title, style="yellow"))
    console.print(Panel(message, border_style="yellow", expand=True, padding=(0, 1)))
    console.print("")

def display_thought(thought: str):
    summary = thought.split('\n')[0][:120]
    if len(thought) > len(summary):
        summary += "..."
    console.print(f"[dim]🤖 AI Thought: {summary}[/dim]")

def display_command(command: str):
    syntax = Syntax(command, "bash", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="⚙️ Suggested Command", border_style="yellow"))

def display_education(education: str):
    if education:
        console.print(Panel(education, title="📚 Education", border_style="green", subtitle="Dev-Safe Mode"))

def display_finding(severity: str, title: str, description: str):
    color = "red" if severity.lower() in ["critical", "high"] else "yellow"
    console.print(Panel(f"[bold]{title}[/bold]\n{description}", title=f"🚨 Finding: {severity.upper()}", border_style=color))

def display_knowledge_update(ports: list, technologies: list, endpoints: list):
    """Prints a brief intelligence dashboard update."""
    lines = []
    if ports:
        lines.append(f"[bold cyan]Ports:[/bold cyan] {', '.join(map(str, ports))}")
    if technologies:
        lines.append(f"[bold magenta]Tech:[/bold magenta] {', '.join(technologies)}")
    if endpoints:
        lines.append(f"[bold green]Endpoints:[/bold green] {len(endpoints)} mapped")
        
    if lines:
        console.print(Panel("\n".join(lines), title="[bold]📡 New Intel Gathered[/bold]", border_style="cyan"))

async def ask_approval() -> str:
    """The Ultimate Firewall: HitL Approval Matrix"""
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

def display_output(output: str, is_error: bool = False):
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

def display_mission(goals: list):
    """Displays the active mission objectives."""
    if not goals:
        return
    
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

def display_ask_response(raw_resp: str):
    """Render the AI response beautifully, handling both JSON and Markdown."""
    import json
    
    # Try parsing as JSON first
    try:
        # Clean potential markdown code blocks if AI wrapped JSON in ```json
        clean_json = raw_resp.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        
        data = json.loads(clean_json.strip())
        thought = data.get("thought", "")
        education = data.get("education", "")
        command = data.get("raw_command", "")
        
        if thought:
            console.print(Panel(Markdown(thought), title="🤖 AI Thought", border_style="magenta"))
        
        if education:
            display_education(education)
            
        if command:
            display_command(command)
            
    except (json.JSONDecodeError, TypeError, AttributeError):
        # Fallback to pure Markdown
        console.print(Panel(Markdown(raw_resp), title="🤖 VibeHack Answer", border_style="cyan"))
