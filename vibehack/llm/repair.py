"""
vibehack/llm/repair.py — Utilities to fix malformed JSON from LLM outputs.
"""
import json
import re
from typing import Optional

def repair_json(text: str) -> Optional[dict]:
    """
    Attempt to extract a valid JSON object from an LLM response that may
    contain leading/trailing prose or broken formatting.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    fenced = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    fenced = re.sub(r"```\s*$", "", fenced, flags=re.MULTILINE).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass

    # Last resort: find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None
