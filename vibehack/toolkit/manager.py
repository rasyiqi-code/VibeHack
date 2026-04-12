"""
vibehack/toolkit/manager.py — Manages ~/.vibehack/bin/ and the session PATH.
"""
import os
import shutil
from pathlib import Path
from vibehack.config import cfg


def ensure_bin_dir() -> Path:
    """Ensure the ~/.vibehack/bin directory exists."""
    cfg.BIN_DIR.mkdir(parents=True, exist_ok=True)
    return cfg.BIN_DIR


def get_toolkit_env() -> dict:
    """Returns a modified environment dict with ~/.vibehack/bin prepended to PATH."""
    env = os.environ.copy()
    bin_path = str(cfg.BIN_DIR)
    current_path = env.get("PATH", "")
    if bin_path not in current_path.split(os.pathsep):
        env["PATH"] = f"{bin_path}{os.pathsep}{current_path}"
    return env


def is_tool_installed(binary_name: str) -> bool:
    """Check if a tool is available in ~/.vibehack/bin or the system PATH."""
    vh_bin = cfg.BIN_DIR / binary_name
    if vh_bin.exists() and os.access(vh_bin, os.X_OK):
        return True
    return shutil.which(binary_name) is not None


def get_tool_path(binary_name: str) -> str | None:
    """Return the full path to a tool binary, or None if not found."""
    vh_bin = cfg.BIN_DIR / binary_name
    if vh_bin.exists() and os.access(vh_bin, os.X_OK):
        return str(vh_bin)
    return shutil.which(binary_name)


# Re-export for legacy compat (loop.py uses VIBEHACK_HOME, BIN_DIR)
VIBEHACK_HOME = cfg.HOME
BIN_DIR = cfg.BIN_DIR
