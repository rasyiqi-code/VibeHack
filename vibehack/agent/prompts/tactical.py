"""
vibehack/agent/prompts/tactical.py — Tactical (Short-Lived) Prompts.

Influenced by Gemini CLI's 'Tactical Inline' pattern.
These messages are injected during execution for loop recovery, 
continuation, and system feedback.
"""

def get_loop_recovery(detail: str = "Repetitive patterns identified") -> str:
    """Tactical feedback to break model reasoning loops."""
    return (
        f"System: Potential loop detected. Details: {detail}. "
        "Please take a step back, reconsider your strategy, and try a different "
        "approach or tool. Ensure you are making forward progress."
    )

def get_truncation_note(limit: int) -> str:
    """Note injected when shell output is truncated to save tokens."""
    return (
        f"\n\nSystem: [VibeHack Note] Output truncated to {limit} chars. "
        "If you need specific segments of the missing output, use targeted tools "
        "(grep, awk, sed, head, tail) to extract them."
    )

def get_block_note(reason: str) -> str:
    """Feedback when a command is blocked by guardrails."""
    return f"System: GUARDRAIL BLOCKED. Reason: {reason}. Propose a safer alternative."

def get_finding_note(title: str) -> str:
    """Confirmation when a finding is saved to state."""
    return f"System: Finding recorded: '{title}'. Move to the next attack surface."

def get_memory_feedback(keyword: str, context: str) -> str:
    """Standardized feedback for LTM search results."""
    if not context:
        return f"System: VIBEHACK-MEMORY — No past experiences found for '{keyword}'."
    return f"System: VIBEHACK-MEMORY — Results for '{keyword}':\n{context}"

def detect_logic_loop(history: list) -> str | None:
    """Detect if the AI is repeating the same command (Logic Loop)."""
    import json
    commands = []
    for msg in reversed(history):
        if msg["role"] == "assistant":
            try:
                # Handle both raw strings and dumped JSONs
                content = msg["content"]
                if content.startswith("{"):
                    data = json.loads(content)
                    cmd = data.get("raw_command")
                else:
                    # Fallback for non-JSON or repaired strings
                    import re
                    match = re.search(r'"raw_command":\s*"(.*?)"', content)
                    cmd = match.group(1) if match else None
                
                if cmd:
                    commands.append(cmd)
                if len(commands) >= 3:
                    break
            except:
                continue
    
    if len(commands) >= 3 and all(c == commands[0] for c in commands):
        return commands[0]
    return None
