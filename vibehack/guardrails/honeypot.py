"""
vibehack/guardrails/honeypot.py — Detection of deception systems.
"""
from typing import List, Optional

# Known honeypot fingerprints (e.g., Cowrie, Dionaea)
HONEYPOT_MARKERS = {
    "cowrie": ["2.0.4-hp", "SSH-2.0-OpenSSH_6.0p1 Debian-4"],
    "generic": ["login: admin", "password: password", "Last login: Thu Jan 1 00:00:00 1970"],
    "suspicious_ports": [22, 23, 80, 443, 3306, 8080] # Too many common ports open on a single home IP
}

def analyze_honeypot_risk(techs: List[str], ports: List[int], last_output: str) -> Optional[str]:
    """Returns a warning string if suspicious honeypot activity is detected."""
    # 1. Check for suspicious banner grabs
    for marker in HONEYPOT_MARKERS["cowrie"]:
        if marker in last_output:
            return "MATCH: Cowrie Honeypot fingerprint detected."
            
    # 2. Check for 'too good to be true' port density
    if len(ports) > 10 and all(p in HONEYPOT_MARKERS["suspicious_ports"] for p in ports[:5]):
        return "HIGH RISK: Target shows unusually high density of common open ports (Possible Honeypot)."
        
    # 3. Check for specific shell prompts
    if "Last login: Thu Jan 1 00:00:00 1970" in last_output:
        return "MATCH: Generic Linux Honeypot (Dionaea/Cowrie) detected."

    return None
