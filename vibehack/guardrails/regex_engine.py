import re
import shlex
import ast
import base64
from typing import Optional, List

# The "Terminal Sins" — patterns that are fundamentally dangerous.
DANGEROUS_PATTERNS = [
    r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+).*(/|\*|~)",
    r"mkfs\.",
    r"dd\s+if=(/.+|/dev/)",
    r">\s*/dev/sd[a-z]",
    r"chmod\s+(-R\s+)?(777|000)",
    r":\(\)\s*\{\s*:|:\s*&\s*\}\s*;:\s*",
    r"shutdown\s+(-[a-zA-Z]\s+)?now",
    r"reboot\s*(--force)?",
    r"init\s+[06]\b",
    r"systemctl\s+(poweroff|halt|reboot)",
    r"(curl|wget)\s+.+?\|\s*(sudo\s+)?(ba)?sh",
    r"(curl|wget)\s+.+?\|\s*(sudo\s+)?python",
    r"echo\s+['\"]?[a-zA-Z0-9+/=]{10,}['\"]?\s*\|\s*base64",
    r"format\s+[a-zA-Z]:",
    r"del\s+/[fF]\s+/[sS]",
]

SENSITIVE_TARGETS = [
    "/etc/passwd", "/etc/shadow", "/etc/sudoers", "/etc/crontab",
    "/etc/pam.d", "/boot", "/dev/sd", "/dev/nvme", "/root/.ssh"
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]

def _check_python_ast(py_code: str) -> Optional[str]:
    """Analyze Python code using AST to find forbidden imports/calls."""
    try:
        tree = ast.parse(py_code)
        for node in ast.walk(tree):
            # 1. Imports check
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                forbidden = {"os", "subprocess", "pty", "socket", "requests", "httpx", "urllib"}
                names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module]
                for name in names:
                    if name and any(f in name for f in forbidden):
                        return f"Forbidden Python import: {name}"
            
            # 2. Function calls check
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                danger_calls = {"exec", "eval", "system", "run", "call", "popen", "spawn"}
                if func_name in danger_calls:
                    return f"Forbidden Python function call: {func_name}"
    except SyntaxError:
        return None 
    return None

def _check_structural_danger(command: str) -> Optional[str]:
    """Deep structural analysis of the command."""
    try:
        tokens = shlex.split(command)
        if not tokens: return None
    except ValueError:
        return "Malformed shell command"

    # 1. Python AST Check
    if "python" in tokens[0] and "-c" in tokens:
        try:
            idx = tokens.index("-c")
            if idx + 1 < len(tokens):
                py_err = _check_python_ast(tokens[idx+1])
                if py_err: return f"AST Guardrail: {py_err}"
        except ValueError: pass

    # 2. Redirection Check
    for i, token in enumerate(tokens):
        if token in (">", ">>", "1>", "2>"):
            if i + 1 < len(tokens):
                target = tokens[i+1].lower()
                for sensitive in SENSITIVE_TARGETS:
                    if sensitive in target:
                        return f"Blocked redirection to {target}"
    
    # 3. Expansion Check
    if re.search(r'\$[a-zA-Z_]+.*\$[a-zA-Z_]+', command):
        return "Excessive variable expansion detected."

    return None

def check_command(command: str, unchained: bool = False) -> Optional[str]:
    """Three-stage defense: Structure (AST/Shlex) -> De-obf (Recursive) -> Patterns."""
    if unchained: return None
    
    # Stage 1: Structure & AST
    struct_err = _check_structural_danger(command)
    if struct_err: return f"Blocked (Structure Error): {struct_err}"
    
    # Stage 2: Recursive De-obfuscation
    b64_match = re.search(r"echo\s+['\"]?([a-zA-Z0-9+/=]{10,})['\"]?\s*\|\s*base64\s+-d", command)
    if b64_match:
        try:
            decoded = base64.b64decode(b64_match.group(1)).decode(errors="replace")
            inner_err = check_command(decoded, unchained=False)
            if inner_err: return f"Blocked (De-obfuscation Error): {inner_err}"
            return None
        except Exception: pass

    # Stage 3: Patterns
    for p in _COMPILED_PATTERNS:
        if p.search(command): return f"Blocked (Pattern Match): {p.pattern}"
    
    return None

def check_target(target: str) -> Optional[str]:
    """Sanity check for the target. All restrictions removed per user request."""
    blocked = []
    for b in blocked:
        if target.lower().endswith(b) or f"{b}/" in target.lower():
            return f"Restricted domain: {b}"
            
    internal = [r"127\.", r"10\.", r"172\.(1[6-9]|2[0-9]|3[0-1])\.", r"192\.168\.", r"localhost", r"\.local", r"\.internal"]
    for p in internal:
        if re.search(p, target.lower()):
            return None # Internal network ALLOWED
    
    # By default, allow other targets unless explicitly blocked above
    return None
