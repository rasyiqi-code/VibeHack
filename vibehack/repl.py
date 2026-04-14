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
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, ConditionalContainer
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
from vibehack.ui.tui import display_banner, display_notice, log_to_pane

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
URL_PATTERN = re.compile(r"(https?://[^\s]+|(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?|localhost(?::\d+)?|[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,})", re.IGNORECASE)

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
        self.interrupted = False
        self.status = "LISTENING"
        self.session_id = generate_session_id()
        self.env = get_toolkit_env()
        self._system_built = False
        self._available_tools: List[str] = []
        
        # ── TUI Setup ─────────────────────────────────────────────────────
        self.completer = SlashCommandCompleter()
        self.style = get_repl_style()
        self.kb = KeyBindings()

        # ── TUI Buffers ──────────────────────────────────────────────────
        self.history_buffer = Buffer()
        self.output_buffer = Buffer()
        self.logs_buffer = Buffer()
        self.input_buffer = Buffer(
            completer=self.completer, 
            history=FileHistory(os.path.join(cfg.HOME, ".history")),
            complete_while_typing=True,
            read_only=Condition(lambda: self.status == "THINKING")
        )
        
        # ── Interruption Hook (ESC) ──────────────────────────────────────
        @self.kb.add('escape')
        def _(event):
            self.interrupted = True
            log_to_pane(self, "logs", "🛑 Interruption signal received (ESC).")

        @self.kb.add('c-c')
        def _(event):
            event.app.exit()

        @Condition
        def is_not_completing():
            # Allow Enter to run the command if no completions are found, even if state exists
            state = self.input_buffer.complete_state
            return not (state and state.completions)

        @self.kb.add('enter', filter=is_not_completing)
        def _(event):
            text = self.input_buffer.text
            if text.strip():
                # 1. Handle instant exit commands
                clean_cmd = text.strip().lower().replace("/", "")
                if clean_cmd in ("exit", "quit", "q"):
                    log_to_pane(self, "logs", "SYSTEM: Exit signal received. Closing...")
                    event.app.exit()
                    return

                # 2. Clear input and set status IMMEDIATELY
                self.input_buffer.text = ""
                self.status = "THINKING"
                
                # 3. Ping-Pong Effect: show user message in timeline
                if not text.startswith("/"):
                    log_to_pane(self, "history", f"👤 USER: {text}")
                    log_to_pane(self, "history", "  [ansicyan]● ● ●[/ansicyan] AI is formulating tactics...")
                
                asyncio.create_task(self.handle_input(text))
                
            event.app.invalidate()

        # ── Dashboard Layout ──────────────────────────────────────────────
        
        def create_window(buffer, title, style="", is_history=False):
            if is_history:
                return Frame(
                    HSplit([
                        Window(content=BufferControl(buffer=buffer, focusable=False), wrap_lines=True),
                        # Minimal separator line
                        Window(height=1, char='─', style='class:frame.border'),
                        # Integrated Input Prompt
                        Window(
                            content=BufferControl(
                                buffer=self.input_buffer,
                                input_processors=[BeforeInput(lambda: HTML('<prompt><b>vibe@hack:~$ </b></prompt>') if self.status == "LISTENING" else HTML('<status-thinking><b>[ SYSTEM BUSY: PROCESSING... ] </b></status-thinking>'))]
                            ),
                            height=1,
                            style='class:prompt'
                        ),
                    ]),
                    title=title,
                    style=style
                )
            return Frame(
                Window(content=BufferControl(buffer=buffer, focusable=False), wrap_lines=True),
                title=title,
                style=style
            )

        body = HSplit([
            # Top Toolbar
            Window(content=FormattedTextControl(lambda: get_top_toolbar(self)), height=1, style='class:top-toolbar'),
            # Main Split Content
            VSplit([
                # Left Pane: Mission (History + Input)
                create_window(self.history_buffer, " MISSION ", "class:history-frame", is_history=True),
                
                # Vertical Separator
                Window(width=1, char='│', style='class:frame.border'),

                # Right Pane: Telemetry
                HSplit([
                    create_window(self.output_buffer, " TELEMETRY ", "class:output-frame"),
                    # Horizontal Separator
                    Window(height=1, char='─', style='class:frame.border'),
                    create_window(self.logs_buffer, " SYSTEM LOGS ", "class:logs-frame"),
                ]),
            ]),
            # Bottom Toolbar
            Window(content=FormattedTextControl(lambda: get_bottom_toolbar(self)), height=1, style='class:bottom-toolbar'),
        ])

        # Support floating completions menu
        self.layout = Layout(
            FloatContainer(
                content=body,
                floats=[
                    Float(xcursor=True, ycursor=True, content=CompletionsMenu(max_height=16))
                ]
            )
        )
        
        # Initialize Application for full-screen management
        self.app = Application(
            layout=self.layout,
            style=self.style,
            full_screen=True,
            key_bindings=self.kb,
            mouse_support=True
        )
        
        # Focus the input buffer correctly via the layout
        self.layout.focus(self.input_buffer)
        
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
        log_to_pane(self, "logs", f"TOOLKIT: discovered {len(self._available_tools)} available binaries in PATH.")

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
        

        log_to_pane(self, "logs", f"SYSTEM: prompt re-compiled (Tools: {len(self._available_tools)}, Findings: {len(self.key_findings)})")
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

        log_to_pane(self, "logs", f"PERSIST: state saved successfully to db and session storage.")

    def _trim_history(self):
        limit = cfg.MAX_TURN_MEMORY * 2
        if len(self.history) > limit + 1:
            removed = len(self.history) - (limit + 1)
            self.history = [self.history[0]] + self.history[-limit:]

            log_to_pane(self, "logs", f"CONTEXT: trimmed {removed} turns from history to respect token limits.")

    def _extract_target_from_text(self, text: str) -> Optional[str]:
        matches = URL_PATTERN.findall(text)
        for m in matches:
            if not m.startswith("http"): m = f"http://{m}"
            return m
        return None

    async def handle_input(self, user_input: str):
        """Processes a single user command from the TUI input buffer."""
        try:
            if user_input.startswith("/"):
                result = await handle_slash_command(self, user_input)
                if self.interrupted:
                    self.interrupted = False
                    log_to_pane(self, "logs", "SYSTEM: Command interrupted.")
                if result is False:
                    self.app.exit()
                    return
                if isinstance(result, tuple) and result[0] == "__install__":
                    from vibehack.toolkit.provisioner import download_tool
                    if await download_tool(result[1]):
                        self._discover_tools()
                        self._rebuild_system_prompt()
            else:
                # Processing normal AI turn
                await process_llm_turn(self, user_input)
                
        except Exception as e:
            log_to_pane(self, "logs", f"🚨 System Error: {e}")
        finally:
            # ALWAYS return to Listening mode
            self.status = "LISTENING"
            self.app.invalidate()

    async def run(self):
        """Main REPL loop entry point."""
        import nest_asyncio
        nest_asyncio.apply()
        
        # Set terminal window title
        sys.stdout.write("\x1b]2;VibeHack [SEC-AGENT]\x07")
        sys.stdout.flush()
        
        self._check_sudo()
        self._discover_tools()
        if self.no_memory is False: init_memory()
        self._rebuild_system_prompt()
        
        # Start background telemetry & connectivity updater
        self._bg_tasks = []
        async def background_tasks():
            from vibehack.ui.tui import update_connectivity
            await update_connectivity() # Initial check
            while True:
                try:
                    await asyncio.sleep(1)
                    self.app.invalidate()
                except asyncio.CancelledError:
                    break
                
        self._bg_tasks.append(asyncio.create_task(background_tasks()))

        # Display start-up notice in logs
        log_to_pane(self, "logs", "⚔️ VibeHack Dashboard Initialized.")
        log_to_pane(self, "logs", f"Session: [bold cyan]{self.session_id}[/bold cyan]")
        if self.target:
            log_to_pane(self, "logs", f"Target: [bold yellow]{self.target}[/bold yellow]")

        # Start the fullscreen application
        await self.app.run_async()

        # Shutdown cleanup
        for t in getattr(self, '_bg_tasks', []):
            t.cancel()
            
        self._persist()
        if hasattr(self, '_kb_listener') and self._kb_listener:
            try:
                self._kb_listener.stop()
            except:
                pass
        if not self.no_memory and len(self.history) > 2:
            ingest_session(self.target or "unknown", self.history, self.key_findings)
        console.print(f"\n[bold green]Session {self.session_id} saved.[/bold green]\n")
