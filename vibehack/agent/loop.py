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
from datetime import datetime
from typing import List, Dict, Optional
from rich.console import Console
from rich.prompt import Prompt

from vibehack.config import cfg
from vibehack.core.shell import execute_shell
from vibehack.llm.provider import UniversalHandler, AgentResponse, Finding
from vibehack.agent.prompts import get_system_prompt
from vibehack.agent.prompts.tactical import (
    get_loop_recovery,
    get_truncation_note,
    get_block_note,
    get_finding_note,
    get_memory_feedback,
    detect_logic_loop,
)
from vibehack.guardrails.regex_engine import check_command, check_target
from vibehack.guardrails.waiver import verify_unchained_access
from vibehack.memory.db import init_memory, get_memory_context, get_memory_stats
from vibehack.memory.ingestion import ingest_session, detect_technologies
from vibehack.session.persistence import save_session, generate_session_id
from vibehack.toolkit.discovery import discover_tools
from vibehack.toolkit.manager import get_toolkit_env
from vibehack.ui.tui import (
    display_banner,
    display_output,
    display_session_info,
    display_thought,
    display_education,
    display_finding,
    display_command,
    ask_approval,
    display_map,
)


console = Console()

from vibehack.agent.pipeline import AgentPipeline, PipelineContext
from vibehack.agent.middlewares import (
    ToolValidationMiddleware,
    SecurityWardenMiddleware,
    ExperienceMiddleware,
    ChameleonMiddleware,
    SkillMiddleware,
    HoneypotMiddleware,
    WorkspaceDiscoveryMiddleware,
)
from vibehack.agent.knowledge import KnowledgeState, extract_knowledge


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
        self.handler = UniversalHandler(api_key, model=cfg.MODEL)
        self.history: List[Dict[str, str]] = []
        self.auto_allow: bool = False
        self.key_findings: List[Finding] = []
        self.session_id = session_id or generate_session_id()
        self.env = get_toolkit_env()
        self.knowledge = KnowledgeState()
        self._tech_hint = ""  # Start with zero bias; let discovery determine the hint

        # Level Dewa: Pipeline Infrastructure
        self.pipeline = AgentPipeline()
        self.pipeline.use(ExperienceMiddleware())
        self.pipeline.use(WorkspaceDiscoveryMiddleware())
        self.pipeline.use(SkillMiddleware())
        self.pipeline.use(HoneypotMiddleware())
        self.pipeline.use(ToolValidationMiddleware())
        self.pipeline.use(ChameleonMiddleware())
        self.pipeline.use(SecurityWardenMiddleware(self.handler))

        from vibehack.reporting.manager import EvidenceManager

        self.evidence_mgr = EvidenceManager(self.session_id)
        self.last_command: Optional[str] = None
        self.last_output: Optional[str] = None

    # ── Internal helpers ──────────────────────────────────────────────────

    def _check_sudo(self):
        if os.geteuid() == 0:
            console.print(
                "\n[bold red on white]  ⚠  ANTI-SUDO WARNING  ⚠  [/bold red on white]\n"
                "[red]Running as ROOT. An AI hallucination here can permanently damage your OS.\n"
                "Press Ctrl-C NOW and restart as a non-privileged user.[/red]\n"
            )

    def _persist(self):
        save_session(
            self.session_id,
            {
                "session_id": self.session_id,
                "target": self.target,
                "persona": self.persona,
                "unchained": self.unchained,
                "history": self.history,
                "findings": [f.model_dump() for f in self.key_findings],
                "knowledge": self.knowledge.to_dict(),
                "auto_allow": self.auto_allow,
                "saved_at": datetime.now().isoformat(),
            },
        )

    def _trim_history(self):
        """Sliding window: keep system prompt + last (MAX_TURN_MEMORY * 2) messages."""
        limit = cfg.MAX_TURN_MEMORY * 2
        if len(self.history) > limit + 1:
            self.history = [self.history[0]] + self.history[-limit:]

    def _detect_loop(self) -> str:
        """Detects if the last 3 commands use the same base tool."""
        cmds = [
            msg.get("content", "")
            for msg in self.history[-3:]
            if msg.get("role") == "user" and "COMMAND:" in msg.get("content", "")
        ]
        if len(cmds) == 3:
            import shlex

            base_cmds = []
            for cmd_str in cmds:
                try:
                    raw = cmd_str.split("COMMAND:")[1].split("\n")[0].strip()
                    parts = shlex.split(raw)
                    if parts:
                        base_cmds.append(parts[0])
                except Exception:
                    pass
            if len(base_cmds) == 3 and len(set(base_cmds)) == 1:
                return base_cmds[0]
        return None

    def _validate_finding(self, finding) -> dict:
        """
        Validates if a security finding is actually supported by evidence.
        Returns: {'supported': bool, 'reason': str, 'confidence': float}
        """
        if not self.last_output:
            return {
                "supported": False,
                "reason": "No output for validation",
                "confidence": 0.0,
            }

        output_lower = self.last_output.lower()
        title_lower = finding.title.lower()
        desc_lower = finding.description.lower()

        # Check 1: Finding keywords should appear in output
        key_terms = set(title_lower.split() + desc_lower.split())
        key_terms = {t for t in key_terms if len(t) > 3}

        matches = 0
        for term in key_terms:
            if term in output_lower:
                matches += 1

        coverage = matches / max(len(key_terms), 1)

        if coverage < 0.3:
            return {
                "supported": False,
                "reason": f"Only {coverage * 100:.0f}% of finding keywords found in output",
                "confidence": coverage,
            }

        # Check 2: Error indicators shouldn't contradict
        contradiction_patterns = [
            ("not found", "false positive"),
            ("no such", "false positive"),
            ("error", "error in command"),
            ("failed", "command failed"),
            ("timed out", "incomplete"),
        ]

        for pattern, reason in contradiction_patterns:
            if pattern in output_lower and coverage < 0.6:
                return {
                    "supported": False,
                    "reason": f"Contradiction: {reason}",
                    "confidence": coverage,
                }

        # Check 3: Positive evidence
        positive_patterns = [
            ("vulnerable", "confirmed"),
            ("exposed", "found"),
            ("injection", "potential"),
            ("root:", "got shell"),
            ("#", "root access"),
        ]

        positive_count = sum(1 for p, _ in positive_patterns if p in output_lower)

        return {
            "supported": positive_count > 0 or coverage >= 0.5,
            "reason": f"Coverage: {coverage * 100:.0f}%, Positive markers: {positive_count}",
            "confidence": min(coverage + positive_count * 0.1, 1.0),
        }

    def _refine_tech_hint(self, text: str):
        """Update tech hint from any rich text (AI thoughts + tool output)."""
        detected = detect_technologies(text)
        if detected and detected[0] != "unknown":
            self._tech_hint = detected[0]

    def _rebuild_system_prompt(self):
        """Regenerate the system prompt with current context."""
        system_prompt = get_system_prompt(
            target=self.target,
            persona=self.persona,
            unchained=self.unchained,
            tools_available=discover_tools(),
            tech_hint=self._tech_hint,
            existing_findings=self.key_findings if self.key_findings else None,
            knowledge_state=self.knowledge.to_dict()
            if not self.knowledge.is_empty()
            else None,
            sandbox=cfg.SANDBOX_ENABLED,
        )
        # Only prepend system prompt if this is a fresh session
        if not self.history or self.history[0]["role"] != "system":
            self.history.insert(0, {"role": "system", "content": system_prompt})
        else:
            # Resumed session — update the system prompt in place
            self.history[0]["content"] = system_prompt

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
        self._rebuild_system_prompt()

        display_session_info(
            self.target,
            self.persona,
            self.unchained,
            self.session_id,
            len(available_tools),
        )
        console.print(f"[dim]💾 Resume: vibehack resume {self.session_id}[/dim]\n")

        # ── Agentic loop ──────────────────────────────────────────────────
        while True:
            try:
                # Loop Detection (Tactical)
                duplicate_cmd = detect_logic_loop(self.history)
                if duplicate_cmd:
                    self.history.append(
                        {
                            "role": "user",
                            "content": get_loop_recovery(
                                f"Command '{duplicate_cmd}' repeated 3x"
                            ),
                        }
                    )

                # 1. LLM call
                with console.status(
                    "[bold green]🤖 AI is thinking...[/bold green]", spinner="dots"
                ):
                    response: AgentResponse = await self.handler.complete(self.history)
                self.history.append(
                    {"role": "assistant", "content": response.model_dump_json()}
                )

                # Refine tech hint from AI thought
                self._refine_tech_hint(response.thought)

                # 2. Display AI state
                display_thought(response.thought)

                # [Level Dewa] Multi-Agent Pipeline (Discovery, Memory, Critique, Obfuscation)
                ctx = PipelineContext(
                    target=self.target,
                    history=self.history[:-1],
                    thought=response.thought,
                    command=response.raw_command,
                    confidence=response.confidence_score,
                    risk=response.risk_assessment,
                    metadata={"technologies": list(self.knowledge.technologies)},
                )

                # Recursive Pipeline Correction (Max 3 attempts)
                correction_count = 0
                while correction_count < 3:
                    ctx = await self.pipeline.run(ctx)
                    if not ctx.stop_execution:
                        break

                    correction_count += 1
                    reason = ctx.warning or "General strategy failure"
                    console.print(
                        f"\n[bold yellow]🛡 PIPELINE INTERRUPT ({correction_count}/3):[/bold yellow] [dim]{reason}[/dim]"
                    )

                    # Feed back to AI
                    self.history.append(
                        {
                            "role": "user",
                            "content": f"PIPELINE FEEDBACK: {reason}. Please adjust ваzh strategy.",
                        }
                    )
                    with console.status(
                        "[bold green]🤖 AI is re-thinking...[/bold green]"
                    ):
                        response = await self.handler.complete(self.history)
                    self.history.append(
                        {"role": "assistant", "content": response.model_dump_json()}
                    )

                    # Update context for next pass
                    ctx.thought = response.thought
                    ctx.command = response.raw_command
                    ctx.stop_execution = False
                    ctx.warning = None

                # Update command from pipeline (might have been obfuscated/changed)
                if ctx.command != response.raw_command:
                    console.print(
                        f"[dim]🧬 Chameleon: Payload adapted ({ctx.metadata.get('obfuscation', 'Unknown')})[/dim]"
                    )

                response.raw_command = ctx.command

                # Inject experience context if found by RAG middleware
                exp_context = ctx.metadata.get("experience_context")
                if exp_context:
                    console.print(
                        f"[dim]🧠 Context: Past experience localized for the current tech stack.[/dim]"
                    )
                    self.history.append(
                        {
                            "role": "user",
                            "content": f"HISTORICAL CONTEXT: {exp_context}",
                        }
                    )

                # Inject expert skills if found by Skill middleware
                skill_context = ctx.metadata.get("skills_context")
                if skill_context:
                    console.print(
                        f"[dim]🎯 Skill: Expert patterns for '{ctx.metadata.get('technologies', ['target'])[0]}' activated.[/dim]"
                    )
                    self.history.append(
                        {
                            "role": "user",
                            "content": f"EXPERT KNOWLEDGE INJECTION:\n{skill_context}",
                        }
                    )

                # Display Honeypot Risk
                hp_risk = ctx.metadata.get("honeypot_risk")
                if hp_risk:
                    console.print(
                        Panel(
                            f"[bold red]⚠️ DECEPTION DETECTED:[/bold red] {hp_risk}",
                            border_style="red",
                        )
                    )
                    self.history.append(
                        {
                            "role": "user",
                            "content": f"TACTICAL WARNING: {hp_risk}. Proceed with extreme caution.",
                        }
                    )

                if response.education and self.persona == "dev-safe":
                    display_education(response.education)

                # Auto-Map update from thoughts
                old_k = (
                    len(self.knowledge.open_ports),
                    len(self.knowledge.technologies),
                    len(self.knowledge.endpoints),
                )
                extract_knowledge(response.thought, self.knowledge)
                if (
                    len(self.knowledge.open_ports),
                    len(self.knowledge.technologies),
                    len(self.knowledge.endpoints),
                ) != old_k:
                    self._rebuild_system_prompt()
                display_map(self.target, self.knowledge.to_dict())

                if response.finding:
                    # v4.2: Hallucination validation
                    # Check if finding is actually supported by evidence
                    finding = response.finding
                    validation = self._validate_finding(finding)

                    if validation["supported"]:
                        display_finding(
                            finding.severity,
                            finding.title,
                            finding.description,
                        )

                        # Evidence capture
                        if self.last_command and self.last_output:
                            path = self.evidence_mgr.capture(
                                finding.title, self.last_command, self.last_output
                            )
                            console.print(
                                f"[bold cyan]📸 Evidence captured:[/bold cyan] [dim]{path}[/dim]"
                            )

                        self.key_findings.append(finding)
                        self.history.append(
                            {
                                "role": "user",
                                "content": get_finding_note(finding.title),
                            }
                        )
                        self._persist()
                    else:
                        console.print(
                            f"[bold yellow]⚠️ FINDING VALIDATION FAILED:[/bold yellow] {validation['reason']}"
                        )
                        self.history.append(
                            {
                                "role": "user",
                                "content": f"HALLUCINATION CHECK: Finding '{finding.title}' not supported by evidence. {validation['reason']}",
                            }
                        )
                    continue

                # 3. Process command
                if response.raw_command:
                    cmd = response.raw_command.strip()

                    if cmd.startswith("vibehack-memory "):
                        self._handle_memory_tool(cmd)
                        continue

                    # 3a. Guardrail check
                    block_reason = check_command(cmd, self.unchained)
                    if block_reason:
                        console.print(
                            f"\n[bold red]🛡 GUARDRAIL BLOCKED:[/bold red] {block_reason}\n"
                        )
                        self.history.append(
                            {
                                "role": "user",
                                "content": get_block_note(block_reason),
                            }
                        )
                        self._persist()
                        continue

                    # 3b. Display proposed command
                    display_command(cmd)
                    console.print(
                        f"[dim]🎯 Confidence: {response.confidence_score * 100:.1f}% | Risk: {response.risk_assessment.upper()}[/dim]"
                    )

                    # 3c. HitL — confidence-based or destructive commands bypass auto-allow
                    low_confidence = response.confidence_score < 0.8
                    high_risk = response.risk_assessment.lower() in ("med", "high")

                    if response.is_destructive:
                        console.print(
                            "[bold red]⚠ DESTRUCTIVE COMMAND — Manual approval required.[/bold red]"
                        )
                        approval = await ask_approval()
                    elif low_confidence or high_risk:
                        reason = "Low Confidence" if low_confidence else "High Risk"
                        console.print(
                            f"[bold yellow]⚠ {reason} — Auto-Allow suspended. Manual approval required.[/bold yellow]"
                        )
                        approval = await ask_approval()
                    elif self.auto_allow:
                        approval = "y"
                        console.print("[dim]⚡ Auto-Allow: executing...[/dim]")
                    else:
                        approval = await ask_approval()

                    if approval == "n":
                        note = Prompt.ask(
                            "[dim]Optional hint / alternative for the AI[/dim]",
                            default="",
                        )
                        feedback = "USER REJECTED."
                        if note:
                            feedback += f" Operator says: {note}"
                        feedback += " Propose a different approach."
                        self.history.append({"role": "user", "content": feedback})
                        self._persist()
                        continue

                    if approval == "a":
                        self.auto_allow = True
                        console.print(
                            "[yellow]⚡ Auto-Allow enabled for this session.[/yellow]"
                        )

                    # 3d. Execute
                    result = await execute_shell(
                        cmd,
                        timeout=cfg.CMD_TIMEOUT,
                        truncate_limit=cfg.TRUNCATE_LIMIT,
                        env=self.env,
                    )

                    # Update tracking for evidence
                    self.last_command = cmd
                    self.last_output = result.stdout + (
                        f"\nSTDERR:\n{result.stderr}" if result.stderr else ""
                    )

                    if result.truncated:
                        console.print(
                            f"[dim]ℹ Output truncated to {cfg.TRUNCATE_LIMIT} chars.[/dim]"
                        )

                    display_output(result.stdout)
                    if result.stderr:
                        display_output(result.stderr, is_error=True)

                    # Refine tech hint from tool output
                    self._refine_tech_hint(result.stdout)

                    # [Level Dewa] Real-time Map update from tool output
                    old_k = (
                        len(self.knowledge.open_ports),
                        len(self.knowledge.technologies),
                        len(self.knowledge.endpoints),
                    )
                    extract_knowledge(result.stdout, self.knowledge)
                    if (
                        len(self.knowledge.open_ports),
                        len(self.knowledge.technologies),
                        len(self.knowledge.endpoints),
                    ) != old_k:
                        self._rebuild_system_prompt()
                    display_map(self.target, self.knowledge.to_dict())

                    # 3e. Feed result back (Sensory Upgrade: Syntract)
                    from vibehack.agent.syntract import summarize_output

                    processed_stdout = await summarize_output(
                        self.handler, cmd, result.stdout
                    )

                    feedback = (
                        f"COMMAND: {cmd}\n"
                        f"EXIT_CODE: {result.exit_code}\n"
                        f"STDOUT:\n{processed_stdout}"
                    )
                    if result.stderr:
                        processed_stderr = await summarize_output(
                            self.handler, f"{cmd} [STDERR]", result.stderr
                        )
                        feedback += f"\nSTDERR:\n{processed_stderr}"
                    if result.truncated:
                        feedback += get_truncation_note(cfg.TRUNCATE_LIMIT)
                        console.print(
                            f"[dim]ℹ Output truncated to {cfg.TRUNCATE_LIMIT} chars.[/dim]"
                        )

                    self.history.append({"role": "user", "content": feedback})

                else:
                    # 4. No command — let user steer
                    console.print(
                        "[dim]AI has no command. Steer the session or press Enter to continue.[/dim]"
                    )
                    user_input = Prompt.ask("💬", default="")

                    if user_input.lower() in ("quit", "exit", "q", ":q"):
                        console.print("[bold green]Session ended.[/bold green]")
                        break
                    if user_input.lower() in ("report", ":report"):
                        console.print(
                            f"[bold cyan]Run:[/bold cyan] vibehack report {self.session_id}"
                        )
                        break

                    content = (
                        user_input
                        if user_input
                        else "Continue with the next logical step."
                    )
                    self.history.append({"role": "user", "content": content})

                # Enforce sliding window + persist after every turn
                self._trim_history()
                self._persist()

            except KeyboardInterrupt:
                console.print(
                    "\n[bold yellow]Interrupted. Saving session...[/bold yellow]"
                )
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

    def _handle_memory_tool(self, cmd: str):
        """Internal tool for AI to search past experiences."""
        from vibehack.memory.db import get_memory_context

        parts = cmd.strip().split()
        keyword = parts[2] if len(parts) > 2 else "web"
        console.print(
            f"[dim]🧠 AI is searching Long-Term Memory for: [cyan]{keyword}[/cyan][/dim]"
        )
        memory_ctx = get_memory_context(keyword)
        self.history.append(
            {"role": "user", "content": get_memory_feedback(keyword, memory_ctx)}
        )
        self._persist()
