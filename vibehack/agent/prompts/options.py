"""
vibehack/agent/prompts/options.py — Structured prompt configuration.

Like Gemini CLI's SystemPromptOptions interface:
Controls WHAT sections are included and WITH WHAT data.
Each field is independently toggleable.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PromptOptions:
    """Type-safe configuration for system prompt composition."""

    # ── Feature toggles (enable/disable sections independently) ──────
    identity: bool = True
    mindset: bool = True
    safety: bool = True           # Credential protection, scope rules
    sandbox: bool = False         # Container-specific rules
    education: bool = True        # Dev-safe explainers
    schema: bool = True           # JSON contract
    context_hints: bool = True    # Token optimization guidelines
    planning: bool = True         # Structured attack planning instructions
    task_tracker: bool = True     # Visual representation of mission goals

    # ── Runtime context (data injected by the system) ────────────────
    interactive: bool = True      # REPL mode vs autonomous (start command)
    target: str = "not set"
    persona: str = "dev-safe"
    unchained: bool = False
    tools: List[str] = field(default_factory=list)
    tech_hint: str = "web"
    model_tier: str = "modern"    # modern (Flash 3) vs legacy

    # ── Dynamic state (populated during session) ─────────────────────
    knowledge: Optional[dict] = None
    findings: Optional[list] = None
    mission_goals: Optional[List[str]] = None
    exploits: Optional[str] = None
    skills: List[str] = field(default_factory=list) # Raw markdown content of skills
