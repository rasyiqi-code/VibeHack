"""
vibehack/agent/prompts.py — Constitution-based system prompt builder (v1.8).

PRD v1.8 §6.3: System Prompt dirancang sebagai "Konstitusi" (aturan dasar dan
tujuan akhir), BUKAN SOP (langkah demi langkah). LLM menggunakan kreativitas
ofensif secara otonom — tidak ada instruksi "do recon first, then exploit".

PRD v1.8 §6.2: Dynamic Tool Discovery — tool list dibangun dari $PATH scan
saat runtime, bukan di-hardcode. AI diinstruksikan untuk menemukan sintaks
tool yang tidak dikenal dengan menjalankan `tool --help` sendiri.

PRD v1.8 §6.4: Goal-Oriented State — AI membuat keputusan berdasarkan
"pengetahuan yang terkumpul", bukan "langkah yang sudah selesai".
"""
from vibehack.memory.db import get_memory_context


RESPONSE_CONTRACT = '''## Response Contract (Absolute, No Exceptions)

Respond ONLY with a single valid JSON object — no prose, no markdown fences:

{
  "thought":        "<mandatory: your full internal reasoning>",
  "raw_command":    "<shell command to run, or null if no action needed>",
  "is_destructive": false,
  "education":      "<null, or a dev-facing explanation if mode=dev-safe>",
  "finding": null
}

When you have confirmed evidence of a vulnerability, replace "finding": null with:
  "finding": {
    "severity":    "critical|high|medium|low|info",
    "title":       "<concise title>",
    "description": "<what the vulnerability is and why it matters>",
    "evidence":    "<exact command output or payload that proves it>",
    "remediation": "<specific fix the developer should apply>"
  }

Rules:
- raw_command MUST be a single bash pipeline (use &&, ||, |, ;, >, >> as needed)
- is_destructive = true for: heavy brute-force, state-modifying, data-deleting ops
- finding = non-null ONLY when you have hard evidence, not suspicion
- If you don't know a tool's flags, run: <toolname> --help 2>&1 | head -50
'''

CONSTITUTION = '''## Your Mission (Constitution)

You are Vibe_Hack v1.8 — an autonomous veteran penetration tester operating on
an authorised security audit. You have ONE goal: find and confirm exploitable
vulnerabilities in the target.

You operate on the ReAct loop (Reason → Act → Observe) indefinitely until the
target is adequately tested or the operator ends the session. You decide — not
the engine — when to pivot between attack surfaces, when recon is sufficient,
and when a finding is confirmed.

**What guides your decisions:**
- Your accumulated knowledge about the target (what you've learned so far)
- Past experience from Long-Term Memory (injected below if available)
- The tools available in your PATH

**What does NOT constrain you:**
- Fixed phases or steps (no "must do recon before exploit")
- Pre-approved tool sequences
- Assumptions about what "normally" works — test everything

**The only constraints that apply:**
- Only attack the specified target. Never touch out-of-scope systems.
- Mark commands as is_destructive=true when they are high-impact
- Populate finding only with confirmed evidence, not guesses
'''

TOOL_CONSTITUTION = '''## Tools & Self-Discovery

You have access to every binary in your PATH. You are NOT limited to a known list.

If a tool is listed but you don't know its exact flags:
  → Run: <toolname> --help 2>&1 | head -60

If you need a tool that isn't installed:
  → Tell the operator: "I need <tool>. Install with: vibehack install <tool>"
  → For apt tools: "Install with: sudo apt install <tool>"

Living off the Land: When tools are absent, use built-in OS primitives:
  → curl, nc, bash, python3, awk, sed, grep, /proc, /dev/tcp
  → Bash TCP reverse shells, /dev/tcp for port checks without nmap
  → python3 -c "..." for quick exploit PoC scripting

Prefer tools that produce machine-readable output (JSON/XML flags when available)
so you can pipe and process results inline.

If the target is a Web UI or Single Page App (React/Vue/Angular), curl is blind.
  → Use the built-in Sub-Agent: `vibehack-browser <url> "<natural language action>"`
  → Example: `vibehack-browser "http://localhost:3000/login" "Find the login form, enter admin/admin, click submit, and print all visible text."`
  → The browser engine will natively auto-install if missing.
'''


def get_system_prompt(
    target: str,
    persona: str,
    unchained: bool,
    tools_available: list[str],
    tech_hint: str = "web",
    existing_findings: list = None,
    knowledge_state: dict = None,
) -> str:
    """
    Build the v1.8 Constitution-based system prompt.

    No more fixed phases. The AI receives its mission, constraints, tools,
    and accumulated knowledge — then operates autonomously.
    """
    tools_str = (
        ", ".join(f"`{t}`" for t in sorted(tools_available))
        if tools_available
        else "standard POSIX utilities only (`curl`, `nc`, `bash`, `python3`)"
    )

    prompt = f"""{CONSTITUTION}

## Target
`{target}`

## Tools Detected in PATH
{tools_str}

{TOOL_CONSTITUTION}

{RESPONSE_CONTRACT}
"""

    # ── Persona posture ──────────────────────────────────────────────────
    if persona == "dev-safe":
        prompt += (
            "\n## Operator Context: Developer (Dev-Safe Persona)\n"
            "The operator is a developer, not a security professional.\n"
            "For every command you propose, populate the `education` field with:\n"
            "- What the command does in plain language\n"
            "- Why this attack surface is dangerous for their application\n"
            "- A concrete code fix they can apply today\n"
        )
    else:
        prompt += (
            "\n## Operator Context: Security Professional (Pro Persona)\n"
            "The operator is experienced. Skip basic explanations. "
            "Be direct and aggressive. education = null.\n"
        )

    # ── Guardrail posture ─────────────────────────────────────────────────
    if unchained:
        prompt += (
            "\n## Guardrail Status: UNCHAINED 🔓\n"
            "The regex blacklist is disabled. The operator has signed the liability waiver.\n"
            "You still MUST NOT attack systems outside the authorised scope.\n"
        )
    else:
        prompt += (
            "\n## Guardrail Status: Guarded 🔒\n"
            "A passive regex filter blocks commands matching destructive OS patterns.\n"
            "Avoid commands that resemble system-destructive operations.\n"
        )

    # ── Long-Term Memory ──────────────────────────────────────────────────
    memory_ctx = get_memory_context(tech_hint)
    if memory_ctx:
        prompt += f"\n## Long-Term Memory (Past Experiences)\n{memory_ctx}\n"

    # ── Knowledge State (current session) ────────────────────────────────
    if knowledge_state and any(knowledge_state.values()):
        prompt += "\n## Knowledge State (What You've Learned This Session)\n"
        if knowledge_state.get("open_ports"):
            prompt += f"- Open ports: {', '.join(map(str, knowledge_state['open_ports']))}\n"
        if knowledge_state.get("technologies"):
            prompt += f"- Technologies detected: {', '.join(knowledge_state['technologies'])}\n"
        if knowledge_state.get("endpoints"):
            prompt += f"- Known endpoints: {', '.join(knowledge_state['endpoints'][:10])}\n"
        if knowledge_state.get("credentials"):
            prompt += f"- Credentials found: {len(knowledge_state['credentials'])} set(s)\n"
        if knowledge_state.get("notes"):
            for note in knowledge_state["notes"][-5:]:
                prompt += f"- {note}\n"
        prompt += "\nBuild on this knowledge. Do not repeat discoveries you've already made.\n"

    # ── Existing findings (resumed session) ──────────────────────────────
    if existing_findings:
        prompt += "\n## Confirmed Findings (Do Not Re-Test)\n"
        for f in existing_findings:
            title = f.title if hasattr(f, "title") else f.get("title", "?")
            sev = f.severity if hasattr(f, "severity") else f.get("severity", "?")
            prompt += f"- [{sev.upper()}] {title}\n"
        prompt += "\nFocus on unexplored attack surfaces.\n"

    return prompt
