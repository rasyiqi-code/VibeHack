import os
from pathlib import Path
from dotenv import load_dotenv
from vibehack.core.keyring_mgr import get_api_key

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

        # Provider Keys (Env Var > Keyring)
        self.OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY") or get_api_key("openrouter") or ""
        self.GOOGLE_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or get_api_key("google") or ""
        self.ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY") or get_api_key("anthropic") or ""
        self.OPENAI_KEY = os.getenv("OPENAI_API_KEY") or get_api_key("openai") or ""
        self.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or get_api_key("github") or ""
        
        # Primary key mapping
        self.API_KEY = os.getenv("VH_API_KEY") or get_api_key("primary") or ""

        # ── Token Economy & Context (v2.6) ───────────────────────────────────
        self.MAX_TURN_MEMORY = int(os.getenv("VH_MAX_TURNS", "10"))
        self.TRUNCATE_LIMIT = int(os.getenv("VH_TRUNCATE_LIMIT", "4000"))
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

        # ── Load Default Models from JSON ────────────────────────────────────
        self.DEFAULTS = {}
        defaults_path = Path(__file__).parent / "llm" / "defaults.json"
        if defaults_path.exists():
            import json
            try:
                with open(defaults_path, "r") as f:
                    self.DEFAULTS = json.load(f)
            except Exception:
                pass
        
        self.DEFAULT_MODELS = self.DEFAULTS.get("default_models", {})
        self.PRIMARY_DEFAULT = self.DEFAULTS.get("primary_default", "openrouter/anthropic/claude-3.5-sonnet")
        self.MODEL_EXAMPLE = self.DEFAULTS.get("model_example", "openai/gpt-4o")

cfg = Config()
