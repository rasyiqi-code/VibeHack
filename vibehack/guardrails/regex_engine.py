import re
import shlex
from typing import Optional, List

# The "Terminal Sins" — commands that could destroy the host OS or exfiltrate unintended data.
# Note: These regex patterns are now the second line of defense after structural analysis.
DANGEROUS_PATTERNS = [
    # Recursive deletion (Linux)
    r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+).*(/|\*|~)",
    # Disk operations
    r"mkfs\.",
    r"dd\s+if=(/.+|/dev/)",
    r">\s*/dev/sd[a-z]",
    r">\s*/dev/nvme",
    # Permission bombers
    r"chmod\s+(-R\s+)?(777|000)",
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
    r"(curl|wget)\s+.+?\|\s*(sudo\s+)?(ba)?sh",
    r"(curl|wget)\s+.+?\|\s*(sudo\s+)?python",
    # Direct disk exfiltration/wipe via netcat
    r"(cat|dd)\s+/dev/[a-z]+.+\|\s*nc\s+",
]

# Sensitive system files/directories that should NEVER be targets of shell redirection
SENSITIVE_TARGETS = [
    "/etc/passwd", "/etc/shadow", "/etc/sudoers", "/etc/crontab",
    "/etc/pam.d", "/boot", "/dev/sd", "/dev/nvme", "/root/.ssh"
]

_COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS]

def _check_structural_danger(command: str) -> Optional[str]:
    """
    Parses the command to detect shell manipulation techniques 
    like redirection and basic obfuscation.
    """
    # 0. Basic bash substitution expansion obfuscation (e.g., r=r; m=m; $r$m -f /)
    if re.search(r'\$[a-zA-Z_]+.*\$[a-zA-Z_]+', command):
        return "Blocked by pattern guardrails: Excessive variable expansion detected."

    try:
        # Use shlex to handle quotes correctly
        parts = shlex.split(command)
        if not parts:
            return None
        
        # 1. Redirection Check (e.g., command > /etc/passwd)
        for i, part in enumerate(parts):
            if part in (">", ">>", "1>", "2>"):
                if i + 1 < len(parts):
                    target = parts[i+1].lower()
                    for sensitive in SENSITIVE_TARGETS:
                        if sensitive in target:
                            return f"Attempted redirection to sensitive path: {target}"
        
        # 2. Obfuscated Execution Check (eval, sh -c with suspicious vars)
        if "eval" in command.lower() or "sh -c" in command.lower():
            if "$" in command or "`" in command:
                return "Potential shell execution obfuscation detected."

    except ValueError:
        # Allow commands with unclosed quotes (often used legitimately in fuzzing/scanning)
        # We rely on regex patterns instead for safety here
        pass
    except Exception:
        return "Command structure is too complex or malformed for safety audit."
    
    return None

def check_command(command: str, unchained: bool = False) -> Optional[str]:
    """
    Multi-stage command verification:
    1. Structural Analysis (shlex)
    2. Regex Pattern Matching
    """
    if unchained:
        return None
    
    # Stage 1: Structure
    struct_error = _check_structural_danger(command)
    if struct_error:
        return f"Blocked by structural guardrails: {struct_error}"
    
    # Stage 2: Patterns
    for compiled_pattern in _COMPILED_PATTERNS:
        if compiled_pattern.search(command):
            return f"Blocked by pattern guardrails: {compiled_pattern.pattern}"
    
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
