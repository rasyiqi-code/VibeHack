"""
vibehack/ui/repl/prompts.py — TUI components for VibeHack REPL.
Handles prompt-toolkit session setup, completers, and styles.
"""
from typing import List
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from vibehack.config import cfg

class SlashCommandCompleter(Completer):
    """Autocomplete for slash commands and tool names."""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # /install <tool> autocomplete
        if text.startswith("/install "):
            prefix = text[9:].lower()
            from vibehack.toolkit.provisioner import DOWNLOADABLE_TOOLS
            for tool in DOWNLOADABLE_TOOLS:
                if tool.startswith(prefix):
                    yield Completion(tool, start_position=-len(prefix))
        
        # Slash command autocomplete
        elif text.startswith("/"):
            from vibehack.core.repl.commands import SLASH_COMMANDS
            word = text.lower()
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(text), display_meta=desc)

def get_repl_style():
    """Default styling for prompt-toolkit with modern Gold accents."""
    return Style.from_dict({
        # Layout components
        'bottom-toolbar': '#ffd700 bg:#132e35',
        'top-toolbar':    '#ffd700', # No background for header
        'prompt':         '#00ffff bg:#132e35 bold', 
        'placeholder':    '#666666 bg:#132e35',

        # Completion Menu (Modern multi-column look)
        'completion-menu':                    'bg:#132e35 #ffffff',
        'completion-menu.selected':           'bg:#a9bf4d #000000 bold',
        'completion-menu.meta':               '#888888 bg:#132e35',
        'completion-menu.selected.meta':      '#000000 bg:#a9bf4d',
        'completion-menu.multi-column-meta':  'bg:#132e35 #888888',

        # Branding & Accents
        'logo':           '#00ffff bold',
        'version':        '#bbbbbb',
        'auth':           '#ffd700',
        'path':           '#00ffff',
        'sandbox-safe':   'bg:#00ff00 #000000 bold',
        'sandbox-warn':   'bg:#ff0000 #ffffff bold',
        'model-hint':     '#ffd700',
    })

def get_top_toolbar(repl):
    """Sticky header for the top of the terminal."""
    from vibehack import __version__
    provider = repl.handler.provider.upper() if hasattr(repl, 'handler') else "UNKNOWN"
    
    # Simple plain-text arrows to avoid raw HTML leak on some terminals
    logo = "❱❱❱"
    
    return HTML(
        f'<b>{logo}</b> <b>VibeHack</b> <version>v{__version__}</version> '
        f'| <auth>Signed in via {provider}</auth> '
        f'| <model-hint>Mission: Autonomous Weapon /audit <ansigray>....</ansigray></model-hint>'
    )

def get_bottom_toolbar(repl):
    """Informative metadata bar shown at the bottom of the terminal."""
    import os
    cwd = os.getcwd().replace(os.path.expanduser("~"), "~")
    
    target = (repl.target[:30] + '...') if repl.target and len(repl.target) > 30 else (repl.target or "no target")
    findings = len(repl.key_findings)
    unchained = "UNCHAINED 🔓" if repl.unchained else "GUARDED 🔒"
    sandbox_status = '<sandbox-safe>ACTIVE 📦</sandbox-safe>' if getattr(cfg, 'SANDBOX_ENABLED', False) else '<sandbox-warn>no sandbox</sandbox-warn>'
    
    return HTML(
        f' <b>VibeHack</b> | Target: <ansicyan>{target}</ansicyan> | '
        f'Findings: <b>{findings}f</b> | {unchained} | '
        f'Sandbox: {sandbox_status} | Mode: {repl.persona}'
    )
