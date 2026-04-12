import re
from typing import Optional

# The "Terminal Sins" — commands that could destroy the host OS or exfiltrate unintended data.
# NOTE: This blocklist is acknowledged to be a passive defense, not a perfect guardrail.
# Obfuscated or indirect execution may bypass these patterns — Human-in-the-Loop is the true firewall.
DANGEROUS_PATTERNS = [
    # Recursive deletion (Linux)
    r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+).*(/|\*|~)",
    # Disk operations
    r"mkfs\.",
    r"dd\s+if=(/.+|/dev/)",
    r">\s*/dev/sd[a-z]",
    r">\s*/dev/nvme",
    # Permission bombers
    r"chmod\s+-R\s+(777|000)\s+/",
    r"chmod\s+(777|000)\s+-R\s+/",
    # Fork bomb
    r":\(\)\s*\{\s*:|:\s*&\s*\}\s*;:\s*",
    # System halt/reboot
    r"shutdown\s+(-[a-zA-Z]\s+)?now",
    r"reboot\s*(--force)?",
    r"init\s+[06]\b",
    r"systemctl\s+(poweroff|halt|reboot)",
    # Windows destructive commands
    r"format\s+[a-zA-Z]:",
    r"del\s+/[fFsS]\s+/[fFsS]",
    # Pipe-to-shell download execution (supply chain)
    r"(curl|wget)\s+.+\|\s*(sudo\s+)?(ba)?sh",
    r"(curl|wget)\s+.+\|\s*(sudo\s+)?python",
    # Direct disk exfiltration/wipe via netcat
    r"(cat|dd)\s+/dev/[a-z]+.+\|\s*nc\s+",
]

def check_command(command: str, unchained: bool = False) -> Optional[str]:
    """
    Scans a command against the dangerous patterns list.
    If unchained is True, it returns None (bypassed).
    """
    if unchained:
        return None
    
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"Blocked by guardrails (Pattern matched: {pattern})"
    
    return None

def check_target(target: str) -> Optional[str]:
    """
    Sanity check for the target domain.
    Prevents accidental attacks on major public services.
    """
    blocked_suffixes = [".gov", ".mil", ".edu", "google.com", "facebook.com", "amazon.com", "microsoft.com", "apple.com"]
    
    for suffix in blocked_suffixes:
        if target.lower().endswith(suffix) or f"{suffix}/" in target.lower():
            return f"Target sanity check failed: {suffix} is a restricted domain."
            
    return None
