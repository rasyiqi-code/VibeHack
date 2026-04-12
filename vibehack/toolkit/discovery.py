"""
vibehack/toolkit/discovery.py — Dynamic Tool Discovery (PRD v1.8 §6.2).

Scans $PATH at startup to find ALL security-relevant binaries — not just a
hardcoded list. This implements the principle:
  "Developer tidak diperbolehkan melakukan hardcode path eksekusi atau argumen
   dari tools keamanan di dalam kode Python maupun System Prompt."

Strategy:
  1. Walk every directory in $PATH
  2. Filter executables matching SECURITY_TOOL_PATTERNS
  3. Supplement with ~/.vibehack/bin/ (provisioned tools)
  4. Return de-duplicated sorted list
"""
import os
import re
import stat
from pathlib import Path
from functools import lru_cache

from vibehack.config import cfg

# Pattern matching security/hacking tools by name prefix/substring
# Designed to be broad — false positives are OK, false negatives are not.
SECURITY_TOOL_PATTERNS = re.compile(
    r"""
    ^(
        # Recon & Web
        nuclei|httpx|ffuf|feroxbuster|gobuster|dirb|dirbuster|
        wfuzz|arjun|subfinder|amass|assetfinder|findomain|
        dnsx|dnsprobe|naabu|masscan|rustscan|
        # Port/Net
        nmap|netcat|nc|ncat|socat|proxychains|
        # Web exploitation
        sqlmap|commix|dalfox|xsstrike|ghauri|
        # Creds & Auth
        hydra|medusa|hashcat|john|crackmapexec|netexec|
        # AD & Internal
        impacket.*|secretsdump|psexec|smbclient|rpcclient|enum4linux|
        bloodhound|sharphound|
        # Cloud
        pacu|cloudfox|scout|prowler|awscli|aws|az|gcloud|
        trivy|grype|snyk|
        # SAST & RE
        semgrep|jadx|ghidra|radare2|r2|apktool|binwalk|strings|
        # Post-exploit
        msfconsole|msf.*|meterpreter|
        # Misc security
        nikto|skipfish|openvas|zap|
        # LotL / built-in
        curl|wget|python3|ruby|perl|nc|bash|sh|
        # Exploit frameworks
        searchsploit
    )$
    """,
    re.VERBOSE | re.IGNORECASE,
)


@lru_cache(maxsize=1)
def discover_tools() -> list[str]:
    """
    Scan $PATH and ~/.vibehack/bin/ for security-relevant executables.
    Returns a sorted, de-duplicated list of binary names.
    Cached — call clear_cache() after new installs to refresh.
    """
    found: set[str] = set()

    # Scan all PATH directories
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    # Always include ~/.vibehack/bin/
    if str(cfg.BIN_DIR) not in path_dirs:
        path_dirs.append(str(cfg.BIN_DIR))

    for dir_str in path_dirs:
        dir_path = Path(dir_str)
        if not dir_path.is_dir():
            continue
        try:
            for entry in dir_path.iterdir():
                if not entry.is_file():
                    continue
                # Check executable bit
                try:
                    if not os.access(entry, os.X_OK):
                        continue
                except OSError:
                    continue
                name = entry.name
                if SECURITY_TOOL_PATTERNS.match(name):
                    found.add(name)
        except PermissionError:
            continue

    return sorted(found)


def clear_discovery_cache():
    """Clear the lru_cache so tools are re-discovered after a new install."""
    discover_tools.cache_clear()


def get_tools_context_string(tools: list[str] = None) -> str:
    """Return a compact string summarising available tools for the system prompt."""
    if tools is None:
        tools = discover_tools()
    if not tools:
        return "No security tools found. Using POSIX built-ins only."
    return ", ".join(f"`{t}`" for t in tools)
