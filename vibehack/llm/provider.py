"""
vibehack/llm/provider.py — Universal LLM provider via LiteLLM.

Supports local models (Ollama, LM Studio) and remote APIs (OpenRouter, Anthropic, Gemini)
out-of-the-box without hardcoding individual provider logic.

Calling modes:
  1. complete()      — standard async call, expects strict JSON, returns AgentResponse
  2. complete_raw()  — returns raw text (for ask mode)
"""
import json
import re
import os
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ValidationError

import litellm
# Drop spammy info logs from litellm if any
litellm.suppress_debug_info = True

from vibehack.config import cfg


class Finding(BaseModel):
    severity: str
    title: str
    description: str
    evidence: Optional[str] = None
    remediation: Optional[str] = None


class AgentResponse(BaseModel):
    """Strict JSON schema the LLM must follow every turn."""
    thought: str = Field(..., description="Internal reasoning — always required")
    raw_command: Optional[str] = Field(None, description="Shell command to execute, or null")
    is_destructive: bool = Field(False, description="True if command writes, deletes, or is high-risk")
    education: Optional[str] = Field(None, description="Educational note for dev-safe mode")
    finding: Optional[Finding] = Field(None, description="Security finding with confirmed evidence")


def _repair_json(text: str) -> Optional[dict]:
    """
    Attempt to extract a valid JSON object from an LLM response that may
    contain leading/trailing prose or broken formatting.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    fenced = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    fenced = re.sub(r"```\s*$", "", fenced, flags=re.MULTILINE).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass

    # Last resort: find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


class UniversalHandler:
    def __init__(self, api_key: str, model: str = None):
        self.provider = cfg.PROVIDER
        self.auth_type = cfg.AUTH_TYPE
        self.auth_file = cfg.AUTH_FILE
        self.api_key = api_key or cfg.API_KEY
        
        # Determine model
        self.model = model or os.getenv("VH_MODEL") or cfg.MODEL
        if not self.model:
            # Defaults per provider if none specified
            defaults = {
                "openrouter": "openrouter/anthropic/claude-3.5-sonnet",
                "google": "gemini/gemini-1.5-pro-latest",
                "anthropic": "anthropic/claude-3-5-sonnet-20240620",
                "openai": "openai/gpt-4o",
                "github": "openai/gpt-4o", # Model for copilot usually via litellm
                "opencode": "opencode/main"
            }
            self.model = defaults.get(self.provider, "openrouter/anthropic/claude-3.5-sonnet")

        # Determine base API. If not set, litellm defaults appropriately per provider prefix.
        self.api_base = cfg.API_BASE if cfg.API_BASE else None

        # For OpenRouter specifically, we want to inject headers for openrouter formatting
        self.custom_headers = {}
        if self.model.startswith("openrouter/"):
            self.custom_headers = {
                "HTTP-Referer": "https://github.com/vibehack",
                "X-Title": "Vibe_Hack",
            }
            
        # ── Auth Hijacking Logic (v2.5) ──────────────────────────────────
        self._google_creds = None
        self._google_creds_json = None
        if self.auth_type == "oauth" and self.provider == "google":
            self._init_google_oauth()

    def _init_google_oauth(self):
        """Initialize Google OAuth credentials from CLI session file."""
        import json
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        if not self.auth_file or not os.path.exists(self.auth_file):
            return

        try:
            with open(self.auth_file, "r") as f:
                data = json.load(f)
                
            self._google_creds = Credentials(
                token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=data.get("client_id", "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"), # Default Gemini CLI Client ID
                client_secret=data.get("client_secret"),
                scopes=data.get("scope", "").split()
            )
            
            # Refresh if expired
            if not self._google_creds.valid:
                self._google_creds.refresh(Request())
                
            self.api_key = self._google_creds.token
            # Convert to JSON for LiteLLM vertex_credentials
            self._google_creds_json = json.dumps({
                "token": self._google_creds.token,
                "refresh_token": self._google_creds.refresh_token,
                "token_uri": self._google_creds.token_uri,
                "client_id": self._google_creds.client_id,
                "client_secret": self._google_creds.client_secret,
                "scopes": self._google_creds.scopes
            })
        except Exception as e:
            print(f"[DEBUG] Google OAuth Hijack failed: {e}")

    def _refresh_auth_if_needed(self):
        """Ensure OAuth tokens are fresh before each call."""
        if self.provider == "google" and self._google_creds:
            from google.auth.transport.requests import Request
            if not self._google_creds.valid:
                import json
                self._google_creds.refresh(Request())
                self.api_key = self._google_creds.token
                # Sync JSON for LiteLLM
                self._google_creds_json = json.dumps({
                    "token": self._google_creds.token,
                    "refresh_token": self._google_creds.refresh_token,
                    "token_uri": self._google_creds.token_uri,
                    "client_id": self._google_creds.client_id,
                    "client_secret": self._google_creds.client_secret,
                    "scopes": self._google_creds.scopes
                })

    async def complete(self, messages: List[Dict[str, str]]) -> AgentResponse:
        """
        Call the LLM and parse the response into a validated AgentResponse.
        Includes JSON repair for slightly malformed responses.
        Retries up to cfg.MAX_RETRIES on transient errors.
        """
        self._refresh_auth_if_needed()
        last_error = None
        for attempt in range(cfg.MAX_RETRIES):
            try:
                # Tell LiteLLM to ask for JSON output if supported
                response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    vertex_credentials=self._google_creds_json,
                    response_format={"type": "json_object"},
                    timeout=cfg.API_TIMEOUT,
                    headers=self.custom_headers,
                )

                content = response.choices[0].message.content

                parsed = _repair_json(content)
                if parsed is None:
                    raise Exception(f"JSON repair failed. Raw content:\n{content[:400]}")

                try:
                    return AgentResponse(**parsed)
                except ValidationError as ve:
                    # Try to salvage minimal response
                    thought = parsed.get("thought", parsed.get("content", str(parsed)))
                    return AgentResponse(thought=str(thought)[:500])

            except Exception as e:
                last_error = e
                if attempt < cfg.MAX_RETRIES - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                continue

        raise Exception(f"LLM call failed after {cfg.MAX_RETRIES} retries: {last_error}")

    async def complete_raw(self, messages: List[Dict[str, str]]) -> str:
        """
        Call the LLM without JSON mode constraint. Returns raw text content.
        Useful for free-form explanations (Ask mode).
        """
        self._refresh_auth_if_needed()
        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            api_base=self.api_base,
            vertex_credentials=self._google_creds_json,
            timeout=cfg.API_TIMEOUT,
            headers=self.custom_headers,
        )
        return response.choices[0].message.content
