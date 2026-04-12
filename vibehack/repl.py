"""
vibehack/repl.py — Interactive REPL Orchestrator for VibeHack.
Modularized in v2.6.45 to separate UI, Logic, and Commands.
"""
import asyncio
import os
import re
from typing import List, Dict, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
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
from vibehack.ui.tui import display_banner

# Modular Imports
from vibehack.core.repl.commands import handle_slash_command
from vibehack.core.repl.logic import process_llm_turn
from vibehack.ui.repl.prompts import SlashCommandCompleter, get_repl_style, get_bottom_toolbar

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

        # ── TUI Setup ─────────────────────────────────────────────────────
        self.completer = SlashCommandCompleter()
        self.session = PromptSession(
            history=FileHistory(os.path.join(cfg.HOME, ".history")),
            completer=self.completer,
            complete_while_typing=True,
        )
        self.style = get_repl_style()

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
        display_banner()
        self._check_sudo()
        self._discover_tools()
        if self.no_memory is False: init_memory()
        self._rebuild_system_prompt()

        console.print(f"[dim]🔍 Tools: {len(self._available_tools)} discovered | Session: {self.session_id}[/dim]\n")

        while True:
            try:
                user_input = await self.session.prompt_async(
                    "you: ",
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
                            clear_discovery_cache()
                            self._discover_tools()
                            self._rebuild_system_prompt()
                    continue

                await process_llm_turn(self, user_input)

            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                await asyncio.sleep(1)

        self._persist()
        if not self.no_memory and len(self.history) > 2:
            ingest_session(self.target or "unknown", self.history, self.key_findings)
        console.print(f"\n[bold green]Session {self.session_id} saved.[/bold green]\n")
