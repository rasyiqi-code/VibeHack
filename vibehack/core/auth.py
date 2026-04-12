import json
import os
import shutil
import subprocess
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
    """Retrieve Google OAuth client configuration using the ultra-stable Google Cloud SDK identity."""
    from vibehack.config import cfg
    path = cfg.HOME / "client_secrets.json"
    
    # Official Google Cloud SDK IDs - Known to be stable and public
    GCLOUD_ID = "764086051780-29qc3qn746i397p5n1uS3a77Reruev0g.apps.googleusercontent.com"
    GCLOUD_SECRET = "d79Btm62_Z975S8_BbaZ_A5L"
    
    default_config = {
        "installed": {
            "client_id": GCLOUD_ID,
            "client_secret": GCLOUD_SECRET,
            "project_id": "google-cloud-sdk",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"]
        }
    }
    
    # Force overwrite if old Gemini CLI IDs were present to prevent 401
    if path.exists():
        try:
            with open(path, "r") as f:
                current = json.load(f)
                cid = current.get("installed", {}).get("client_id", "")
                if "681255809395" in cid: # Old Gemini CLI prefix
                    needs_update = True
                else:
                    return current # Use custom user config
        except Exception:
            pass

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
    
    # Generate the auth URL - response_type FIRST for maximum resilience
    params = [
        ("response_type", "code"),
        ("client_id", client_id),
        ("redirect_uri", "http://localhost:58765/"),
        ("scope", " ".join(SCOPES)),
        ("access_type", "offline"),
        ("prompt", "consent"),
        ("code_challenge", code_challenge),
        ("code_challenge_method", "S256"),
    ]
    
    # Use quote (for %20) instead of quote_plus (for +) to be more URL-standard
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    
    console.print("\n[bold blue]🌐 OpenClaw-Style Manual Login (PKCE Enabled)[/bold blue]")
    console.print("1. Salalin link ini ke browser Anda (Paling aman: [bold cyan]Ctrl+Klik[/bold cyan] link di bawah):")
    
    # Clickable link for modern terminals
    console.print(f"\n[link={auth_url}][underline cyan]{auth_url}[/underline cyan][/link]\n", soft_wrap=True)
    
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
    """Exchanges auth code for real tokens with PKCE verifier and no-secret fallback."""
    from rich.console import Console
    console = Console()
    
    token_url = "https://oauth2.googleapis.com/token"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    
    # Base params for PKCE
    base_data = {
        "code": code,
        "client_id": client_id,
        "code_verifier": code_verifier,
        "redirect_uri": "http://localhost:58765/",
        "grant_type": "authorization_code"
    }

    # Attempt 1: With Secret (Official/OpenClaw style)
    try:
        data_with_secret = base_data.copy()
        data_with_secret["client_secret"] = client_secret
        
        response = requests.post(token_url, data=data_with_secret, headers=headers)
        
        if response.status_code == 200:
            tokens = response.json()
        elif response.status_code in [400, 401]:
            # Attempt 2: Without Secret (Public Client/Gemini CLI style)
            console.print("[yellow]⚠️  Google menolak Client Secret. Mencoba metode Public Client (No-Secret)...[/yellow]")
            response = requests.post(token_url, data=base_data, headers=headers)
            
            if response.status_code == 200:
                tokens = response.json()
            else:
                console.print(f"[red]❌ Gagal menukarkan token: {response.status_code}[/red]")
                try:
                    err_data = response.json()
                    console.print(f"[dim]Google Error: {err_data.get('error')} - {err_data.get('error_description')}[/dim]")
                except:
                    console.print(f"[dim]{response.text}[/dim]")
                return None
        else:
            console.print(f"[red]❌ Unexpected Google Error: {response.status_code}[/red]")
            return None
        
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
def is_cli_installed(cmd: str) -> bool:
    """Check if a CLI command is available in PATH."""
    return shutil.which(cmd) is not None

def verify_gemini_cli_bridge() -> bool:
    """Verify if gemini-cli is authenticated and usable."""
    if not is_cli_installed("gemini"):
        return False
    
    try:
        # Check if authenticated/usable by getting version
        process = subprocess.Popen(
            ["gemini", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        _, _ = process.communicate(timeout=5)
        return process.returncode == 0
    except Exception:
        return False

def run_gemini_bridge(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Run prompt via official gemini CLI subprocess."""
    from rich.console import Console
    console = Console()
    
    args = ["gemini"]
    if model:
        # Strip LiteLLM prefixes for official CLI compatibility
        clean_model = model.replace("gemini/", "").replace("vertex_ai/", "")
        args.extend(["--model", clean_model])
    
    # Add prompt as a single argument for one-shot execution
    args.append(prompt)
    
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(timeout=120)
        
        if process.returncode != 0:
            console.print(f"[bold red]Bridge Error:[/bold red] {stderr}")
            return None
            
        return stdout.strip()
    except subprocess.TimeoutExpired:
        process.kill()
        console.print(f"[bold red]Bridge Exception:[/bold red] Command '{args}' timed out after 120 seconds")
        return None
    except Exception as e:
        console.print(f"[bold red]Bridge Exception:[/bold red] {str(e)}")
        return None
