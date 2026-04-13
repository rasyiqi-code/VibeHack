"""
vibehack/repl.py — Interactive REPL Orchestrator for VibeHack.
Modularized in v2.6.45 to separate UI, Logic, and Commands.
"""
import asyncio
import os
import re
import sys
from datetime import datetime
from typing import List, Dict, Optional

from prompt_toolkit import Application, PromptSession
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout import Layout, HSplit, Window, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.containers import FloatContainer, Float, WindowAlign
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.widgets import Frame
from rich.console import Console

from vibehack.config import cfg
from vibehack.llm.provider import UniversalHandler, Finding
from vibehack.agent.prompts import get_system_prompt
from vibehack.agent.knowledge import KnowledgeState
from vibehack.memory.db import init_memory, get_memory_stats
from vibehack.memory.ingestion import ingest_session
from vibehack.session.persistence import save_session, generate_session_id
from vibehack.toolkit.manager import get_toolkit_env
from vibehack.toolkit.discovery import discover_tools, clear_discovery_cache
from vibehack.ui.tui import display_banner, display_notice

# Modular Imports
from vibehack.core.repl.commands import handle_slash_command
from vibehack.core.repl.logic import process_llm_turn
from vibehack.ui.repl.prompts import (
    SlashCommandCompleter, get_repl_style, get_bottom_toolbar, 
    get_top_toolbar, get_input_hint
)
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.layout.containers import FloatContainer, Float
from prompt_toolkit.layout.menus import CompletionsMenu

console = Console()
URL_PATTERN = re.compile(r"(https?://[^\s]+|(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?|localhost(?::\d+)?)", re.IGNORECASE)

class VibehackREPL:
    def __init__(self, target=None, op_mode="agent", persona="dev-safe", unchained=False, no_memory=False, api_key=""):
        self.target = target
        self.op_mode = op_mode
        self.persona = persona
        self.unchained = unchained
        self.no_memory = no_memory
        self.api_key = api_key
        self.handler = UniversalHandler(api_key, model=cfg.MODEL)
        self.history: List[Dict[str, str]] = []
        self.key_findings: List[Finding] = []
        self.knowledge = KnowledgeState()
        self.auto_allow = False
        self.session_id = generate_session_id()
        self.env = get_toolkit_env()
        self._system_built = False
        self._available_tools: List[str] = []
        self.interrupted = False
        
        # ── Interruption Hook (ESC) ──────────────────────────────────────
        try:
            from pynput import keyboard
            def on_press(key):
                if key == keyboard.Key.esc:
                    self.interrupted = True
            
            self._kb_listener = keyboard.Listener(on_press=on_press)
            self._kb_listener.start()
        except:
            self._kb_listener = None

        # ── TUI Setup ─────────────────────────────────────────────────────
        self.completer = SlashCommandCompleter()
        self.style = get_repl_style()
        
        # Buffers for history and input
        self.history_buffer = Buffer(read_only=True)
        self.input_buffer = Buffer(completer=self.completer, history=FileHistory(os.path.join(cfg.HOME, ".history")))
        
        self.kb = KeyBindings()
        
        @self.kb.add('c-c')
        def _(event):
            event.app.exit()

        @Condition
        def is_not_completing():
            return not self.input_buffer.complete_state

        @self.kb.add('enter', filter=is_not_completing)
        def _(event):
            # Process input and clear buffer
            text = self.input_buffer.text
            self.input_buffer.reset()
            # This will be handled in the main loop logic via a flag or queue
            # but for simplicity in Application.run_async, we can trigger a task
            pass

        # Full-Screen Layout with Sticky Components
        self.layout = Layout(
            HSplit([
                # Sticky Top Bar
                Window(content=FormattedTextControl(lambda: get_top_toolbar(self)), height=1, style='class:top-toolbar'),
                # Scrollable History Window
                Window(content=BufferControl(buffer=self.history_buffer), wrap_lines=True),
                # Input Area (Full width)
                FloatContainer(
                    content=HSplit([
                        # Dark separator hint line
                        Window(content=FormattedTextControl(lambda: get_input_hint(self)), height=1),
                        # Prompt line
                        Window(
                            content=BufferControl(
                                buffer=self.input_buffer,
                                input_processors=[BeforeInput(HTML('<prompt><b> > </b></prompt>'))]
                            ),
                            height=1,
                            style='class:prompt'
                        ),
                    ]),
                    floats=[
                        Float(
                            content=Window(
                                content=CompletionsMenu(max_height=12),
                                style='completion-menu',
                                dont_extend_width=False, # Force full width
                            ),
                            left=0,
                            right=0,
                            bottom=1
                        )
                    ]
                ),
                # Sticky Bottom Bar
                Window(content=FormattedTextControl(lambda: get_bottom_toolbar(self)), height=1, style='class:bottom-toolbar'),
            ])
        )
        
        # Initialize Application for full-screen management
        self.app = Application(
            layout=self.layout,
            style=self.style,
            full_screen=True,
            key_bindings=self.kb,
            mouse_support=True
        )
        
        self.session = PromptSession(
            history=FileHistory(os.path.join(cfg.HOME, ".history")),
            completer=self.completer,
            complete_while_typing=True,
            style=self.style,
            bottom_toolbar=lambda: get_bottom_toolbar(self)
        )

    def _check_sudo(self):
        if os.geteuid() == 0:
            console.print("[bold red on white]  ⚠  ROOT — AI hallucinations can destroy your OS  ⚠  [/bold red on white]")

    def _discover_tools(self):
        self._available_tools = discover_tools()

    def _rebuild_system_prompt(self):
        system_prompt = get_system_prompt(
            target=self.target or "not yet set",
            persona=self.persona,
            unchained=self.unchained,
            tools_available=self._available_tools,
            tech_hint=next(iter(self.knowledge.technologies), "web"),
            existing_findings=self.key_findings,
            knowledge_state=self.knowledge.to_dict() if not self.knowledge.is_empty() else None,
            sandbox=cfg.SANDBOX_ENABLED
        )
        if self.history and self.history[0]["role"] == "system":
            self.history[0]["content"] = system_prompt
        else:
            self.history.insert(0, {"role": "system", "content": system_prompt})
        self._system_built = True

    def _persist(self):
        save_session(self.session_id, {
            "session_id": self.session_id,
            "target": self.target or "",
            "op_mode": self.op_mode,
            "persona": self.persona,
            "unchained": self.unchained,
            "history": self.history,
            "findings": [f.model_dump() for f in self.key_findings],
            "knowledge": self.knowledge.to_dict(),
            "auto_allow": self.auto_allow,
            "saved_at": datetime.now().isoformat(),
        })

    def _trim_history(self):
        limit = cfg.MAX_TURN_MEMORY * 2
        if len(self.history) > limit + 1:
            self.history = [self.history[0]] + self.history[-limit:]

    def _extract_target_from_text(self, text: str) -> Optional[str]:
        matches = URL_PATTERN.findall(text)
        for m in matches:
            if not m.startswith("http"): m = f"http://{m}"
            return m
        return None

    async def run(self):
        # ── Professional TUI Initialization ───────────────────────────────
        # Set terminal window title
        sys.stdout.write("\x1b]2;VibeHack [SEC-AGENT]\x07")
        sys.stdout.flush()
        
        # Ensure we start with a small top margin for better readability
        os.system('clear' if os.name == 'posix' else 'cls')
        print("") # Top margin
        
        display_banner()
        self._check_sudo()
        self._discover_tools()
        if self.no_memory is False: init_memory()
        self._rebuild_system_prompt()

        # Display start-up notice (Professional style)
        display_notice(
            "VibeHack is an autonomous security agent. All activities are logged to "
            "~/.vibehack/sessions for audit and cross-session learning.",
            title="SECURITY ADVISORY"
        )

        # ── Prompt Setup with Sticky Components ───────────────────────────
        # Note: We use the bottom_toolbar and a custom prompt style to 
        # achieve the modern AI CLI look.
        
        while True:
            try:
                # ── Print Input Hint (Modern UI) ──────────────────────────
                # We use a separator bar without text as requested
                console.print(get_input_hint(self))
                
                # Calculate terminal width
                try:
                    width = os.get_terminal_size().columns
                except OSError:
                    width = 80

                # Hacker Style Prompt: Sharp and glowing neons with Gold placeholder
                user_input = await self.session.prompt_async(
                    HTML('<b><ansiyellow>vibe</ansiyellow><ansigray>@</ansigray><ansicyan>hack</ansicyan><ansigray>:</ansigray><ansiblue>~</ansiblue><ansigray>$</ansigray> </b>'),
                    placeholder=HTML('<ansiyellow>awaiting_instruction...</ansiyellow>'),
                    bottom_toolbar=lambda: get_bottom_toolbar(self),
                    style=self.style
                )
                if not user_input.strip(): continue

                if user_input.startswith("/"):
                    result = handle_slash_command(self, user_input)
                    if result is False: break
                    if isinstance(result, tuple) and result[0] == "__install__":
                        from vibehack.toolkit.provisioner import download_tool
                        if await download_tool(result[1]):
                            self._discover_tools()
                            self._rebuild_system_prompt()
                    continue

                await process_llm_turn(self, user_input)

            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                console.print(f"[bold red]Unexpected error:[/bold red] {e}")
                break

        self._persist()
        if hasattr(self, '_kb_listener') and self._kb_listener:
            try:
                self._kb_listener.stop()
            except:
                pass
        if not self.no_memory and len(self.history) > 2:
            ingest_session(self.target or "unknown", self.history, self.key_findings)
        console.print(f"\n[bold green]Session {self.session_id} saved.[/bold green]\n")
