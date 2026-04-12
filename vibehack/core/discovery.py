import os
import json
import yaml
from pathlib import Path
from typing import Optional

def find_gemini_key() -> Optional[str]:
    """Search for Gemini API key in local environment or config."""
    # 1. Env check
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv("GEMINI_API_KEY")
    if os.getenv("GOOGLE_API_KEY"):
        return os.getenv("GOOGLE_API_KEY")
        
    # 2. Config directory search
    path = Path.home() / ".gemini"
    # Check .env
    env_file = path / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
                        return v.strip().strip('"').strip("'")
                        
    # Check settings.json
    settings = path / "settings.json"
    if settings.exists():
        try:
            data = json.load(open(settings))
            return data.get("api_key") or data.get("google_api_key")
        except:
            pass
            
    return None

def find_claude_key() -> Optional[str]:
    """Search for Claude Code credentials."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return os.getenv("ANTHROPIC_API_KEY")
        
    path = Path.home() / ".claude" / ".credentials.json"
    if path.exists():
        try:
            data = json.load(open(path))
            return data.get("accessToken") or data.get("api_key")
        except:
            pass
    return None

def find_codex_key() -> Optional[str]:
    """Search for ChatGPT Codex auth."""
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_API_KEY")
        
    path = Path.home() / ".codex" / "auth.json"
    if path.exists():
        try:
            data = json.load(open(path))
            return data.get("access_token") or data.get("api_key")
        except:
            pass
    return None

def find_github_token() -> Optional[str]:
    """Search for GitHub token via gh cli or copilot config."""
    for env in ["COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"]:
        if os.getenv(env):
            return os.getenv(env)
            
    # gh cli config
    path = Path.home() / ".config" / "gh" / "hosts.yml"
    if path.exists():
        try:
            data = yaml.safe_load(open(path))
            # Get the first host's token (usually github.com)
            for host in data.values():
                if "oauth_token" in host:
                    return host["oauth_token"]
        except:
            pass
            
    return None

def find_opencode_key() -> Optional[str]:
    """Search for OpenCode auth."""
    path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if path.exists():
        try:
            data = json.load(open(path))
            # Try to get first available provider key
            for p in data.values():
                if isinstance(p, dict) and "api_key" in p:
                    return p["api_key"]
        except:
            pass
    return None
