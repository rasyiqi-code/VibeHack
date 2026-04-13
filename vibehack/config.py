import os
from pathlib import Path
from dotenv import load_dotenv

# Define Home first
VIBEHACK_HOME = Path.home() / ".vibehack"
GLOBAL_ENV = VIBEHACK_HOME / ".env"

# Ensure home directory exists
VIBEHACK_HOME.mkdir(parents=True, exist_ok=True)

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
        # ── LLM Core ──────────────────────────────────────────────────────────
        self.PROVIDER = os.getenv("VH_PROVIDER", "openrouter")
        self.API_KEY = os.getenv("VH_API_KEY", "")
        self.API_BASE = os.getenv("VH_API_BASE", "")
        self.MODEL = os.getenv("VH_MODEL", "google/gemini-2.0-flash-exp:free")
        self.API_TIMEOUT = int(os.getenv("VH_API_TIMEOUT", "60"))
        self.MAX_RETRIES = int(os.getenv("VH_MAX_RETRIES", "3"))

        # Auth Metadata
        self.AUTH_TYPE = os.getenv("VH_AUTH_TYPE", "key") # 'key' or 'oauth'
        self.AUTH_FILE = os.getenv("VH_AUTH_FILE", "")

        # Provider Keys
        self.OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
        self.GOOGLE_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        self.ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        self.OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
        self.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN", "")

        # ── Token Economy & Context (v2.6) ───────────────────────────────────
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

        # Ensure subdirectories exist
        self.BIN_DIR.mkdir(parents=True, exist_ok=True)
        self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # ── Feature Toggles ──────────────────────────────────────────────────
        self.MEMORY_ENABLED = os.getenv("VH_NO_MEMORY", "false").lower() != "true"
        self.SANDBOX_ENABLED = os.getenv("VH_SANDBOX", "false").lower() == "true"

cfg = Config()
