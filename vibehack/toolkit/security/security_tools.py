"""
vibehack/toolkit/security/security_tools.py — Security Tools Auto-Provisioning.

Manages installation of pentesting tools from apt repository.
"""

import subprocess
import getpass
from subprocess import Popen, PIPE
from typing import Dict, List

# Standard security tools available in apt
SECURITY_TOOLS = {
    # Reconnaissance
    "nmap": {"package": "nmap", "description": "Network mapper", "category": "recon"},
    "netcat": {
        "package": "netcat-traditional",
        "description": "Swiss army knife",
        "category": "recon",
    },
    "curl": {"package": "curl", "description": "HTTP client", "category": "recon"},
    "wget": {"package": "wget", "description": "Download utility", "category": "recon"},
    # Web scanning
    "nikto": {
        "package": "nikto",
        "description": "Web server scanner",
        "category": "web",
    },
    "gobuster": {
        "package": "gobuster",
        "description": "Directory busting",
        "category": "web",
    },
    "dirb": {"package": "dirb", "description": "URL bruteforcing", "category": "web"},
    # SQL Injection
    "sqlmap": {
        "package": "sqlmap",
        "description": "SQL injection tool",
        "category": "exploit",
    },
    # Password
    "hydra": {
        "package": "hydra",
        "description": "Password cracker",
        "category": "password",
    },
    # Wireless
    "aircrack-ng": {
        "package": "aircrack-ng",
        "description": "Wireless cracker",
        "category": "wireless",
    },
}


def is_tool_available(tool_name: str) -> bool:
    """Check if tool is available in PATH."""
    result = subprocess.run(["which", tool_name], capture_output=True, text=True)
    return result.returncode == 0


def get_missing_tools(required_tools: List[str]) -> List[str]:
    """Get list of tools not installed."""
    return [
        t for t in required_tools if t in SECURITY_TOOLS and not is_tool_available(t)
    ]


def install_tool(tool_name: str, use_sudo: bool = None) -> bool:
    """Install a single tool using apt. Prompts for password if needed."""
    if tool_name not in SECURITY_TOOLS:
        return False

    package = SECURITY_TOOLS[tool_name]["package"]

    # Try without sudo first
    result = subprocess.run(
        ["apt-get", "install", "-y", package],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        return True

    if use_sudo is False:
        return False

    # Try with sudo password prompt
    try:
        sudo_password = getpass.getpass("⚠️ Tool installation requires sudo password: ")
        proc = Popen(
            ["sudo", "-S", "apt-get", "install", "-y", package],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input=sudo_password + "\n", timeout=180)
        return proc.returncode == 0
    except Exception:
        return False


def install_tools_batch(tools: List[str], use_sudo: bool = None) -> Dict[str, bool]:
    """Install multiple tools at once."""
    packages = list(
        set(SECURITY_TOOLS[t]["package"] for t in tools if t in SECURITY_TOOLS)
    )
    if not packages:
        return {t: False for t in tools}

    result = subprocess.run(
        ["apt-get", "install", "-y"] + packages,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode == 0:
        return {t: True for t in tools}

    if use_sudo is False:
        return {t: False for t in tools}

    try:
        sudo_password = getpass.getpass("⚠️ Tool installation requires sudo password: ")
        proc = Popen(
            ["sudo", "-S", "apt-get", "install", "-y"] + packages,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        proc.communicate(input=sudo_password + "\n", timeout=300)
        return {t: is_tool_available(t) for t in tools}
    except Exception:
        return {t: False for t in tools}


def ensure_tools(
    tools: List[str], auto_install: bool = True, use_sudo: bool = None
) -> Dict[str, bool]:
    """Ensure required tools are available."""
    missing = get_missing_tools(tools)
    if not missing:
        return {t: True for t in tools}
    if auto_install:
        return install_tools_batch(missing, use_sudo)
    return {t: False for t in missing}


def install_common_tools(use_sudo: bool = None) -> bool:
    """Install most common pentesting tools."""
    common = ["nmap", "curl", "wget", "nikto", "gobuster", "dirb", "sqlmap", "netcat"]
    results = ensure_tools(common, auto_install=True, use_sudo=use_sudo)
    return all(results.values())


def check_tool_availability(tool_names: List[str]) -> Dict[str, bool]:
    """Quick check if tools are available."""
    return {t: is_tool_available(t) for t in tool_names}
