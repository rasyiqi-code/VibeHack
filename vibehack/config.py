import os
from pathlib import Path
from dotenv import load_dotenv

# Define Home first
VIBEHACK_HOME = Path.home() / ".vibehack"
GLOBAL_ENV = VIBEHACK_HOME / ".env"

def load_config_env():
    """Load from local .env then global ~/.vibehack/.env"""
    load_dotenv() # Local .env
    if GLOBAL_ENV.exists():
        load_dotenv(GLOBAL_ENV, override=False)

load_config_env()

class Config:
    def __init__(self):
        self.load()

    def load(self):
        # ── LLM ───────────────────────────────────────────────────────────────
        self.API_KEY = os.getenv("VH_API_KEY", "")
        self.API_BASE = os.getenv("VH_API_BASE", "")
        self.MODEL = os.getenv("VH_MODEL", "openrouter/anthropic/claude-3.5-sonnet")
        self.API_TIMEOUT = int(os.getenv("VH_API_TIMEOUT", "60"))
        self.MAX_RETRIES = int(os.getenv("VH_MAX_RETRIES", "3"))

        # ── Session ───────────────────────────────────────────────────────────
        self.MAX_TURN_MEMORY = int(os.getenv("VH_MAX_TURNS", "10"))
        self.TRUNCATE_LIMIT = int(os.getenv("VH_TRUNCATE_LIMIT", "2500"))
        self.CMD_TIMEOUT = int(os.getenv("VH_CMD_TIMEOUT", "120"))

        # ── Paths ─────────────────────────────────────────────────────────────
        self.HOME = VIBEHACK_HOME
        self.BIN_DIR = self.HOME / "bin"
        self.SESSIONS_DIR = self.HOME / "sessions"
        self.REPORTS_DIR = self.HOME / "reports"
        self.MEMORY_DB = self.HOME / "memory.db"
        self.GLOBAL_ENV = GLOBAL_ENV

        # ── Features ──────────────────────────────────────────────────────────
        self.MEMORY_ENABLED = os.getenv("VH_NO_MEMORY", "false").lower() != "true"
        self.TELEMETRY_ENABLED = os.getenv("VH_TELEMETRY", "false").lower() == "true"
        self.SANDBOX_ENABLED = os.getenv("VH_SANDBOX", "false").lower() == "true"

cfg = Config()
