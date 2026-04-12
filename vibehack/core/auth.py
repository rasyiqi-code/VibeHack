import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import urllib.parse
import requests
import hashlib
import base64
import secrets

def _get_client_config() -> Dict[str, Any]:
    """Retrieve Google OAuth client configuration from local file or default."""
    from vibehack.config import cfg
    path = cfg.HOME / "client_secrets.json"
    
    default_config = {
        "installed": {
            "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
            "client_secret": "GOCSPX-S5S4Vv054Gis-8kI-Z6LdJ1UvI0",
            "project_id": "gemini-cli",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"]
        }
    }
    
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default_config
            
    # Auto-generate if missing
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(default_config, f, indent=2)
    except Exception:
        pass
        
    return default_config

SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

def manual_google_login(save_path: Path) -> Optional[Dict[str, Any]]:
    """Interactive Google OAuth2 login via manual URL pasting with PKCE."""
    from rich.prompt import Prompt
    from rich.console import Console
    console = Console()
    
    config = _get_client_config()
    client_id = config["installed"]["client_id"]
    client_secret = config["installed"]["client_secret"]
    
    # ── PKCE Generation (OpenClaw Match: HEX 32 bytes) ──────────────
    code_verifier = secrets.token_hex(32)
    # Code Challenge: SHA256 of hex verifier, then base64url encoded
    challenge_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_hash).decode('ascii').replace('=', '')
    
    # Generate the auth URL - Matching OpenClaw's exact structure & order
    params = [
        ("client_id", client_id),
        ("redirect_uri", "http://localhost:58765/"),
        ("response_type", "code"),
        ("scope", " ".join(SCOPES)),
        ("access_type", "offline"),
        ("prompt", "consent"),
        ("code_challenge", code_challenge),
        ("code_challenge_method", "S256"),
    ]
    
    query = urllib.parse.urlencode(params)
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    
    console.print("\n[bold blue]🌐 OpenClaw-Style Manual Login (PKCE Enabled)[/bold blue]")
    console.print("1. Salalin link ini ke browser Anda:")
    console.print(f"\n[cyan]{auth_url}[/cyan]\n")
    console.print("2. Login seperti biasa.")
    console.print("3. Browser akan mengarah ke halaman '[bold red]Site can't be reached[/bold red]' atau '[bold yellow]localhost error[/bold yellow]'.")
    console.print("4. [bold green]Salin (COPY) seluruh URL halaman error tersebut[/bold green] lalu tempel di sini.")
    
    pasted_url = Prompt.ask("\n➤ Tempel URL Redirect di sini")
    
    if not pasted_url:
        return None
        
    code = extract_code_from_url(pasted_url)
    if not code:
        console.print("[red]❌ Gagal menemukan kode autentikasi di URL tersebut.[/red]")
        return None
        
    console.print("[yellow]⏳ Menukarkan kode dengan token...[/yellow]")
    return exchange_code_for_token(code, client_id, client_secret, code_verifier, save_path)

def extract_code_from_url(url: str) -> Optional[str]:
    """Extracts 'code' parameter from the redirect URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        return params.get("code", [None])[0]
    except Exception:
        return None

def exchange_code_for_token(code: str, client_id: str, client_secret: str, code_verifier: str, save_path: Path) -> Optional[Dict[str, Any]]:
    """Exchanges auth code for real tokens with PKCE verifier."""
    try:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": code_verifier,
            "redirect_uri": "http://localhost:58765/",
            "grant_type": "authorization_code"
        }
        
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        tokens = response.json()
        
        # Save credentials
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        compat_data = {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "scope": tokens.get("scope"),
            "token_type": tokens.get("token_type", "Bearer"),
            "client_id": client_id,
            "client_secret": client_secret,
            "expires_in": tokens.get("expires_in")
        }
        
        with open(save_path, "w") as f:
            json.dump(compat_data, f, indent=2)
            
        return compat_data
    except Exception as e:
        from rich.console import Console
        Console().print(f"[red]❌ Gagal menukarkan token: {e}[/red]")
        if hasattr(e, 'response') and e.response:
             Console().print(f"[dim]Detail: {e.response.text}[/dim]")
        return None
