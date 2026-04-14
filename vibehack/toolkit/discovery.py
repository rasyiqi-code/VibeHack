"""
vibehack/toolkit/discovery.py — Pure Agnostic Dynamic Discovery.

Scans the system without bias. VibeHack does not filter for 'security' tools.
Everything that is executable is visible to the AI.
"""
import os
from pathlib import Path
from functools import lru_cache
from vibehack.config import cfg

@lru_cache(maxsize=1)
def discover_tools() -> list[str]:
    """
    Scan $PATH and ~/.vibehack/bin/ for ALL executable files.
    No filters. No bias.
    """
    found: set[str] = set()
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)

    if cfg.BIN_DIR.exists():
        path_dirs.append(str(cfg.BIN_DIR))

    for dir_str in path_dirs:
        dir_path = Path(dir_str)
        if not dir_path.is_dir():
            continue
        try:
            for entry in dir_path.iterdir():
                if entry.is_file() and os.access(entry, os.X_OK):
                    found.add(entry.name)
        except (PermissionError, OSError):
            continue

    return sorted(found)

def clear_discovery_cache():
    discover_tools.cache_clear()

def get_tools_context_string(tools: list[str] = None) -> str:
    """Return a summary of WHATEVER is available in the environment."""
    if tools is None:
        tools = discover_tools()
    
    # We truncate the list if it's too long to save tokens, 
    # but we don't filter it by name.
    if len(tools) > 150:
        return ", ".join(f"`{t}`" for t in tools[:150]) + " ... (and more)"
    return ", ".join(f"`{t}`" for t in tools)

def check_tool_exists(command_name: str) -> bool:
    import shutil
    base_cmd = command_name.split()[0] if command_name else ""
    return shutil.which(base_cmd) is not None

def get_tool_status(tool_name: str) -> str:
    if check_tool_exists(tool_name):
        return "installed"
    return "missing" # No longer 'provisionable' as we don't have a registry.
