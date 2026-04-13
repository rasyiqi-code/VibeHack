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
            word = text.lower()
            for cmd in SLASH_COMMANDS:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(text))

def get_repl_style():
    """Default styling for prompt-toolkit with modern Gold accents."""
    return Style.from_dict({
        'bottom-toolbar': '#ffd700 bg:#1e1e1e',
        'top-toolbar':    '#ffd700 bg:#1e1e1e',
        'prompt':         '#00ffff bold',
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
    
    # Gemini-style multi-colored arrow logo
    logo = HTML('<ansiblue><b>❱</b></ansiblue><ansicyan><b>❱</b></ansicyan><ansigreen><b>❱</b></ansigreen>')
    
    return HTML(
        f'{logo} <b>VibeHack</b> <version>v{__version__}</version> '
        f'| <auth>Signed in via {provider}</auth> '
        f'| <model-hint>Mission: Autonomous Weapon /audit</model-hint>'
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
