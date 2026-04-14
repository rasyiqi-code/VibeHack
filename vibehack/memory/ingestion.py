"""
vibehack/memory/ingestion.py — End-of-session memory ingestion.

Extracts meaningful "experiences" from a finished session's conversation history
and writes them to the local LTM database. This is the "learning" step.

Patterns extracted:
  - Commands that produced findings → score +1 (success)
  - Commands that errored / yielded nothing useful → score -1 (failure)
  - Technology hints detected from output (express, nginx, spring, etc.)
"""

import json
import re
from typing import List, Dict
from vibehack.memory.db import record_experiences
from vibehack.llm.provider import Finding

def detect_technologies(text: str) -> List[str]:
    """Dynamically detect technologies from headers, banners, or patterns."""
    found = set()
    
    # Generic Server & Powered-By Headers
    server_matches = re.findall(r"Server:\s+([a-zA-Z0-9\-_]+)", text, re.IGNORECASE)
    found.update([s.lower() for s in server_matches])
    
    powered_matches = re.findall(r"X-Powered-By:\s+([a-zA-Z0-9\-_]+)", text, re.IGNORECASE)
    found.update([p.lower() for p in powered_matches])

    # Universal Technology/Banner extraction pattern: Name/1.2.3 or Name_1.2.3 or Name 1.2.3
    # We ensure the name starts with a letter to avoid capturing protocol versions like 1.1/HTTP as tech
    generic_banner = re.compile(r"([a-zA-Z][a-zA-Z0-9\-_]{2,})[/_\s](\d+\.[\d\.a-z\-]+)", re.IGNORECASE)
    for m in generic_banner.finditer(text):
        tech_name = m.group(1).lower()
        if tech_name not in ["http", "https", "tcp", "udp", "port", "server", "ok"]:
            found.add(tech_name)
            
    return list(found) if found else ["unknown"]


def ingest_session(
    target: str,
    history: List[Dict[str, str]],
    findings: List[Finding],
) -> int:
    """
    Parse session history and write learned experiences to LTM.
    Returns the number of experiences recorded.
    """
    recorded = 0
    turns = []

    # Convert history into paired (assistant, user_feedback) turns
    i = 0
    while i < len(history):
        msg = history[i]
        if msg["role"] == "assistant":
            try:
                agent_data = json.loads(msg["content"])
            except (json.JSONDecodeError, TypeError):
                i += 1
                continue

            # Look ahead for the user response (tool output)
            user_feedback = ""
            if i + 1 < len(history) and history[i + 1]["role"] == "user":
                user_feedback = history[i + 1]["content"]

            turns.append((agent_data, user_feedback))
        i += 1

    # Record experiences based on exit codes and finding correlation
    experiences_to_record = []
    for agent_data, feedback in turns:
        command = agent_data.get("raw_command")
        thought = agent_data.get("thought", "")
        if not command:
            continue

        techs = detect_technologies(thought + feedback)
        exit_code_match = re.search(r"EXIT_CODE:\s*(\d+)", feedback)
        exit_code = int(exit_code_match.group(1)) if exit_code_match else -1
        stdout_snippet = feedback[:300] if feedback else ""

        # Determine if this command contributed to a finding
        is_successful = False
        for finding in findings:
            if command in (finding.evidence or "") or command[:30] in (finding.description or ""):
                is_successful = True
                break

        if not is_successful and exit_code == 0 and len(stdout_snippet) > 50:
            is_successful = True

        score = 1 if is_successful else -1
        summary = f"{command[:80]}... → exit:{exit_code}"

        # Record once for each tech found to improve LTM search results
        for t in techs:
            experiences_to_record.append((target, t, command[:500], score, summary))

    recorded = record_experiences(experiences_to_record)

    return recorded
