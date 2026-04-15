"""
vibehack/agent/syntract.py — Structured Intel Extraction & Anti-Injection Layer.

Processes raw shell output to:
1. Redact potential prompt injections from target data.
2. Summarize large outputs to save tokens.
3. Extract structured entities (emails, IPs, hashes) for the knowledge base.
"""

import re
import json
from typing import Dict, Any, List, Optional
from vibehack.config import cfg

# Phase 1: Basic regex patterns (still needed for quick filtering before LLM)
INJECTION_TRIGGERS = [
    r"(?i)system:",
    r"(?i)user:",
    r"(?i)assistant:",
    r"(?i)instruction:",
    r"(?i)command:",
    r"(?i)ignore\s+all\s+previous",
    r"(?i)forget\s+your\s+rules",
    r"\[ansicyan\].*?\[/ansicyan\]",
    r"(?i)now\s+ignore\s+all",
    r"(?i)disregard\s+all",
]

# Phase 2: Expanded patterns for common bypass techniques
INJECTION_BYPASS_PATTERNS = [
    r"\{\{.*?\}\}",  # Template injection
    r"<\s*script",  # XSS attempts
    r"\\\u[0-9a-fA-F]{4}",  # Unicode escape
    r"\x[0-9a-fA-F]{2}",  # Hex encoding
    r"&#\d+;",  # HTML entities
]


def _quick_redact_basic(text: str) -> str:
    """Fast regex-based pre-filtering."""
    if not text:
        return ""
    for pattern in INJECTION_TRIGGERS:
        text = re.sub(pattern, "[REDACTED_BASIC]", text)
    for pattern in INJECTION_BYPASS_PATTERNS:
        text = re.sub(pattern, "[REDACTED_BYPASS]", text)
    return text


def detect_injection_risk(text: str) -> dict:
    """
    Multi-layer injection detection.
    Returns: {'risk_level': 'low'|'medium'|'high', 'detections': [], 'recommendation': str}
    """
    if not text or len(text) < 10:
        return {"risk_level": "low", "detections": [], "recommendation": "pass"}

    detections = []
    text_lower = text.lower()

    # Layer 1: Direct command patterns
    direct_triggers = [
        ("system:", "Direct system prompt"),
        ("ignore all previous", "Instruction override"),
        ("forget your rules", "Role override"),
        ("new instruction:", "New instruction injection"),
    ]
    for trigger, desc in direct_triggers:
        if trigger in text_lower:
            detections.append(f"Direct: {desc}")

    # Layer 2: Contextual framing (AI trying to frame target as authoritative)
    framing_patterns = [
        (r"as an ai\b", "AI self-reference"),
        (r"your role is to", "Role assignment"),
        (r"you must\b", "Obligation framing"),
        (r"respond only in", "Output format hijack"),
    ]
    for pattern, desc in framing_patterns:
        if re.search(pattern, text_lower):
            detections.append(f"Framing: {desc}")

    # Layer 3: Encoding attempts (bypass techniques)
    if re.search(r"\\u[0-9a-fA-F]{4}|\\\x[0-9a-fA-F]{2}", text):
        detections.append("Encoding: Unicode/Hex escape")
    if re.search(r"&#\d+;|&#x[0-9a-fA-F]+;", text):
        detections.append("Encoding: HTML entity")
    if re.search(r"\{(?:\s*\{)+|(?:\}\s*\})+", text):
        detections.append("Encoding: Nested template")

    # Layer 4: Behavioral manipulation
    behavioral = [
        ("respond only with", "Output restriction"),
        ("say nothing else", "Output suppression"),
        ("exit", "Exit command"),
    ]
    for trigger, desc in behavioral:
        if trigger in text_lower:
            detections.append(f"Behavioral: {desc}")

    # Risk scoring
    if len(detections) >= 3:
        risk_level = "high"
        recommendation = "block"
    elif len(detections) >= 1:
        risk_level = "medium"
        recommendation = "flag"
    else:
        risk_level = "low"
        recommendation = "pass"

    return {
        "risk_level": risk_level,
        "detections": detections,
        "recommendation": recommendation,
    }


def redact_injections(text: str) -> str:
    """
    Multi-layer injection prevention:
    1. Quick regex pre-filter
    2. Risk analysis
    3. Wrap in boundaries
    """
    if not text:
        return ""

    # Layer 1: Quick regex redaction
    text = _quick_redact_basic(text)

    # Layer 2: Risk analysis (strips high-risk content markers)
    risk = detect_injection_risk(text)
    if risk["risk_level"] == "high":
        # Replace entire content with warning
        return f"\n<DATA_FLAGGED_SECURITY_WARNING detections={risk['detections']}>\n[Content redacted due to detected prompt injection patterns]\n</DATA_FLAGGED>\n"

    # Layer 3: Wrap in boundaries
    return (
        f"\n<TARGET_DATA_START risk={risk['risk_level']}>\n{text}\n<TARGET_DATA_END>\n"
    )


async def summarize_output(handler, command: str, raw_output: str) -> str:
    """
    Selective entity extraction instead of lossy summarization.
    Preserves ALL raw data but tags sections for easy reference.
    """
    # Always run injection detection first
    raw_output = redact_injections(raw_output)

    if len(raw_output) < 1500:
        # Small output: preserve as-is with metadata
        return f"<RAW_OUTPUT size={len(raw_output)}>\n{raw_output}\n</RAW_OUTPUT>"

    # Big output: Extract entities and wrap with metadata instead of summarizing
    entities = extract_entities(raw_output)

    # Build structured summary (NOT lossy)
    summary_parts = [
        f"<OUTPUT_METADATA>",
        f"  original_size={len(raw_output)}",
        f"  ips_found={len(entities.get('ips', []))}",
        f"  emails_found={len(entities.get('emails', []))}",
        f"  hashes_found={len(entities.get('hashes', []))}",
        f"</OUTPUT_METADATA>",
        f"<EXTRACTED_ENTITIES>",
    ]

    if entities.get("ips"):
        summary_parts.append(f"  IPs: {', '.join(entities['ips'][:20])}")
    if entities.get("emails"):
        summary_parts.append(f"  Emails: {', '.join(entities['emails'][:10])}")
    if entities.get("hashes"):
        summary_parts.append(f"  Hashes: {', '.join(entities['hashes'][:10])}")

    summary_parts.append("</EXTRACTED_ENTORIES>")
    summary_parts.append(f"<RAW_SNIPPETS>")

    # Preserve first and last 2KB for context (NOT summary)
    half = 2048
    summary_parts.append(f"# First {half} bytes:\n{raw_output[:half]}")
    summary_parts.append(f"# Last {half} bytes:\n{raw_output[-half:]}")
    summary_parts.append("</RAW_SNIPPETS>")

    return "\n".join(summary_parts)


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extracts interesting security entities using high-precision regex."""
    entities = {
        "ips": list(set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text))),
        "emails": list(
            set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text))
        ),
        "hashes": list(set(re.findall(r"\b[a-fA-F0-9]{32,64}\b", text))),
    }
    return entities
