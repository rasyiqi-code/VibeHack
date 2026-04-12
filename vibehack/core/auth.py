import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Public Client ID from Gemini CLI (Community known)
DEFAULT_CLIENT_CONFIG = {
    "installed": {
        "client_id": "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        "project_id": "gemini-cli",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["http://localhost"]
    }
}

SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

def start_google_login(save_path: Path) -> Optional[Dict[str, Any]]:
    """Perform interactive Google OAuth2 login and save credentials."""
    try:
        flow = InstalledAppFlow.from_client_config(
            DEFAULT_CLIENT_CONFIG,
            scopes=SCOPES
        )
        
        # run_local_server will open the browser
        print("\n[VibeHack] Opening browser for Google Sign-in...")
        creds = flow.run_local_server(port=0, success_message="Auth successful! You can close this tab.")
        
        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save credentials as JSON
        creds_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
            "expiry": creds.expiry.isoformat() if creds.expiry else None
        }
        
        # We also want to match the format expected by our UniversalHandler
        # which looks for 'access_token' and 'refresh_token' primarily.
        compat_data = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "scope": " ".join(creds.scopes),
            "token_type": "Bearer",
            "client_id": creds.client_id,
            "client_secret": creds.client_secret
        }
        
        with open(save_path, "w") as f:
            json.dump(compat_data, f, indent=2)
            
        return compat_data
    except Exception as e:
        print(f"\n[ERROR] Login failed: {e}")
        return None
