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
    """
    Advanced Loop Detection.
    Detects:
    1. Identical repetitions (A-A-A)
    2. Simple cycles (A-B-A-B)
    """
    import json
    import re

    commands = []
    for msg in reversed(history):
        if msg["role"] == "assistant":
            try:
                content = msg["content"]
                if content.startswith("{"):
                    data = json.loads(content)
                    cmd = data.get("raw_command")
                else:
                    match = re.search(r'"raw_command":\s*"(.*?)"', content)
                    cmd = match.group(1) if match else None
                
                if cmd:
                    # Normalize command to avoid bypass with spaces
                    commands.append(cmd.strip())
            except:
                continue
        if len(commands) >= 6:
            break

    if not commands:
        return None

    # Case 1: Identical repetition (A-A-A)
    if len(commands) >= 3 and all(c == commands[0] for c in commands[:3]):
        return f"Repetitive command: {commands[0]}"

    # Case 2: Simple cycle (A-B-A-B)
    # index 0=A, 1=B, 2=A, 3=B
    if len(commands) >= 4:
        if commands[0] == commands[2] and commands[1] == commands[3]:
            return f"Cycling pattern detected: {commands[1]} -> {commands[0]}"

    return None
