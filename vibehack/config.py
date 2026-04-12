"""
vibehack/config.py — Centralised configuration loader.

All runtime settings loaded from environment variables / .env file.
Import this module to access config values instead of calling os.getenv() everywhere.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── LLM ───────────────────────────────────────────────────────────────
    API_KEY: str = os.getenv("VH_API_KEY", "")
    API_BASE: str = os.getenv("VH_API_BASE", "") # Empty = default fallback to generic provider base
    MODEL: str = os.getenv("VH_MODEL", "openrouter/anthropic/claude-3.5-sonnet")
    API_TIMEOUT: int = int(os.getenv("VH_API_TIMEOUT", "60"))
    MAX_RETRIES: int = int(os.getenv("VH_MAX_RETRIES", "3"))

    # ── Session ───────────────────────────────────────────────────────────
    MAX_TURN_MEMORY: int = int(os.getenv("VH_MAX_TURNS", "10"))
    TRUNCATE_LIMIT: int = int(os.getenv("VH_TRUNCATE_LIMIT", "2500"))
    CMD_TIMEOUT: int = int(os.getenv("VH_CMD_TIMEOUT", "120"))

    # ── Paths ─────────────────────────────────────────────────────────────
    HOME: Path = Path.home() / ".vibehack"
    BIN_DIR: Path = HOME / "bin"
    SESSIONS_DIR: Path = HOME / "sessions"
    REPORTS_DIR: Path = HOME / "reports"
    MEMORY_DB: Path = HOME / "memory.db"

    # ── Features ──────────────────────────────────────────────────────────
    MEMORY_ENABLED: bool = os.getenv("VH_NO_MEMORY", "false").lower() != "true"
    TELEMETRY_ENABLED: bool = os.getenv("VH_TELEMETRY", "false").lower() == "true"
    SANDBOX_ENABLED: bool = os.getenv("VH_SANDBOX", "false").lower() == "true"


cfg = Config()
