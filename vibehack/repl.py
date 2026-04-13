"""
vibehack/repl.py — Interactive REPL Orchestrator for VibeHack.
Modularized in v2.6.45 to separate UI, Logic, and Commands.
"""
import asyncio
import os
import re
from datetime import datetime
from typing import List, Dict, Optional

from prompt_toolkit import Application, PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import Layout, HSplit, Window, ScrollablePane
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.processors import BeforeInput, Placeholder
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML, ANSI
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
from vibehack.ui.repl.prompts import SlashCommandCompleter, get_repl_style, get_bottom_toolbar, get_top_toolbar

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

        # Output Capture Setup
        from io import StringIO
        self.log_io = StringIO()
        self.target_console = Console(file=self.log_io, force_terminal=True, width=120, color_system="truecolor")

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
            text = self.input_buffer.text.strip()
            if not text:
                return
            
            self.input_buffer.reset()
            # Append human message to history UI
            self.log(HTML(f"<ansicyan><b>you:</b></ansicyan> {text}"))
            
            # Start processing in background
            asyncio.create_task(self._handle_input(text))

    async def _handle_input(self, text: str):
        if text.startswith("/"):
            result = handle_slash_command(self, text)
            if result is False:
                self.app.exit()
            elif isinstance(result, tuple) and result[0] == "__install__":
                from vibehack.toolkit.provisioner import download_tool
                if await download_tool(result[1]):
                    clear_discovery_cache()
                    self._discover_tools()
                    self._rebuild_system_prompt()
            return

        try:
            await process_llm_turn(self, text)
        except Exception as e:
            self.log(f"[bold red]Error:[/bold red] {e}")

        # Full-Screen Layout
        self.layout = Layout(
            HSplit([
                # Sticky Top Bar
                Window(content=FormattedTextControl(lambda: get_top_toolbar(self)), height=1, style='class:top-toolbar'),
                # Scrollable History Window
                Window(content=BufferControl(buffer=self.history_buffer), wrap_lines=True),
                # Sticky Bottom Bar
                Window(content=FormattedTextControl(lambda: get_bottom_toolbar(self)), height=1, style='class:bottom-toolbar'),
                # Input Area
                Window(
                    content=BufferControl(
                        buffer=self.input_buffer,
                        input_processors=[
                            BeforeInput([('class:prompt', '> ')]),
                            Placeholder([('class:placeholder', 'Type your message or @path/to/file')])
                        ]
                    ),
                    height=1,
                    style='class:prompt'
                ),
            ])
        )
        
        # Initialize Application for full-screen management
        self.app = Application(
            layout=self.layout,
            style=self.style,
            full_screen=True,
            key_bindings=self.kb,
            mouse_support=True,
            on_invalidate=lambda _: self._scroll_to_bottom()
        )
        
    def _scroll_to_bottom(self):
        """Ensures the history window is always scrolled to the latest logs."""
        pass # Will be handled by layout configuration or manual buffer positioning
        
    def log(self, renderable):
        """Capture Rich renderables as ANSI and append to history buffer."""
        self.target_console.print(renderable)
        ansi_text = self.log_io.getvalue()
        self.log_io.truncate(0)
        self.log_io.seek(0)
        
        self.history_buffer.insert_text(ansi_text)
        # Force scroll to bottom by moving cursor in history buffer
        self.history_buffer.cursor_position = len(self.history_buffer.text)

    def _check_sudo(self):
        if os.geteuid() == 0:
            self.log("[bold red on white]  ⚠  ROOT — AI hallucinations can destroy your OS  ⚠  [/bold red on white]")

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

    def _log_output(self, text: str):
        """Append text to the history buffer for the TUI."""
        new_text = self.history_buffer.text + text + "\n"
        self.history_buffer.text = new_text

    async def run(self):
        # ── Setup ──
        self._check_sudo()
        self._discover_tools()
        if self.no_memory is False: init_memory()
        self._rebuild_system_prompt()

        # Render initial banner to history buffer
        from vibehack.ui.tui import get_banner_renderable
        self.log(get_banner_renderable())
        
        # Start Application
        try:
            await self.app.run_async()
        finally:
            self._persist()
            if not self.no_memory and len(self.history) > 2:
                ingest_session(self.target or "unknown", self.history, self.key_findings)
            print(f"\nSession {self.session_id} saved.\n")
