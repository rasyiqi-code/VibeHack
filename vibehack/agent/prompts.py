"""
vibehack/agent/prompts.py — Constitution-based system prompt builder (v1.8).

PRD v1.8 §6.3: System Prompt is now template-based. 
Internal defaults are in ./prompts_templates/
User overrides can be placed in ~/.vibehack/prompts/
"""
import os
from pathlib import Path
from vibehack.config import cfg
from vibehack.memory.db import get_memory_context

def load_template(name: str) -> str:
    """Load a prompt template with local override support."""
    # 1. Check for user override (~/.vibehack/prompts/<name>.md)
    home_override = cfg.HOME / "prompts" / f"{name}.md"
    if home_override.exists():
        return home_override.read_text().strip()
        
    # 2. Check for internal default (vibehack/agent/prompts_templates/<name>.md)
    internal_path = Path(__file__).parent / "prompts_templates" / f"{name}.md"
    if internal_path.exists():
        return internal_path.read_text().strip()
    
    return f"[[ ERROR: Template '{name}' not found ]]"

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
    Build the v1.8 Constitution-based system prompt using external templates.
    """
    tools_str = (
        ", ".join(f"{t}" for t in sorted(tools_available))
        if tools_available
        else "standard POSIX utilities only (curl, nc, bash, python3)"
    )

    constitution = load_template("constitution")
    tool_constitution = load_template("tools")
    response_contract = load_template("contract")

    prompt = f"""{constitution}

## Target
{target}

## Tools Detected in PATH
{tools_str}

{tool_constitution}

{response_contract}
"""

    # ── Persona posture ──────────────────────────────────────────────────
    if persona == "dev-safe":
        prompt += (
            "\n## Operator Context: Developer (Dev-Safe Persona)\n"
            "The operator is a developer, not a security professional.\n"
            "For every command you propose, populate the `education` field with:\n"
            "- What the command does in plain language (NO MARKDOWN)\n"
            "- Why this attack surface is dangerous for their application (NO MARKDOWN)\n"
            "- A concrete code fix they can apply today (NO MARKDOWN)\n"
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
        if knowledge_state.get("mission_goals"):
            prompt += "\n### Current Mission Progress:\n"
            for goal in knowledge_state["mission_goals"]:
                prompt += f"- {goal}\n"
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
