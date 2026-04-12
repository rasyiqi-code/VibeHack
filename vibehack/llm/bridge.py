"""
vibehack/llm/bridge.py — Instruction redirection to system CLI tools.
"""
from typing import List, Dict
from vibehack.core.auth import run_gemini_bridge

def format_messages_for_bridge(messages: List[Dict[str, str]]) -> str:
    """Convert message history to a single structured prompt for the CLI."""
    prompt_lines = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        
        if role == "system":
            prompt_lines.append(f"INSTRUCTIONS: {content}")
        elif role == "user":
            prompt_lines.append(f"USER: {content}")
        else:
            prompt_lines.append(f"ASSISTANT: {content}")
    
    prompt_lines.append("ASSISTANT: ")
    return "\n\n".join(prompt_lines)

def execute_bridge_call(messages: List[Dict[str, str]], model: str, provider: str) -> str:
    """Redirect call to the appropriate system CLI."""
    if provider == "google":
        prompt = format_messages_for_bridge(messages)
        content = run_gemini_bridge(prompt, model=model)
        if not content:
            raise Exception("Bridge Mode failed to return content from gemini-cli")
        return content
    
    raise NotImplementedError(f"Bridge mode not yet implemented for {provider}")
