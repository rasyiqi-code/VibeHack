import os
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

def get_gemini_info() -> Dict[str, Any]:
    """Search for official provider API key, model, and OAuth session."""
    info = {
        "key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        "model": os.getenv("GEMINI_MODEL"),
        "auth_file": None,
        "mode": "key"
    }
    
    path = Path.home() / ".gemini"
    
    # Check for OAuth session (Higher Priority for 'Auth to CLI')
    oauth_file = path / "oauth_creds.json"
    if oauth_file.exists():
        info["auth_file"] = str(oauth_file)
        info["mode"] = "oauth"
        try:
            with open(oauth_file, "r") as f:
                data = json.load(f)
                info["key"] = data.get("access_token")
        except:
            pass
            
    # Fallback to key discovery if OAuth not found or for additional info
    env_file = path / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    k_clean = k.strip()
                    v_clean = v.strip().strip('"').strip("'")
                    if not info["key"] and k_clean in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
                        info["key"] = v_clean
                    if not info["model"] and k_clean == "GEMINI_MODEL":
                        info["model"] = v_clean
                        
    settings = path / "settings.json"
    if settings.exists():
        try:
            data = json.load(open(settings))
            if not info["key"]:
                info["key"] = data.get("api_key") or data.get("google_api_key")
            if not info["model"]:
                m = data.get("model")
                info["model"] = m.get("name") if isinstance(m, dict) else m
        except:
            pass
            
    return info

def get_claude_info() -> Dict[str, Any]:
    """Search for advanced provider credentials and model."""
    info = {
        "key": os.getenv("ANTHROPIC_API_KEY"),
        "model": os.getenv("ANTHROPIC_MODEL"),
        "auth_file": None,
        "mode": "key"
    }
    
    path = Path.home() / ".claude" / ".credentials.json"
    if path.exists():
        info["auth_file"] = str(path)
        info["mode"] = "oauth"
        try:
            data = json.load(open(path))
            info["key"] = data.get("accessToken") or data.get("api_key")
        except:
            pass
    return info

def get_codex_info() -> Dict[str, Any]:
    """Search for standard provider auth and model."""
    info = {
        "key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("OPENAI_MODEL"),
        "auth_file": None,
        "mode": "key"
    }
    
    path = Path.home() / ".codex" / "auth.json"
    if path.exists():
        info["auth_file"] = str(path)
        info["mode"] = "oauth"
        try:
            data = json.load(open(path))
            info["key"] = data.get("access_token") or data.get("api_key")
        except:
            pass
            
    config_path = Path.home() / ".codex" / "config.toml"
    if not info["model"] and config_path.exists():
        try:
            with open(config_path, "r") as f:
                for line in f:
                    if "default_model" in line or "model =" in line:
                        info["model"] = line.split("=")[-1].strip().strip('"')
        except:
            pass
            
    return info

def get_github_info() -> Dict[str, Any]:
    """Search for platform-specific token and model."""
    info = {
        "key": os.getenv("COPILOT_GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"),
        "model": os.getenv("COPILOT_MODEL"),
        "auth_file": None,
        "mode": "key"
    }
    
    path = Path.home() / ".config" / "gh" / "hosts.yml"
    if path.exists():
        info["auth_file"] = str(path)
        info["mode"] = "oauth"
        try:
            data = yaml.safe_load(open(path))
            for host in data.values():
                if "oauth_token" in host:
                    info["key"] = host["oauth_token"]
                    break
        except:
            pass
            
    return info

def get_opencode_info() -> Dict[str, Any]:
    """Search for external tool auth and model."""
    info = {"key": None, "model": None, "auth_file": None, "mode": "key"}
    path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if path.exists():
        info["auth_file"] = str(path)
        info["mode"] = "oauth"
        try:
            data = json.load(open(path))
            for p in data.values():
                if isinstance(p, dict) and "api_key" in p:
                    info["key"] = p["api_key"]
                    info["model"] = p.get("model")
                    break
        except:
            pass
    return info
