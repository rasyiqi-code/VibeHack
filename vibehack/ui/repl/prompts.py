"""
vibehack/ui/repl/prompts.py — TUI components for VibeHack REPL.
Handles prompt-toolkit session setup, completers, and styles.
"""
from typing import List
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
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
    """Default styling for prompt-toolkit."""
    return Style.from_dict({
        'bottom-toolbar': '#aaaaaa bg:#222222',
        'prompt': 'bold #00ff00',
    })

def get_bottom_toolbar(repl):
    """Dynamic metadata bar shown at the bottom of the terminal."""
    target = repl.target or "no target"
    mode = repl.persona
    unchained = "UNCHAINED 🔓" if repl.unchained else "GUARDED 🔒"
    findings = len(repl.key_findings)
    
    return HTML(
        f' <b>VibeHack</b> | Target: <ansicyan>{target}</ansicyan> | '
        f'Mode: {mode} | {unchained} | Findings: <b>{findings}f</b>'
    )
