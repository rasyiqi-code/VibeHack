"""
vibehack/repl.py — Interactive REPL for Vibe_Hack v1.8.

Primary UX: run `vibehack` → interactive hacking co-pilot (like Claude Code
but for offensive security). Implements PRD v1.8 architecture:

  §6.1 ReAct Loop  — Reason → Act → Observe, infinite, no hardcoded workflow
  §6.2 Dynamic Tool Discovery — scans $PATH at runtime
  §6.3 Constitution Prompt — goal-oriented, not SOP
  §6.4 Knowledge State — tracks WHAT is known, not what steps were done
"""
import asyncio
import os
import re
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from vibehack.config import cfg
from vibehack.llm.provider import UniversalHandler, AgentResponse, Finding
from vibehack.agent.prompts import get_system_prompt
from vibehack.agent.knowledge import KnowledgeState, extract_knowledge
from vibehack.guardrails.regex_engine import check_command, check_target
from vibehack.guardrails.waiver import verify_unchained_access
from vibehack.memory.db import init_memory, get_memory_stats
from vibehack.memory.ingestion import ingest_session
from vibehack.session.persistence import save_session
from vibehack.toolkit.manager import get_toolkit_env
from vibehack.toolkit.discovery import discover_tools, clear_discovery_cache
from vibehack.core.shell import execute_shell
from vibehack.ui.tui import (
    display_banner, display_thought, display_command,
    display_education, display_finding, display_output,
    display_session_info, display_knowledge_update, ask_approval,
)

console = Console()

# Regex to detect URLs/IPs mentioned in user messages
URL_PATTERN = re.compile(
    r"(https?://[^\s]+|(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?|localhost(?::\d+)?)",
    re.IGNORECASE,
)

SLASH_COMMANDS = {
    "/help":      "Show this help message",
    "/target":    "Set or show target (/target http://localhost:3000)",
    "/mode":      "Switch operational mode (/mode agent | /mode ask)",
    "/persona":   "Switch persona (/persona dev-safe | /persona pro)",
    "/ask":       "Ask a theory question without executing anything",
    "/unchained": "Toggle unchained mode (disables regex guardrails)",
    "/install":   "Install a tool (/install nuclei)",
    "/findings":  "List confirmed findings",
    "/knowledge": "Show current knowledge state (ports, tech, endpoints)",
    "/report":    "Generate Markdown audit report",
    "/clear":     "Clear conversation history (keeps knowledge & findings)",
    "/memory":    "Show Long-Term Memory stats",
    "/tools":     "Show tools discovered in your PATH",
    "/exit":      "Save session and exit",
}


class VibehackREPL:
    def __init__(
        self,
        target: Optional[str] = None,
        op_mode: str = "agent",
        persona: str = "dev-safe",
        unchained: bool = False,
        no_memory: bool = False,
        api_key: str = "",
    ):
        self.target = target
        self.op_mode = op_mode
        self.persona = persona
        self.unchained = unchained
        self.no_memory = no_memory
        self.api_key = api_key
        self.handler = UniversalHandler(api_key, model=os.getenv("VH_MODEL", cfg.MODEL))
        self.history: List[Dict[str, str]] = []
        self.key_findings: List[Finding] = []
        self.knowledge = KnowledgeState()       # §6.4 Knowledge State
        self.auto_allow = False
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.env = get_toolkit_env()
        self._system_built = False
        self._available_tools: List[str] = []  # §6.2 Dynamic discovery

    # ── Internals ─────────────────────────────────────────────────────────

    def _check_sudo(self):
        if os.geteuid() == 0:
            console.print(
                "[bold red on white]  ⚠  ROOT — AI hallucinations can destroy your OS  ⚠  [/bold red on white]"
            )

    def _discover_tools(self):
        """§6.2: Scan $PATH dynamically at startup and after installs."""
        self._available_tools = discover_tools()

    def _rebuild_system_prompt(self):
        """Rebuild the system prompt with current knowledge state."""
        system_prompt = get_system_prompt(
            target=self.target or "not yet set",
            persona=self.persona,
            unchained=self.unchained,
            tools_available=self._available_tools,
            tech_hint=next(iter(self.knowledge.technologies), "web"),
            existing_findings=self.key_findings if self.key_findings else None,
            knowledge_state=self.knowledge.to_dict() if not self.knowledge.is_empty() else None,
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
        """Sliding window: keep system prompt + last N*2 messages."""
        limit = cfg.MAX_TURN_MEMORY * 2
        if len(self.history) > limit + 1:
            self.history = [self.history[0]] + self.history[-limit:]

    def _extract_target_from_text(self, text: str) -> Optional[str]:
        matches = URL_PATTERN.findall(text)
        for m in matches:
            if not m.startswith("http"):
                m = f"http://{m}"
            return m
        return None

    def _print_status_bar(self):
        target_display = f"[cyan]{self.target}[/cyan]" if self.target else "[dim]no target[/dim]"
        op_color = "magenta" if self.op_mode == "ask" else "blue"
        persona_color = "green" if self.persona == "dev-safe" else "yellow"
        unchained = " [bold red]🔓UNCHAINED[/bold red]" if self.unchained else ""
        sandbox_flag = " [bold blue]📦SANDBOX[/bold blue]" if cfg.SANDBOX_ENABLED else ""
        findings = f"[yellow]{len(self.key_findings)}f[/yellow]" if self.key_findings else "[dim]0f[/dim]"
        ports = f" [dim]ports:{len(self.knowledge.open_ports)}[/dim]" if self.knowledge.open_ports else ""
        techs = f" [dim]tech:{len(self.knowledge.technologies)}[/dim]" if self.knowledge.technologies else ""
        console.print(
            f"[dim]┌[/dim] {target_display}  "
            f"[{op_color}]{self.op_mode}[/{op_color}] "
            f"[{persona_color}]{self.persona}[/{persona_color}]{unchained}{sandbox_flag}  "
            f"{findings}{ports}{techs}",
            highlight=False,
        )

    # ── Slash command handlers ────────────────────────────────────────────

    def _handle_slash(self, cmd: str):
        """
        Handle /command. Returns:
          True  → keep running
          False → signal exit
          ("__install__", tool_name) → async install needed
        """
        parts = cmd.strip().split(None, 1)
        verb = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if verb == "/help":
            lines = [f"  [cyan]{k}[/cyan]  [dim]{v}[/dim]" for k, v in SLASH_COMMANDS.items()]
            console.print(Panel("\n".join(lines), title="Slash Commands", border_style="dim"))

        elif verb == "/target":
            if arg:
                err = check_target(arg)
                if err:
                    console.print(f"[red]Blocked:[/red] {err}")
                else:
                    self.target = arg
                    console.print(f"[green]✓ Target:[/green] {arg}")
                    self._rebuild_system_prompt()
            else:
                console.print(f"Target: [cyan]{self.target or 'not set'}[/cyan]")

        elif verb == "/mode":
            if arg in ("agent", "ask"):
                self.op_mode = arg
                console.print(f"[green]✓ Operation mode:[/green] {arg}")
            else:
                console.print(f"Mode: {self.op_mode} | Use: /mode agent  or  /mode ask")

        elif verb == "/persona":
            if arg in ("dev-safe", "pro"):
                self.persona = arg
                console.print(f"[green]✓ Persona:[/green] {arg}")
                self._rebuild_system_prompt()
            else:
                console.print(f"Persona: {self.persona} | Use: /persona dev-safe  or  /persona pro")


        elif verb == "/unchained":
            if not self.unchained:
                if verify_unchained_access(True):
                    self.unchained = True
                    console.print("[bold red]🔓 Unchained mode enabled.[/bold red]")
                    self._rebuild_system_prompt()
            else:
                self.unchained = False
                console.print("[green]🔒 Guardrails restored.[/green]")
                self._rebuild_system_prompt()

        elif verb == "/install":
            if not arg:
                console.print("[dim]Usage: /install <tool>[/dim]")
            else:
                from vibehack.toolkit.provisioner import DOWNLOADABLE_TOOLS
                if arg not in DOWNLOADABLE_TOOLS:
                    console.print(f"[red]'{arg}' not in registry.[/red]")
                    console.print(f"[dim]{', '.join(DOWNLOADABLE_TOOLS.keys())}[/dim]")
                else:
                    return ("__install__", arg)

        elif verb == "/knowledge":
            if self.knowledge.is_empty():
                console.print("[dim]No knowledge accumulated yet. Start scanning.[/dim]")
            else:
                k = self.knowledge
                if k.open_ports:
                    console.print(f"🔌 [bold]Open ports:[/bold] {', '.join(map(str, sorted(k.open_ports)))}")
                if k.technologies:
                    console.print(f"⚙  [bold]Technologies:[/bold] {', '.join(sorted(k.technologies))}")
                if k.endpoints:
                    console.print(f"🗺  [bold]Endpoints ({len(k.endpoints)}):[/bold] {', '.join(k.endpoints[:10])}{'...' if len(k.endpoints) > 10 else ''}")
                if k.credentials:
                    console.print(f"🔑 [bold]Credentials:[/bold] {len(k.credentials)} found")
                if k.notes:
                    console.print("[bold]📝 Notes:[/bold]")
                    for note in k.notes[-5:]:
                        console.print(f"  • {note}")

        elif verb == "/findings":
            if not self.key_findings:
                console.print("[dim]No confirmed findings yet.[/dim]")
            else:
                BADGES = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
                for i, f in enumerate(self.key_findings, 1):
                    console.print(f"  {i}. {BADGES.get(f.severity.lower(), '?')} [{f.severity.upper()}] {f.title}")

        elif verb == "/report":
            from vibehack.reporting.exporter import export_report
            path = export_report(
                self.target or "unknown", self.key_findings,
                self.history, cfg.HOME / "reports"
            )
            console.print(f"[bold green]✅ Report:[/bold green] {path}")

        elif verb == "/clear":
            sys_msg = self.history[0] if self.history and self.history[0]["role"] == "system" else None
            self.history = [sys_msg] if sys_msg else []
            console.print("[dim]History cleared. Knowledge and findings preserved.[/dim]")

        elif verb == "/memory":
            if not self.no_memory:
                s = get_memory_stats()
                console.print(
                    f"🧠 LTM: [bold]{s['total']}[/bold] experiences  "
                    f"([green]{s['successes']} ✅[/green] / [red]{s['failures']} ❌[/red])"
                )
            else:
                console.print("[dim]LTM disabled.[/dim]")

        elif verb == "/tools":
            tools = self._available_tools
            console.print(f"[green]Discovered ({len(tools)}):[/green] {', '.join(tools) or 'none'}")
            console.print("[dim]Scanned from $PATH + ~/.vibehack/bin/[/dim]")

        elif verb in ("/exit", "/quit", "/q"):
            return False

        else:
            console.print(f"[red]Unknown:[/red] {verb}. Type /help")

        return True

    # ── Main LLM turn (ReAct: Reason → Act → Observe) ────────────────────

    async def _do_llm_turn(self, user_message: str, force_ask: bool = False):
        """One ReAct iteration. §6.1: pure loop, no hardcoded workflow."""

        is_ask_mode = force_ask or self.op_mode == "ask"

        # Intercept shell commands typed by mistake
        if user_message.strip().startswith("vibehack "):
            parts = user_message.strip().split()
            if len(parts) > 2 and parts[1] == "install":
                tool_name = parts[2]
                console.print(
                    f"\n[yellow]ℹ  That's a shell command. Use inside REPL:[/yellow] [cyan]/install {tool_name}[/cyan]\n"
                )
                from vibehack.toolkit.provisioner import DOWNLOADABLE_TOOLS
                if tool_name in DOWNLOADABLE_TOOLS and Confirm.ask(f"Install {tool_name} now?", default=True):
                    from vibehack.toolkit.provisioner import download_tool
                    ok = await download_tool(tool_name)
                    if ok:
                        clear_discovery_cache()
                        self._discover_tools()
                        self._rebuild_system_prompt()
                return
            console.print(
                f"\n[yellow]ℹ  Shell commands go outside the REPL.[/yellow]\n"
                "[dim]Try asking naturally: 'scan for open ports' / 'check my toolkit'[/dim]\n"
            )
            return

        # Auto-detect target from natural language
        if not self.target:
            detected = self._extract_target_from_text(user_message)
            if detected and not check_target(detected):
                self.target = detected
                console.print(f"[dim]✓ Target auto-detected: {detected}[/dim]")
                self._rebuild_system_prompt()

        if not self._system_built:
            self._rebuild_system_prompt()

        self.history.append({"role": "user", "content": user_message})

        # ── Reason: Call LLM ──────────────────────────────────────────────
        console.print()
        # with console.status("[dim]Thinking...[/dim]", spinner="dots2"): # Removed old wrapper
        try:
            if is_ask_mode:
                # In ask mode, we use raw completion, skipping JSON constraints
                ask_sys = {"role": "system", "content": "The user is asking a question or requesting a payload. DO NOT output JSON. Respond in plain helpful markdown text."}
                ask_history = [ask_sys] + self.history

                with console.status("[bold magenta]🤖 AI is formulating answer...[/bold magenta]", spinner="dots"):
                    raw_resp = await self.handler.complete_raw(ask_history)
                console.print(f"\n{raw_resp}\n")
                self.history.append({"role": "assistant", "content": raw_resp})
                self._trim_history()
                self._persist()
                return

            with console.status("[bold green]🤖 AI is thinking...[/bold green]", spinner="dots"):
                response: AgentResponse = await self.handler.complete(self.history)
        except Exception as e:
            console.print(f"[red]LLM error:[/red] {e}")
            self.history.pop()
            return

        self.history.append({"role": "assistant", "content": response.model_dump_json()})

        # Update tech hint from thought
        from vibehack.memory.ingestion import detect_technology
        tech = detect_technology(response.thought)
        if tech != "unknown":
            self.knowledge.technologies.add(tech)

        # Display thought
        console.print()
        display_thought(response.thought)

        if response.education and self.persona == "dev-safe":
            display_education(response.education)

        # Finding recorded → persist + continue
        if response.finding:
            display_finding(
                response.finding.severity,
                response.finding.title,
                response.finding.description,
            )
            self.key_findings.append(response.finding)
            self.knowledge.tested_surfaces.add(response.finding.title)
            self.history.append({
                "role": "user",
                "content": f"[FINDING CONFIRMED] {response.finding.title}. Continue to next unexplored surface.",
            })
            self._persist()
            return

        # ── Act: Execute command ──────────────────────────────────────────
        if response.raw_command:
            cmd = response.raw_command.strip()

            block = check_command(cmd, self.unchained)
            if block:
                console.print(f"\n[bold red]🛡 BLOCKED:[/bold red] {block}\n")
                self.history.append({
                    "role": "user",
                    "content": f"GUARDRAIL BLOCKED: {block}. Propose an alternative.",
                })
                self._persist()
                return

            display_command(cmd)

            if response.is_destructive:
                console.print("[bold red]⚠  DESTRUCTIVE — manual approval required[/bold red]")
                approval = ask_approval()
            elif self.auto_allow:
                approval = "y"
                console.print("[dim]⚡ Auto-Allow[/dim]")
            else:
                approval = ask_approval()

            if approval == "n":
                note = Prompt.ask("[dim]Hint for AI (optional)[/dim]", default="")
                msg = "USER REJECTED."
                if note:
                    msg += f" Hint: {note}"
                self.history.append({"role": "user", "content": msg})
                self._persist()
                return

            if approval == "a":
                self.auto_allow = True
                console.print("[yellow]⚡ Auto-Allow enabled[/yellow]")

            # ── Observe: Capture output ───────────────────────────────────
            result = execute_shell(cmd, timeout=cfg.CMD_TIMEOUT, truncate_limit=cfg.TRUNCATE_LIMIT, env=self.env)

            if result.truncated:
                console.print("[dim]ℹ Output truncated[/dim]")

            display_output(result.stdout)
            if result.stderr:
                display_output(result.stderr, is_error=True)

            # §6.4: Auto-extract knowledge from output
            old_ports = len(self.knowledge.open_ports)
            old_tech = len(self.knowledge.technologies)
            old_endpoints = len(self.knowledge.endpoints)

            extract_knowledge(result.stdout, self.knowledge)
            extract_knowledge(result.stderr or "", self.knowledge)
            
            new_ports = list(self.knowledge.open_ports) if len(self.knowledge.open_ports) > old_ports else []
            new_tech = list(self.knowledge.technologies) if len(self.knowledge.technologies) > old_tech else []
            new_endpoints = self.knowledge.endpoints if len(self.knowledge.endpoints) > old_endpoints else []
            
            if new_ports or new_tech or new_endpoints:
                display_knowledge_update(new_ports, new_tech, new_endpoints)

            # Rebuild prompt if we learned something new
            if not self.knowledge.is_empty():
                self._rebuild_system_prompt()

            feedback = (
                f"COMMAND: {cmd}\nEXIT_CODE: {result.exit_code}\n"
                f"STDOUT:\n{result.stdout}"
            )
            if result.stderr:
                feedback += f"\nSTDERR:\n{result.stderr}"
            if result.truncated:
                feedback += "\n[Truncated. Ask for specific data if needed.]"
            self.history.append({"role": "user", "content": feedback})

        self._trim_history()
        self._persist()

    # ── Entry point ───────────────────────────────────────────────────────

    async def run(self):
        display_banner()
        self._check_sudo()

        # §6.2: Dynamic tool discovery at startup
        self._discover_tools()

        # Target gate
        if self.target:
            err = check_target(self.target)
            if err:
                console.print(f"[red]{err}[/red]")
                self.target = None

        # Unchained waiver
        if self.unchained and not verify_unchained_access(True):
            self.unchained = False

        # LTM init
        if not self.no_memory:
            init_memory()
            s = get_memory_stats()
            if s["total"] > 0:
                console.print(f"[dim]🧠 LTM: {s['total']} experiences loaded[/dim]")

        self._rebuild_system_prompt()

        display_session_info(
            self.target or "not set",
            self.persona,
            self.unchained,
            self.session_id,
            len(self._available_tools),
        )
        console.print(
            f"[dim]🔍 Tools: {len(self._available_tools)} discovered in $PATH[/dim]"
        )
        console.print(
            "[dim]Chat naturally or use /help. Set target with /target <url> or mention it in chat.[/dim]\n"
        )

        # ── ReAct REPL loop (§6.1) ────────────────────────────────────────
        while True:
            try:
                console.print()
                self._print_status_bar()

                try:
                    user_input = Prompt.ask("[bold green]you[/bold green]")
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[bold yellow]Saving...[/bold yellow]")
                    break

                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    if user_input.startswith("/ask "):
                        # One-off ask question
                        q = user_input[5:].strip()
                        if q:
                            await self._do_llm_turn(q, force_ask=True)
                        continue

                    result = self._handle_slash(user_input)
                    if result is False:
                        break
                    if isinstance(result, tuple) and result[0] == "__install__":
                        from vibehack.toolkit.provisioner import download_tool
                        ok = await download_tool(result[1])
                        if ok:
                            clear_discovery_cache()
                            self._discover_tools()
                            self._rebuild_system_prompt()
                    continue

                await self._do_llm_turn(user_input)

            except KeyboardInterrupt:
                console.print("\n[bold yellow]Interrupted. Saving...[/bold yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                await asyncio.sleep(1)

        # ── End session ───────────────────────────────────────────────────
        self._persist()

        if not self.no_memory and len(self.history) > 2:
            try:
                count = ingest_session(self.target or "unknown", self.history, self.key_findings)
                if count:
                    console.print(f"[dim]🧠 {count} experience(s) → LTM[/dim]")
            except Exception:
                pass

        if self.key_findings:
            console.print(
                f"\n[bold green]{len(self.key_findings)} finding(s).[/bold green] "
                f"Report: [cyan]vibehack report {self.session_id}[/cyan]\n"
            )
        else:
            console.print(f"\n[dim]Session: {self.session_id}[/dim]")
