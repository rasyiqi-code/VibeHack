"""
vibehack/agent/prompts/registry.py — Backward-compatible template registry.

Used by load_template() for named lookups (e.g., ask_mode).
Core prompt logic has moved to sections.py (render functions).
"""
from vibehack.agent.prompts.sections import render_schema


class PromptRegistry:
    """Named template lookup for non-builder use cases."""

    ASK_MODE = (
        "The operator is asking you a technical question. "
        "Answer directly and thoroughly — you are a mentor now, not an operator. "
        "No JSON needed unless you want to structure your thought process. "
        "Plain text, no markdown decoration."
    )

    @classmethod
    def get(cls, name: str) -> str:
        mapping = {
            "ask_mode": cls.ASK_MODE,
        }
        return mapping.get(name, "")
