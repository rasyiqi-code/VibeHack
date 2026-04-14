"""
vibehack/agent/prompts/loader.py — Dynamic skill discovery and loading.
"""
from pathlib import Path
from typing import List, Optional
from vibehack.config import cfg

def load_skills_for_tech(technologies: List[str]) -> List[str]:
    """
    Search and load relevant markdown skills based on detected tech stack.
    Discovers aliases by scanning 'Tags:' or 'Aliases:' headers in skill files.
    """
    loaded_content = []
    seen_files = set()
    base_dir = Path(__file__).parent.parent.parent / "skills"
    
    if not base_dir.exists():
        return []

    # 1. Build Dynamic Alias Map by scanning file headers
    # Map: tag -> Path
    tag_map = {}
    for skill_file in base_dir.glob("*.md"):
        try:
            # We only read the first 10 lines for performance
            with open(skill_file, "r", encoding="utf-8") as f:
                header = [next(f) for _ in range(10)]
            
            # Look for "Aliases: ..." or "Tags: ..."
            for line in header:
                if line.lower().startswith(("aliases:", "tags:")):
                    tags = [t.strip().lower() for t in line.split(":")[1].split(",")]
                    for t in tags:
                        tag_map[t] = skill_file
            
            # Also map the filename itself (without .md)
            tag_map[skill_file.stem.lower()] = skill_file
        except (StopIteration, Exception):
            # Also map filename if header read fails
            tag_map[skill_file.stem.lower()] = skill_file

    # 2. Match and Load
    for tech in technologies:
        tech_clean = tech.lower().strip()
        path = tag_map.get(tech_clean)
        
        if path and path.name not in seen_files:
            try:
                content = path.read_text(encoding="utf-8")
                loaded_content.append(content)
                seen_files.add(path.name)
            except Exception:
                pass
                    
    return loaded_content
