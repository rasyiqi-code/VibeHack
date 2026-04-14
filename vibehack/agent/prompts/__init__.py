"""
vibehack/agent/prompts/__init__.py — Public API for the prompt system.

Supports:
  1. Full env var override (VH_SYSTEM_PROMPT=path → bypass builder)
  2. Per-section file overrides (~/.vibehack/prompts/identity.md)
  3. Composable builder with PromptOptions
"""
import os
from pathlib import Path
from vibehack.config import cfg
from vibehack.agent.prompts.options import PromptOptions
from vibehack.agent.prompts.registry import PromptRegistry
from vibehack.agent.prompts.builder import build_system_prompt as _build


# Re-export for external consumers
__all__ = ["get_system_prompt", "load_template", "PromptOptions"]


def load_template(name: str) -> str:
    """
    Load a prompt template.
    1. Check for user override (~/.vibehack/prompts/<name>.md)
    2. Fallback to native internal Registry.
    """
    home_override = cfg.HOME / "prompts" / f"{name}.md"
    if home_override.exists():
        return home_override.read_text().strip()

    return PromptRegistry.get(name)


def get_system_prompt(
    target: str,
    persona: str,
    unchained: bool,
    tools_available: list[str],
    tech_hint: str = "web",
    existing_findings: list = None,
    knowledge_state: dict = None,
    sandbox: bool = False,
) -> str:
    """
    Build the system prompt. Entry point for repl.py and loop.py.

    Priority:
      1. VH_SYSTEM_PROMPT env var → full file override (like GEMINI_SYSTEM_MD)
      2. Per-section file overrides (~/.vibehack/prompts/*.md)
      3. Native composable builder
    """
    # ── Priority 1: Full env var override ─────────────────────────────
    env_override = os.getenv("VH_SYSTEM_PROMPT", "").strip()
    if env_override:
        override_path = Path(env_override).expanduser()
        if override_path.exists():
            return override_path.read_text().strip()

    # ── Priority 2: Collect per-section file overrides ────────────────
    overrides = {}
    section_names = ["identity", "mindset", "safety", "schema", "context_hints", "sandbox"]
    for name in section_names:
        home_part = cfg.HOME / "prompts" / f"{name}.md"
        if home_part.exists():
            overrides[name] = home_part.read_text().strip()

    # ── Priority 3: Build from structured options ─────────────────────
    model_name = cfg.MODEL.lower()
    legacy_keys = ["gpt-3.5", "claude-2", "gemini-pro-1.0", "bison"]
    tier = "legacy" if any(k in model_name for k in legacy_keys) else "modern"

    from vibehack.toolkit.exploits import get_exploit_context
    tech_list = list(knowledge_state.get("technologies", [])) if knowledge_state else []
    exploit_intel = get_exploit_context(tech_list)

    from vibehack.agent.prompts.loader import load_skills_for_tech
    skills = load_skills_for_tech(tech_list)

    options = PromptOptions(
        interactive=True,
        target=target,
        persona=persona,
        unchained=unchained,
        tools=tools_available,
        tech_hint=tech_hint,
        knowledge=knowledge_state,
        findings=existing_findings,
        exploits=exploit_intel,
        sandbox=sandbox or cfg.SANDBOX_ENABLED,
        education=(persona == "dev-safe"),
        model_tier=tier,
        mission_goals=knowledge_state.get("mission_goals") if knowledge_state else None,
        skills=skills
    )

    return _build(options, overrides=overrides)
