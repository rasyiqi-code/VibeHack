"""
vibehack/llm/google_auth.py — Google OAuth hijacking and ADC synchronization.
"""
import os
import json
from typing import Optional, Any
from rich.console import Console
from vibehack.config import cfg

console = Console()

class GoogleAuthHandler:
    """Handles hijacked Google CLI session credentials."""
    def __init__(self, auth_file: str):
        self.auth_file = auth_file
        self.creds = None
        self.adc_path = cfg.HOME / "google_adc.json"

    def initialize(self) -> Optional[str]:
        """Load and refresh credentials from auth file. Returns access token."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import google.auth.exceptions
        
        if not self.auth_file or not os.path.exists(self.auth_file):
            return None

        try:
            with open(self.auth_file, "r") as f:
                data = json.load(f)
                
            DEFAULT_CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
            client_id = data.get("client_id", DEFAULT_CLIENT_ID)
            client_secret = data.get("client_secret")

            self.creds = Credentials(
                token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=data.get("scope", "").split()
            )
            
            if not self.creds.valid:
                try:
                    self.creds.refresh(Request())
                except google.auth.exceptions.RefreshError as e:
                    console.print(f"[yellow]⚠️  Google Refresh failed: {e}[/yellow]")
                except Exception as e:
                    console.print(f"[dim]⚠️  OAuth sync warning: {e}[/dim]")
                
            self.sync_adc()
            return self.creds.token
        except Exception as e:
            console.print(f"[DEBUG] Google OAuth Hijack failed: {e}")
            return None

    def sync_adc(self):
        """Map credentials to a standard Google 'authorized_user' JSON for ADC."""
        if not self.creds:
            return
            
        adc_data = {
            "type": "authorized_user",
            "client_id": self.creds.client_id or "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com",
            "client_secret": self.creds.client_secret or "",
            "refresh_token": self.creds.refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
            "quota_project_id": os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT") or "gemini-cli"
        }
        with open(self.adc_path, "w") as f:
            json.dump(adc_data, f, indent=2)
            
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(self.adc_path)

    def refresh_if_needed(self) -> Optional[str]:
        """Ensure token is fresh before a call."""
        if self.creds and not self.creds.valid:
            from google.auth.transport.requests import Request
            import google.auth.exceptions
            try:
                self.creds.refresh(Request())
                self.sync_adc()
                return self.creds.token
            except google.auth.exceptions.RefreshError:
                console.print("[red]⚠️  Session expired. Re-authenticate via: gcloud auth application-default login[/red]")
            except Exception as e:
                 console.print(f"[dim]OAuth Refresh Warning: {e}[/dim]")
        return getattr(self.creds, 'token', None)
