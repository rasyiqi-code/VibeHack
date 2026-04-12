import os
import json
import yaml
from pathlib import Path
from typing import Optional, Tuple

def find_gemini_key() -> Tuple[Optional[str], Optional[str]]:
    """Search for Gemini API key and model."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = os.getenv("GEMINI_MODEL")
    
    path = Path.home() / ".gemini"
    
    # Check .env if key/model not in actual env
    env_file = path / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    k_clean = k.strip()
                    v_clean = v.strip().strip('"').strip("'")
                    if not key and k_clean in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
                        key = v_clean
                    if not model and k_clean == "GEMINI_MODEL":
                        model = v_clean
                        
    # Check settings.json
    settings = path / "settings.json"
    if settings.exists():
        try:
            data = json.load(open(settings))
            if not key:
                key = data.get("api_key") or data.get("google_api_key")
            if not model:
                model = data.get("model")
                if isinstance(model, dict):
                    model = model.get("name")
        except:
            pass
            
    return key, model

def find_claude_key() -> Tuple[Optional[str], Optional[str]]:
    """Search for Claude Code credentials and model."""
    key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL")
    
    path = Path.home() / ".claude" / ".credentials.json"
    if path.exists():
        try:
            data = json.load(open(path))
            if not key:
                key = data.get("accessToken") or data.get("api_key")
            # Usually Claude CLI stores model in a separate config or uses Sonnet 3.5
            # We'll stick to Sonnet if not found
        except:
            pass
    return key, model

def find_codex_key() -> Tuple[Optional[str], Optional[str]]:
    """Search for ChatGPT Codex auth and model."""
    key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL") # Custom check
    
    path = Path.home() / ".codex" / "auth.json"
    if path.exists():
        try:
            data = json.load(open(path))
            if not key:
                key = data.get("access_token") or data.get("api_key")
        except:
            pass
            
    # Check config.toml for model
    config_path = Path.home() / ".codex" / "config.toml"
    if not model and config_path.exists():
        try:
            # Simple line parsing for toml to avoid extra deps if possible
            # But we already have PyYAML, maybe toml should be there too? 
            # For now, let's just grep style
            with open(config_path, "r") as f:
                for line in f:
                    if "default_model" in line or "model =" in line:
                        model = line.split("=")[-1].strip().strip('"')
        except:
            pass
            
    return key, model

def find_github_token() -> Tuple[Optional[str], Optional[str]]:
    """Search for GitHub token and model."""
    token = os.getenv("COPILOT_GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    model = os.getenv("COPILOT_MODEL")

    # gh cli config
    path = Path.home() / ".config" / "gh" / "hosts.yml"
    if path.exists():
        try:
            data = yaml.safe_load(open(path))
            for host in data.values():
                if "oauth_token" in host:
                    token = host["oauth_token"]
                    break
        except:
            pass
            
    return token, model

def find_opencode_key() -> Tuple[Optional[str], Optional[str]]:
    """Search for OpenCode auth and model."""
    key = None
    model = None
    path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if path.exists():
        try:
            data = json.load(open(path))
            for p in data.values():
                if isinstance(p, dict) and "api_key" in p:
                    key = p["api_key"]
                    model = p.get("model")
                    break
        except:
            pass
    return key, model
