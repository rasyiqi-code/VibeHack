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

def display_banner():
    """Modern, prominent full-width header for VibeHack."""
    from vibehack import __version__
    
    # Gemini-style logo sequence
    logo = "[bold #0000ff]❱[/bold #0000ff][bold #00ffff]❱[/bold #00ffff][bold #00ff00]❱[/bold #00ff00]"
    
    header = Table.grid(expand=True)
    header.add_column(style="bold white")
    header.add_column(justify="right", style="dim")
    
    header.add_row(
        f"{logo}  [bold white]VibeHack[/bold white] [cyan]v{__version__}[/cyan]",
        "The Autonomous Weapon [green]●[/green] Ready"
    )
    
    console.print(Panel(
        header, 
        border_style="#1e1e1e", 
        expand=True, 
        padding=(0, 1)
    ))

def display_notice(message: str, title: str = "NOTICE"):
    """Gemini-style yellow boxed notice."""
    console.print(Panel(
        message,
        title=f"[bold yellow]{title}[/bold yellow]",
        border_style="yellow",
        expand=True,
        padding=(0, 1)
    ))

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
    """Visualises the attack surface as a Tree."""
    tree = Tree(f"🎯 [bold cyan]Target: {target}[/bold cyan]")
    
    # ── Services Branch ──
    if knowledge_state.get("open_ports"):
        svc = tree.add("🔌 [bold white]Services (Open Ports)[/bold white]")
        for port in knowledge_state["open_ports"]:
            svc.add(f"[cyan]Port {port}[/cyan]")
            
    # ── Stack Branch ──
    if knowledge_state.get("technologies"):
        stack = tree.add("⚙️ [bold magenta]Technology Stack[/bold magenta]")
        for tech in knowledge_state["technologies"]:
            stack.add(f"[magenta]{tech}[/magenta]")
            
    # ── Surface Branch ──
    if knowledge_state.get("endpoints"):
        surface = tree.add("🗺️ [bold green]Mapped Endpoints[/bold green]")
        for ep in knowledge_state["endpoints"][:15]:
            surface.add(f"[green]{ep}[/green]")
        if len(knowledge_state["endpoints"]) > 15:
            surface.add("[dim]... and more[/dim]")
            
    # ── Intel Branch ──
    if knowledge_state.get("notes") or knowledge_state.get("credentials") or knowledge_state.get("tested_surfaces"):
        intel = tree.add("🔑 [bold yellow]Intel & Findings[/bold yellow]")
        if knowledge_state.get("credentials"):
            intel.add(f"[yellow]{len(knowledge_state['credentials'])} credentials found[/yellow]")
        if knowledge_state.get("tested_surfaces"):
            intel.add(f"[dim]Tested: {', '.join(knowledge_state['tested_surfaces'])}[/dim]")
        for note in knowledge_state.get("notes", [])[-5:]:
            intel.add(f"[dim]{note}[/dim]")

    console.print(Panel(tree, border_style="dim", expand=False))

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
