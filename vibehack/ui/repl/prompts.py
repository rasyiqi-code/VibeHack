"""
vibehack/ui/repl/prompts.py — TUI components for VibeHack REPL.
Handles prompt-toolkit session setup, completers, and styles.
"""
from typing import List
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from vibehack.config import cfg
from vibehack.core.repl.commands import SLASH_COMMANDS

class SlashCommandCompleter(Completer):
    """Autocomplete for slash commands with descriptions (Gemini style)."""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # /install <tool> autocomplete
        if text.startswith("/install "):
            prefix = text[9:].lower()
            from vibehack.toolkit.provisioner import DOWNLOADABLE_TOOLS
            for tool in DOWNLOADABLE_TOOLS:
                if tool.startswith(prefix):
                    yield Completion(tool, start_position=-len(prefix))
        
        # Slash command autocomplete with descriptions
        elif text.startswith("/"):
            word = text.lower()
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(word):
                    # Gemini style: Command on left, Description on right
                    # Padding meta to force full-width display in the floating menu
                    try:
                        import os
                        width = os.get_terminal_size().columns
                    except OSError:
                        width = 80
                        
                    # Calculate padding needed for full-width feeling
                    # cmd is roughly 15 chars, desc is rest.
                    meta_padding = " " * (width - len(cmd) - len(desc) - 5)
                    full_meta = desc + meta_padding
                    
                    yield Completion(cmd, start_position=-len(text), display_meta=full_meta)

def get_input_hint(repl):
    """A tactical separator for the hacker style."""
    from rich.text import Text
    import os
    
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 100

    # Professional minimalist separator
    label = " INPUT "
    remaining = width - len(label) - 4
    left = "─" * (remaining // 2)
    right = "─" * (remaining - (remaining // 2))
    
    hint = Text(f"{left}[{label}]{right}", style="#444444")
    return hint

def get_repl_style():
    """Gemini CLI inspired styling with dark input area."""
    return Style.from_dict({
        'bottom-toolbar': '#00ff00 bg:#000000',
        'top-toolbar':    '#00ffff bg:#000000',
        'prompt':         '#00ffff bold',
        'prompt-area':    'bg:#000000',
        'completion-menu': 'bg:#111111 #00ff00',
        'completion-menu.completion': 'bg:#111111 #00ff00',
        'completion-menu.completion.current': 'bg:#00ffff #000000',
        'completion-menu.meta.completion': 'bg:#111111 #00aaaa',
        'completion-menu.meta.completion.current': 'bg:#00ffff #000000',
        'logo':           '#00ff00 bold',
        'version':        '#ffd700',
        'auth':           '#ffd700',
        'sandbox-safe':   '#00ff00',
        'sandbox-warn':   '#ff0000 bold blink',
    })

def get_top_toolbar(repl):
    """Tactical header for hacker style."""
    from vibehack import __version__
    logo = HTML('<logo><b>[ VIBEHACK CORE ]</b></logo>')
    return HTML(
        f'{logo} <version>v{__version__}</version> '
        f'| <auth>LINK_ESTABLISHED</auth> '
        f'| CPU: [OK] | MEM: [OK] | SEC_OPS: [ACTIVE]'
    )

def get_bottom_toolbar(repl):
    """Refined Dashboard Toolbar with Version and Model info across the bottom."""
    from vibehack import __version__
    import os
    
    # Left Side: Status & Intelligence
    target = (repl.target[:25] + '...') if repl.target and len(repl.target) > 25 else (repl.target or "NO_TARGET")
    findings = len(repl.key_findings)
    status_icon = "🔓" if getattr(repl, 'unchained', False) else "🔒"
    
    # Brain Meta
    model = repl.handler.model if hasattr(repl, 'handler') else "???"
    short_model = model.split("/")[-1] # e.g. gemini-1.5-flash
    
    # Session Metadata
    session_id = getattr(repl, 'session_id', '???')
    persona = getattr(repl, 'persona', 'dev-safe')
    
    left_part = f" [v{__version__}] | {status_icon} {target} | FINDINGS: {findings} | BRAIN: {short_model} | MISSION: {persona.upper()} "
    right_part = f" SESSION: {session_id} "
    
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 100
        
    padding_count = width - len(left_part) - len(right_part) - 2
    padding = " " * max(0, padding_count)
    
    return HTML(f"<b><ansiyellow>{left_part}{padding}{right_part}</ansiyellow></b>")
