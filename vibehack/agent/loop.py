"""
vibehack/agent/loop.py — Core agentic loop (Raw Shell / HitL Edition).

Orchestrates:
  1. Target + Unchained gate checks
  2. Tool discovery
  3. System prompt construction (with LTM injection)
  4. Per-turn: LLM → Guardrail → HitL Approval → Shell Exec → Feedback
  5. End-of-session: LTM ingestion + final persist
"""
import asyncio
import os
import uuid
from datetime import datetime
from typing import List, Dict
from rich.console import Console
from rich.prompt import Prompt

from vibehack.config import cfg
from vibehack.core.shell import execute_shell
from vibehack.llm.provider import UniversalHandler, AgentResponse, Finding
from vibehack.agent.prompts import get_system_prompt
from vibehack.guardrails.regex_engine import check_command, check_target
from vibehack.guardrails.waiver import verify_unchained_access
from vibehack.memory.db import init_memory, get_memory_context, get_memory_stats
from vibehack.memory.ingestion import ingest_session, detect_technology
from vibehack.session.persistence import save_session
from vibehack.toolkit.discovery import discover_tools

# Re-exported for legacy compat (cli.py check command)
# Will be removed when cli.py check is fully migrated to discovery
KNOWN_TOOLS: list[str] = []  # Populated at runtime via discover_tools()


console = Console()

class AgentLoop:
    def __init__(
        self,
        target: str,
        api_key: str,
        persona: str = "dev-safe",
        unchained: bool = False,
        no_memory: bool = False,
        session_id: str = None,
    ):
        self.target = target
        self.persona = persona
        self.unchained = unchained
        self.no_memory = no_memory
        self.handler = UniversalHandler(api_key, model=os.getenv("VH_MODEL", cfg.MODEL))
        self.history: List[Dict[str, str]] = []
        self.auto_allow: bool = False
        self.key_findings: List[Finding] = []
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.env = get_toolkit_env()
        self._tech_hint = "web"  # Refined dynamically from AI thoughts

    # ── Internal helpers ──────────────────────────────────────────────────

    def _check_sudo(self):
        if os.geteuid() == 0:
            console.print(
                "\n[bold red on white]  ⚠  ANTI-SUDO WARNING  ⚠  [/bold red on white]\n"
                "[red]Running as ROOT. An AI hallucination here can permanently damage your OS.\n"
                "Press Ctrl-C NOW and restart as a non-privileged user.[/red]\n"
            )

    def _persist(self):
        save_session(self.session_id, {
            "session_id": self.session_id,
            "target": self.target,
            "persona": self.persona,
            "unchained": self.unchained,
            "history": self.history,
            "findings": [f.model_dump() for f in self.key_findings],
            "auto_allow": self.auto_allow,
            "saved_at": datetime.now().isoformat(),
        })

    def _trim_history(self):
        """Sliding window: keep system prompt + last (MAX_TURN_MEMORY * 2) messages."""
        limit = cfg.MAX_TURN_MEMORY * 2
        if len(self.history) > limit + 1:
            self.history = [self.history[0]] + self.history[-limit:]

    def _refine_tech_hint(self, text: str):
        """Update tech hint from any rich text (AI thoughts + tool output)."""
        detected = detect_technology(text)
        if detected != "unknown":
            self._tech_hint = detected

    def _build_finding_feedback(self, finding: Finding) -> str:
        return (
            f"[VIBEHACK] Finding recorded: [{finding.severity.upper()}] {finding.title}. "
            "Do not re-test this. Continue to next attack surface."
        )

    # ── Main run loop ─────────────────────────────────────────────────────

    async def run(self):
        display_banner()
        self._check_sudo()

        # ── Gate 1: Target sanity ─────────────────────────────────────────
        target_error = check_target(self.target)
        if target_error:
            display_output(target_error, is_error=True)
            return

        # ── Gate 2: Unchained waiver ──────────────────────────────────────
        if not verify_unchained_access(self.unchained):
            return

        # ── §6.2 Dynamic Tool Discovery ───────────────────────────────────
        available_tools = discover_tools()
        global KNOWN_TOOLS
        KNOWN_TOOLS = available_tools  # Keep export in sync for legacy callers

        # ── LTM memory context ────────────────────────────────────────────
        if not self.no_memory:
            init_memory()
            stats = get_memory_stats()
            if stats["total"] > 0:
                console.print(
                    f"[dim]🧠 LTM: {stats['total']} experiences loaded "
                    f"({stats['successes']} successes / {stats['failures']} failures)[/dim]"
                )

        # ── System prompt ─────────────────────────────────────────────────
        system_prompt = get_system_prompt(
            target=self.target,
            persona=self.persona,
            unchained=self.unchained,
            tools_available=available_tools,
            tech_hint=self._tech_hint,
            existing_findings=self.key_findings if self.key_findings else None,
        )

        # Only prepend system prompt if this is a fresh session
        if not self.history or self.history[0]["role"] != "system":
            self.history.insert(0, {"role": "system", "content": system_prompt})
        else:
            # Resumed session — update the system prompt in place
            self.history[0]["content"] = system_prompt

        display_session_info(self.target, self.persona, self.unchained, self.session_id, len(available_tools))
        console.print(f"[dim]💾 Resume: vibehack resume {self.session_id}[/dim]\n")

        # ── Agentic loop ──────────────────────────────────────────────────
        while True:
            try:
                # 1. LLM call
                with console.status("[bold green]🤖 AI is thinking...[/bold green]", spinner="dots"):
                    response: AgentResponse = await self.handler.complete(self.history)
                self.history.append({"role": "assistant", "content": response.model_dump_json()})

                # Refine tech hint from AI thought
                self._refine_tech_hint(response.thought)

                # 2. Display AI state
                display_thought(response.thought)

                if response.education and self.persona == "dev-safe":
                    display_education(response.education)

                if response.finding:
                    display_finding(
                        response.finding.severity,
                        response.finding.title,
                        response.finding.description,
                    )
                    self.key_findings.append(response.finding)
                    self.history.append({
                        "role": "user",
                        "content": self._build_finding_feedback(response.finding),
                    })
                    self._persist()
                    continue  # Finding recorded — let AI propose next step

                # 3. Process command
                if response.raw_command:
                    cmd = response.raw_command.strip()

                    # 3a. Guardrail check
                    block_reason = check_command(cmd, self.unchained)
                    if block_reason:
                        console.print(f"\n[bold red]🛡 GUARDRAIL BLOCKED:[/bold red] {block_reason}\n")
                        self.history.append({
                            "role": "user",
                            "content": f"GUARDRAIL BLOCKED: {block_reason}. Rethink — propose a safer alternative.",
                        })
                        self._persist()
                        continue

                    # 3b. Display proposed command
                    display_command(cmd)

                    # 3c. HitL — destructive commands bypass auto-allow
                    if response.is_destructive:
                        console.print(
                            "[bold red]⚠  DESTRUCTIVE COMMAND — Auto-Allow suspended. Manual approval required.[/bold red]"
                        )
                        approval = ask_approval()
                    elif self.auto_allow:
                        approval = "y"
                        console.print("[dim]⚡ Auto-Allow: executing...[/dim]")
                    else:
                        approval = ask_approval()

                    if approval == "n":
                        note = Prompt.ask("[dim]Optional hint / alternative for the AI[/dim]", default="")
                        feedback = "USER REJECTED."
                        if note:
                            feedback += f" Operator says: {note}"
                        feedback += " Propose a different approach."
                        self.history.append({"role": "user", "content": feedback})
                        self._persist()
                        continue

                    if approval == "a":
                        self.auto_allow = True
                        console.print("[yellow]⚡ Auto-Allow enabled for this session.[/yellow]")

                    # 3d. Execute
                    result = execute_shell(cmd, timeout=cfg.CMD_TIMEOUT, truncate_limit=cfg.TRUNCATE_LIMIT, env=self.env)

                    if result.truncated:
                        console.print("[dim]ℹ Output truncated to 2,500 chars.[/dim]")

                    display_output(result.stdout)
                    if result.stderr:
                        display_output(result.stderr, is_error=True)

                    # Refine tech hint from tool output
                    self._refine_tech_hint(result.stdout)

                    # 3e. Feed result back
                    feedback = (
                        f"COMMAND: {cmd}\n"
                        f"EXIT_CODE: {result.exit_code}\n"
                        f"STDOUT:\n{result.stdout}"
                    )
                    if result.stderr:
                        feedback += f"\nSTDERR:\n{result.stderr}"
                    if result.truncated:
                        feedback += "\n[Note: Output truncated. Request specific fields if needed.]"

                    self.history.append({"role": "user", "content": feedback})

                else:
                    # 4. No command — let user steer
                    console.print("[dim]AI has no command. Steer the session or press Enter to continue.[/dim]")
                    user_input = Prompt.ask("💬", default="")

                    if user_input.lower() in ("quit", "exit", "q", ":q"):
                        console.print("[bold green]Session ended.[/bold green]")
                        break
                    if user_input.lower() in ("report", ":report"):
                        console.print(f"[bold cyan]Run:[/bold cyan] vibehack report {self.session_id}")
                        break

                    content = user_input if user_input else "Continue with the next logical step."
                    self.history.append({"role": "user", "content": content})

                # Enforce sliding window + persist after every turn
                self._trim_history()
                self._persist()

            except KeyboardInterrupt:
                console.print("\n[bold yellow]Interrupted. Saving session...[/bold yellow]")
                break

            except Exception as e:
                console.print(f"\n[bold red]Loop error:[/bold red] {e}")
                self._persist()
                await asyncio.sleep(2)  # Brief pause before retrying

        # ── End of session ────────────────────────────────────────────────
        self._persist()

        if not self.no_memory and self.history:
            console.print("[dim]🧠 Ingesting session into Long-Term Memory...[/dim]")
            try:
                count = ingest_session(self.target, self.history, self.key_findings)
                console.print(f"[dim]   {count} experience(s) recorded.[/dim]")
            except Exception as e:
                console.print(f"[dim]   LTM ingestion failed: {e}[/dim]")

        if self.key_findings:
            console.print(
                f"\n[bold green]Session complete.[/bold green] "
                f"{len(self.key_findings)} finding(s). Generate report:\n"
                f"[cyan]  vibehack report {self.session_id}[/cyan]\n"
            )
