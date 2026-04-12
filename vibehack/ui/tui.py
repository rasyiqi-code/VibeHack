import sys
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.markdown import Markdown

console = Console()

def get_masked_input(prompt_text: str) -> str:
    """Gets password input while printing '*' for each character. Works on Linux/UNIX."""
    import sys
    # If not a TTY, fallback to standard input
    if not sys.stdin.isatty():
        return Prompt.ask(prompt_text, password=True)

    import tty, termios
    sys.stdout.write(prompt_text + " ")
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
    banner = """
╔══════════════════════════════════════════╗
║  🔥 [bold red]Vibe_Hack v2.2[/bold red]                      ║  
║  [dim]The Autonomous Weapon Update[/dim]             ║
╚══════════════════════════════════════════╝
    [dim]Type [cyan]/help[/cyan] in REPL to see Slash Commands[/dim]
"""
    console.print(banner)

def display_thought(thought: str):
    md = Markdown(thought)
    console.print(Panel(md, title="🤖 AI Thought", border_style="blue"))

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

def ask_approval() -> str:
    """The Ultimate Firewall: HitL Approval Matrix"""
    choice = Prompt.ask(
        "❓ Execute? [bold cyan][y][/bold cyan]es / [bold red][n][/bold red]o / [bold yellow][a][/bold yellow]llow session",
        choices=["y", "n", "a"],
        default="n"
    )
    return choice

def display_output(output: str, is_error: bool = False):
    style = "red" if is_error else "dim white"
    if output:
        console.print(Panel(output, title="📝 Terminal Output", border_style=style))

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
