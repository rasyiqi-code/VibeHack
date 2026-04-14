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

import os
import re
import psutil
from vibehack import __version__

def get_repl_style():
    """Gold Hacker Style: Transparent and high-contrast."""
    return Style.from_dict({
        'bottom-toolbar': 'noinherit #ffd700 bg:default bold',
        'top-toolbar':    'noinherit #ffd700 bg:default bold',
        'prompt':         '#ffd700 bold',
        'prompt-area':    '',
        'completion-menu': 'bg:default #00ff00',
        'completion-menu.completion': 'bg:default #00ff00',
        'completion-menu.completion.current': 'bg:#ffd700 #000000 bold',
        'completion-menu.meta.completion': 'bg:default #00aaaa',
        'completion-menu.meta.completion.current': 'bg:#ffd700 #000000',
        'logo':           '#ffd700 bold',
        'version':        '#ffffff dim',
        'auth':           '#00ff00',
        'sandbox-safe':   '#00ff00',
        'sandbox-warn':   '#ff0000 bold blink',
        'status-thinking': 'noinherit #ff0000 bg:default bold blink',
        'status-listening': 'noinherit #ffd700 bg:default bold',
        
        # Frame & Border Styles (GOLD Theme)
        'history-frame':   '#00ff00',
        'output-frame':    '#00ff00',
        'logs-frame':      '#00ff00 dim',
        'frame.border':    '#ffd700',
        'frame.label':     '#ffd700 bold',
    })

def get_top_toolbar(repl):
    """Tactical header with real-time system telemetry."""
    # Real Telemetry with fallback
    try:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        right = f' CPU: [{cpu}%] | MEM: [{mem}%] | SEC_OPS: [ACTIVE] '
    except:
        right = ' CPU: [OK] | MEM: [OK] | SEC_OPS: [ACTIVE] '
    
    left_raw = f' [ VIBEHACK CORE ] v{__version__} | LINK_ESTABLISHED '
    left_styled = f' <logo><b>[ VIBEHACK CORE ]</b></logo> <version>v{__version__}</version> | <auth>LINK_ESTABLISHED</auth> '
    
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 100
        
    padding = width - len(left_raw) - len(right)
    if padding < 0: padding = 1
    
    return HTML(left_styled + (" " * padding) + right)

def get_bottom_toolbar(repl):
    """Balanced Mission Control bar with left and right alignment."""
    # Mission Context
    target = getattr(repl, 'target', 'NO_TARGET') or 'NO_TARGET'
    findings = len(getattr(repl, 'key_findings', []))
    
    # Simple token estimation
    history = getattr(repl, 'history', [])
    tokens = sum(len(m.get("content", "")) for m in history) // 4
    
    model_name = "AI"
    if hasattr(repl, 'handler') and hasattr(repl.handler, 'model'):
        model_name = repl.handler.model.split("/")[-1]
        
    session_id = str(getattr(repl, 'session_id', 'UNKNOWN'))
    
    # Status indicators
    status = getattr(repl, 'status', 'LISTENING').upper()
    status_icon = "🧠" if status == "THINKING" else "🔒"
    status_style = "status-thinking" if status == "THINKING" else "status-listening"
    
    left_styled = (
        f' [v{__version__}] | {status_icon} {target} | TOKENS: {tokens} | '
        f'AGENT: <{status_style}>{status}</{status_style}> | '
        f'FINDINGS: {findings} | BRAIN: {model_name} '
    )
    left_raw = (
        f' [v{__version__}] | {status_icon} {target} | TOKENS: {tokens} | '
        f'AGENT: {status} | FINDINGS: {findings} | BRAIN: {model_name} '
    )
    right = f' SESSION: {session_id} '
    
    try:
        width = os.get_terminal_size().columns
    except OSError:
        width = 100
        
    padding = width - len(left_raw) - len(right)
    if padding < 0: padding = 1
    
    return HTML(left_styled + (" " * padding) + right)
