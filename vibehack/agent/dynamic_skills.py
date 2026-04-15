"""
vibehack/agent/dynamic_skills.py — Dynamic Skills System.

Features:
  - Skills loaded from markdown files
  - Runtime updates from CVE intelligence
  - Adaptive learning integration
  - Technology-specific hints
"""

import json
import re
from typing import Dict, List, Optional
from pathlib import Path


class DynamicSkills:
    """
    Dynamic skill loader that evolves during runtime.
    Combines static skills with learned patterns and CVE intelligence.
    """

    def __init__(self):
        self.skills_dir = Path(__file__).parent.parent / "skills"
        self._load_skills()

    def _load_skills(self):
        """Load all skill files."""
        self.skills = {}

        if not self.skills_dir.exists():
            return

        for skill_file in self.skills_dir.glob("*.md"):
            tech = skill_file.stem  # filename without extension
            try:
                with open(skill_file) as f:
                    content = f.read()
                    self.skills[tech.lower()] = content
            except:
                pass

    def get_skill(self, technology: str) -> Optional[str]:
        """Get skill for a specific technology."""
        tech_lower = technology.lower()

        # Direct match
        if tech_lower in self.skills:
            return self.skills[tech_lower]

        # Fuzzy match - check if technology is part of skill name
        for skill_name in self.skills.keys():
            if skill_name in tech_lower or tech_lower in skill_name:
                return self.skills[skill_name]

        return None

    def get_skill_context(self, technology: str, cve_context: str = "") -> str:
        """
        Get full skill context including learned patterns.
        """
        skill = self.get_skill(technology)

        if not skill and not cve_context:
            return ""

        parts = []

        # Static skill
        if skill:
            parts.append(f"### {technology.upper()} TACTICS:\n{skill}")

        # CVE intelligence
        if cve_context:
            parts.append(cve_context)

        return "\n\n".join(parts)

    def add_skill(self, technology: str, content: str):
        """Add or update a skill."""
        tech_lower = technology.lower()
        skill_file = self.skills_dir / f"{tech_lower}.md"

        with open(skill_file, "w") as f:
            f.write(content)

        self.skills[tech_lower] = content

    def list_skills(self) -> List[str]:
        """List all available skills."""
        return list(self.skills.keys())


# Global instance
_skills = None


def get_dynamic_skills() -> DynamicSkills:
    """Get global dynamic skills instance."""
    global _skills
    if _skills is None:
        _skills = DynamicSkills()
    return _skills


def get_skill_context(technology: str, cve_context: str = "") -> str:
    """Quick function to get skill context."""
    return get_dynamic_skills().get_skill_context(technology, cve_context)


# Integration with adaptive learning and CVE
async def get_enhanced_context(technologies: List[str]) -> str:
    """
    Get enhanced context combining skills, CVEs, and learned tactics.
    """
    from vibehack.toolkit.security import get_cve_context
    from vibehack.memory.adaptive import get_learned_tactics

    context_parts = []

    for tech in technologies:
        # Get skill
        skill = get_dynamic_skills().get_skill(tech)

        # Get CVEs
        cve = get_cve_context(tech)

        # Get learned tactics
        learned = get_learned_tactics(tech)

        tech_context = f"### {tech.upper()}"

        if skill:
            tech_context += f"\n\n{skill}"

        if cve:
            tech_context += f"\n\n{cve}"

        if learned:
            top_tactics = [f"- {t['tactic'][:100]}" for t in learned[:3]]
            tech_context += f"\n\n### Learned Patterns:\n" + "\n".join(top_tactics)

        context_parts.append(tech_context)

    return "\n\n---\n\n".join(context_parts)
