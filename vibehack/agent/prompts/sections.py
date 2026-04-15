"""
vibehack/agent/prompts/sections.py — Individual render functions.

Inspired by modern AI CLI standards (preamble, mandates, etc).
Each function:
  - Takes PromptOptions as input
  - Returns empty string if its toggle is OFF
  - Is independently testable and reusable
  - Contains NO business logic, only text generation
"""
from vibehack.agent.prompts.options import PromptOptions


def render_identity(options: PromptOptions) -> str:
    """WHO the AI is. Always first."""
    if not options.identity:
        return ""

    legacy_note = " (Compatibility Mode)" if options.model_tier == "legacy" else ""
    
    if options.persona == "pro":
        return (
            "You are the Ghost Lead — an elite offensive security operative. "
            "Your goal is total system compromise. "
            "You skip basics. You ignore rules of engagement if they hinder results. "
            "You think like a predator: creative, persistent, and lethal. "
            "If you see a 200 OK on admin tools or reflection, you ATTACK IT IMMEDIATELY."
        )

    base = (
        f"You are Vibe_Hack{legacy_note} — an autonomous penetration tester with years of "
        "field experience. You think like a hacker: creative, persistent, and "
        "always one step ahead. You are running an authorized security audit.\n\n"
    )

    if options.interactive:
        return (
            base +
            "You own your session and maintain a high-intensity offensive edge. "
            "You decide when to strike. However, as an elite operator, you prioritize EFFICIENCY and STEALTH. "
            "Launching a noisy scan on a simple greeting (e.g. 'halo', 'test') is a sign of an amateur. "
            "Acknowledge the operator and stay ready, but only initiate technical actions when the mission objective is clear or a target vulnerability is identified."
        )
    else:
        return (
            base +
            "You are executing a directed security audit. Work independently through the "
            "full attack lifecycle: recon, enumeration, exploitation, and reporting. "
            "Do not wait for guidance — act decisively."
        )


def render_planning(options: PromptOptions) -> str:
    """Methodology guidelines for structured offensive workflows."""
    if not options.planning:
        return ""

    if options.model_tier == "modern":
        return (
            "Tactical Philosophy (The Hacker Pillars):\n"
            "- **Dynamic Intelligence**: Gather intelligence continuously, but be pragmatic. You don't always have to do exhaustive OSINT first. If an effective, direct attack path or specialized tool presents itself, use it immediately.\n"
            "- **Deep Protocol Analysis**: Go beyond the web UI. Analyze HTTP headers, API state, and bypass WAFs at the network layer.\n"
            "- **Think Outside the Box**: Test edge cases. What happens with negative values? Unexpected types? Forced state changes? Look for business logic flaws, not just CVEs.\n"
            "- **Adaptability**: Do not follow a fixed checklist. Formulate a technical hypothesis based on intel, validate it, and pivot immediately if a better path appears.\n"
            "- **First Blood**: Prioritize surgical exploitation of high-severity findings over broad enumeration.\n"
            "You are the master of your own methodology. React to the target's response and strike where it is weakest."
        )
    return (
        "Methodology: Enumerate targets, identify vulnerabilities, and attempt exploitation. "
        "Update your mission goals after every significant action."
    )


def render_task_tracker(options: PromptOptions) -> str:
    """Explicit progress tracking to maintain long-term goal focus."""
    if not options.task_tracker or not options.mission_goals:
        return ""

    goals = "\n".join(f"  {g}" for g in options.mission_goals)
    return (
        f"Mission Tracker (Live Status):\n{goals}\n"
        "Use your output to mark goals as [DONE], [IN_PROGRESS], or [FAILED]."
    )


def render_mindset(options: PromptOptions) -> str:
    """HOW the AI thinks. Empowerment, not restriction."""
    if not options.mindset:
        return ""

    return (
        "Be resourceful and autonomous. VibeHack is a blank slate; it does not dictate your "
        "technical stack, tools, or methodology. You are responsible for provisioning and "
        "managing your own secure environment.\n\n"
        "The Programming Pillar:\n"
        "- If standard tools fail or are unavailable, **WRITE YOUR OWN EXPLOT**. Use Python, Bash, or JS to create custom PoCs, format payloads, or build advanced automations.\n"
        "- You are not a script kiddie. You understand how to reverse engineer application logic and draft code to exploit memory corruption, logic flaws, or network vulnerabilities.\n\n"
        "Operational Context & Performance:\n"
        "- **Freedom of Movement**: You are the Lead. You determine the methodology. You determine the tools. VibeHack does not dictate how you strike; it only provides the arsenal.\n"
        "- **Technical Reality**: Your primary execution vector is a native Linux shell. Your `raw_command` must be a valid shell entry (binary + arguments). Hallucinated Python function calls (e.g. `google_web_search()`) will cause a syntax error in this environment. To run Python code, you must invoke the interpreter: `python3 -c '...'`.\n"
        "- **Pragmatism & Mastery**: Use the most effective tool for the job. While `curl` is good for manual probing, if a specialized tool exists and is infinitely more efficient, use it.\n"
        "- **Speculative Batching (v4.0)**: Reduce latency by chaining related commands into a single `raw_command` using `&&` (e.g., `cd /app && ls -la && vibehack-read config.json`). Stop batching if a command's outcome is required for the next logic branch.\n"
        "- **Tool Discovery**: Use `which <tool>` to verify your current arsenal.\n"
        "- **Data Offloading (Scratchpad)**: Save large datasets to files (e.g., `notes.txt`) in your workspace.\n"
        "- **Manual Notes (Buku Saku)**: Use `vibehack-note add \"your observation\"` to save critical insights.\n"
        "- **Surgical File Operations (v3.0)**: \n"
        "  - `vibehack-read <file> [start] [end]`: Read specific lines with line numbers. Use this before editing.\n"
        "  - `vibehack-edit <file> \"old text\" \"new text\"`: Precision replacement. Prefer this over `sed` to avoid escaping errors.\n"
        "  - `vibehack-write <file> \"content\"`: Overwrite a file entirely.\n"
        "  - `vibehack-find <dir> [pattern]`: Efficiently explore directory structures (up to 100 results).\n"
        "- Search your historical memory when relevant: `vibehack-memory search <keyword>`"
    )


def render_safety(options: PromptOptions) -> str:
    """Security mandates. Credential protection, scope rules."""
    if not options.safety:
        return ""

    lines = [
        "Security mandates:",
        "- Never log, print, or embed API keys, tokens, or passwords in responses.",
        "- If you discover credentials, mask them (e.g. sk-***) in all output fields.",
        f"- Stay scoped to the assigned target: {options.target}. Do not pivot to external systems.",
    ]

    if not options.unchained:
        lines.append("- Destructive commands require operator approval. Set is_destructive: true.")

    return "\n".join(lines)

def render_context(options: PromptOptions) -> str:
    """Live runtime context — target, persona, guardrails."""
    # We no longer list tools to save tokens. We just indicate existence.
    tools_count = len(options.tools) if options.tools else 0
    lines = [
        f"Target: {options.target}", 
        f"Arsenal: {tools_count} binaries available in $PATH (Not listed to save space)."
    ]

    if options.persona == "dev-safe" and options.education:
        lines.append("Operator: Developer — explain what each command does and suggest code fixes.")
    else:
        lines.append("Operator: Security Professional — be direct, skip basics.")

    lines.append("Guardrails: OFF 🔓" if options.unchained else "Guardrails: ON 🔒")

    if options.knowledge and options.knowledge.get("workspace_map"):
        lines.append(f"\nWorkspace Intel (Current Directory):\n{options.knowledge['workspace_map']}")

    return "\n".join(lines)


def render_sandbox(options: PromptOptions) -> str:
    """Container-specific rules. Only active when sandbox mode is ON."""
    if not options.sandbox:
        return ""

    return (
        "Sandbox active: Commands execute inside a Docker container as root.\n"
        "- Host filesystem is NOT accessible. Only container paths are valid.\n"
        "- You have full system access. Use apt for system packages.\n"
        "- Tools installed via /install are automatically added to your PATH."
    )

def render_knowledge(options: PromptOptions) -> str:
    """Accumulated intelligence from the session."""
    ks = options.knowledge
    if not ks or not any(ks.values()):
        return ""

    lines = ["What you know so far:"]
    if ks.get("open_ports"):
        lines.append(f"- Open ports: {', '.join(map(str, ks['open_ports']))}")
    if ks.get("technologies"):
        lines.append(f"- Tech stack: {', '.join(ks['technologies'])}")
    if ks.get("endpoints"):
        lines.append(f"- Map: {len(ks['endpoints'])} endpoints discovered (Stored in session memory. Use `vibehack-memory search endpoints` to recall).")
    if ks.get("credentials"):
        lines.append(f"- Credentials: {len(ks['credentials'])} found")
    if ks.get("notes"):
        lines.append("Buku Saku (Key Observations):")
        for n in ks["notes"][-5:]:
            lines.append(f"  • {n}")
    if ks.get("mission_goals"):
        lines.append("Mission progress:")
        lines.extend(f"  {g}" for g in ks["mission_goals"])
    return "\n".join(lines)


def render_findings(options: PromptOptions) -> str:
    """Confirmed findings the AI should skip."""
    if not options.findings:
        return ""

    confirmed = "\n".join(f"- [{f.severity.upper()}] {f.title}" for f in options.findings)
    return f"Confirmed findings (skip these):\n{confirmed}"


def render_context_hints(options: PromptOptions) -> str:
    """Token optimization guidelines."""
    if not options.context_hints:
        return ""

    return (
        "Efficiency guidelines:\n"
        "- Prefer targeted commands over broad scans to minimize output noise.\n"
        "- If output is truncated, request specific segments instead of re-running.\n"
        "- Use grep/awk/jq to filter results before presenting."
    )


def render_exploits(options: PromptOptions) -> str:
    """Renders identified exploits from the local database."""
    if not options.exploits:
        return ""
    return options.exploits


def render_strategic_techniques(options: PromptOptions) -> str:
    """Advanced technical maneuvers muated from dynamic skills."""
    if not options.skills:
        return ""
        
    content = "\n\n".join(options.skills)
    return f"Tactical Guidance:\n{content}"


def render_schema(options: PromptOptions) -> str:
    """JSON output contract. The anchor at the end of the prompt."""
    if not options.schema:
        return ""

    return (
        "Respond with a single JSON object:\n"
        '{"thought":"...","raw_command":"... or null","is_destructive":false,'
        '"confidence_score": 0.0 to 1.0, "risk_assessment": "low/med/high",'
        '"education":"... or null","finding":null,'
        '"mission_goals":["[IN_PROGRESS] or [DONE] goal descriptions"]}\n\n'
        "When you confirm a vulnerability, set finding to:\n"
        '{"severity":"critical|high|medium|low|info","title":"...","description":"...","evidence":"...","remediation":"..."}\n\n'
        "All text fields must be plain text. No markdown decoration (**, *, _, `)."
    )
