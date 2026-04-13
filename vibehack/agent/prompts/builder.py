"""
vibehack/agent/prompts/builder.py — Composable prompt orchestrator.

# Like Modern CLI's getCoreSystemPrompt():
  1. Receives PromptOptions (structured config)
  2. Calls individual render functions
  3. Filters empty sections
  4. Joins into final prompt
  5. Optionally exports debug output

Architecture:
  PromptOptions
      ↓
  build_system_prompt(options)
      ↓
  ├─→ render_identity(options)
  ├─→ render_mindset(options)
  ├─→ render_safety(options)
  ├─→ render_context(options)
  ├─→ render_sandbox(options)
  ├─→ render_knowledge(options)
  ├─→ render_findings(options)
  ├─→ render_context_hints(options)
  ├─→ render_schema(options)       ← anchor (last = strongest)
      ↓
  Final prompt (string)
"""
import os
from vibehack.agent.prompts.options import PromptOptions
from vibehack.agent.prompts.sections import (
    render_identity,
    render_mindset,
    render_planning,
    render_task_tracker,
    render_safety,
    render_context,
    render_sandbox,
    render_knowledge,
    render_findings,
    render_context_hints,
    render_schema,
)


# ── Render pipeline (ordered) ────────────────────────────────────────
# Each function returns "" if its toggle is off → filtered out by join.
RENDER_PIPELINE = [
    render_identity,
    render_mindset,
    render_planning,
    render_task_tracker,
    render_safety,
    render_context,
    render_sandbox,
    render_knowledge,
    render_findings,
    render_context_hints,
    render_schema,        # Always last = strongest anchor for the AI
]


def build_system_prompt(options: PromptOptions, overrides: dict = None) -> str:
    """
    Compose the system prompt from structured options.

    Like Gemini CLI's getCoreSystemPrompt(options: SystemPromptOptions).
    """
    # Apply file overrides as raw section replacements
    override_map = overrides or {}

    sections = []
    for render_fn in RENDER_PIPELINE:
        # Check if there's a file override for this section
        section_name = render_fn.__name__.replace("render_", "")
        if section_name in override_map:
            section_text = override_map[section_name]
        else:
            section_text = render_fn(options)

        if section_text:
            sections.append(section_text)

    prompt = "\n\n".join(sections)

    # ── Variable substitution in overrides (${target}, ${tools}, etc.) ──
    prompt = _substitute_variables(prompt, options)

    # ── Debug export ─────────────────────────────────────────────────
    if os.getenv("VH_DEBUG_PROMPT", "").strip() == "1":
        _export_debug(prompt)

    return prompt


def _substitute_variables(prompt: str, options: PromptOptions) -> str:
    """Replace ${var} placeholders in override templates."""
    tools_csv = ", ".join(sorted(options.tools)) if options.tools else "coreutils"
    replacements = {
        "${target}": options.target,
        "${tools}": tools_csv,
        "${persona}": options.persona,
        "${tech_hint}": options.tech_hint,
    }
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    return prompt


def _export_debug(prompt: str):
    """Write the generated prompt to disk for inspection."""
    from vibehack.config import cfg
    debug_path = cfg.HOME / "debug_prompt.md"
    try:
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(prompt)
    except Exception:
        pass  # Debug export is best-effort
