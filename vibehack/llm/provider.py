"""
vibehack/llm/provider.py — Universal LLM provider orchestrator via LiteLLM.
Modularized in v2.6.45 to separate Schemas, Repair, GoogleAuth, and Bridge logic.
"""

import os
import asyncio
from typing import Optional, List, Dict
from pydantic import ValidationError

import litellm
import logging

# Suppress Litellm internal logging which might corrupt the TUI with raw dict dumps
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

# Silence LiteLLM inner warnings & force local cost map to avoid timeout hangs
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
litellm.suppress_debug_info = True

from vibehack.config import cfg
from vibehack.llm.schemas import Finding, AgentResponse
from vibehack.llm.repair import repair_json

_repair_json = repair_json
from vibehack.llm.google_auth import GoogleAuthHandler
from vibehack.llm.bridge import execute_bridge_call


class UniversalHandler:
    def __init__(self, api_key: str = None, model: str = None, provider: str = None):
        self.provider = provider or cfg.PROVIDER
        self.auth_type = cfg.AUTH_TYPE
        self.auth_file = cfg.AUTH_FILE

        # Use provided key, or get provider-specific key
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self._get_provider_key()

        self.model = model or cfg.MODEL

        # Initialization defaults
        if not self.model or self.model == "auto":
            self.model = cfg.DEFAULT_MODELS.get(self.provider, cfg.PRIMARY_DEFAULT)

        # LiteLLM routing prefixing
        if self.provider == "google" and not ("/" in self.model):
            prefix = "vertex_ai/" if self.auth_type == "oauth" else "gemini/"
            self.model = f"{prefix}{self.model}"
        elif self.provider and self.provider != "custom":
            if not self.model.startswith(f"{self.provider}/"):
                self.model = f"{self.provider}/{self.model}"

        self.api_base = cfg.API_BASE or None
        self.custom_headers = {}
        if self.model and self.model.startswith("openrouter/"):
            self.custom_headers = {
                "HTTP-Referer": "https://github.com/vibehack",
                "X-Title": "Vibe_Hack",
            }

        # Specialized Auth Handler
        self.google_auth = None
        if self.auth_type == "oauth" and self.provider == "google":
            self.google_auth = GoogleAuthHandler(self.auth_file)
            token = self.google_auth.initialize()
            if token:
                self.api_key = token

    def _get_provider_key(self) -> str:
        """Get provider-specific API key."""
        provider = self.provider.lower()
        key_map = {
            "openrouter": cfg.OPENROUTER_KEY,
            "google": cfg.GOOGLE_KEY,
            "anthropic": cfg.ANTHROPIC_KEY,
            "openai": cfg.OPENAI_KEY,
        }
        provider_key = key_map.get(provider, "")
        if provider_key:
            return provider_key
        return cfg.API_KEY

    def switch_model(
        self,
        model: str,
        api_key: str = None,
        provider: str = None,
        auth_type: str = "key",
    ):
        """Seamlessly update model, provider and credentials."""
        if provider:
            self.provider = provider
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self._get_provider_key()
        self.auth_type = auth_type
        self.model = model

        if self.provider == "google" and not ("/" in self.model):
            prefix = "vertex_ai/" if self.auth_type == "oauth" else "gemini/"
            self.model = f"{prefix}{self.model}"
        elif self.provider and self.provider != "custom":
            if not self.model.startswith(f"{self.provider}/"):
                self.model = f"{self.provider}/{self.model}"

        if self.auth_type == "oauth" and self.provider == "google":
            self.google_auth = GoogleAuthHandler(self.auth_file)
            token = self.google_auth.initialize()
            if token:
                self.api_key = token

        self.custom_headers = {}
        if self.model and self.model.startswith("openrouter/"):
            self.custom_headers = {
                "HTTP-Referer": "https://github.com/vibehack",
                "X-Title": "Vibe_Hack",
            }

    async def complete(self, messages: List[Dict[str, str]]) -> AgentResponse:
        """Call LLM and return validated AgentResponse."""
        # 1. Handle Bridge Mode
        if self.auth_type == "bridge":
            content = execute_bridge_call(messages, self.model, self.provider)
            parsed = repair_json(content)
            if parsed is None:
                raise Exception(f"Bridge JSON repair failed: {content[:400]}")
            return AgentResponse(**parsed)

        # 2. Refresh OAuth if needed (with safety check)
        if hasattr(self, "google_auth") and self.google_auth:
            token = self.google_auth.refresh_if_needed()
            if token:
                self.api_key = token

        # Fallback models for different providers
        FALLBACK_MODELS = {
            "openrouter": [
                "openrouter/anthropic/claude-3.5-sonnet",
                "openrouter/openai/gpt-4o-mini",
            ],
            "openai": [
                "openai/gpt-4o-mini",
                "openai/gpt-3.5-turbo",
            ],
            "anthropic": [
                "anthropic/claude-3-haiku-20240307",
            ],
            "google": [
                "google/gemini-1.5-flash-001",
            ],
        }

        # 3. Standard LiteLLM Call with fallback
        last_error = None
        fallback_attempted = False

        for attempt in range(cfg.MAX_RETRIES):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "api_key": self.api_key,
                    "api_base": self.api_base,
                    "timeout": cfg.API_TIMEOUT,
                    "headers": self.custom_headers,
                }
                if self.provider == "google" and "vertex_ai/" in self.model:
                    kwargs["vertex_project"] = self.api_key
                    kwargs.pop("api_key", None)

                response = await litellm.acompletion(**kwargs)
                raw_text = response.choices[0].message.content
                
                # Check if litellm bizarrely returned a Google API quota error as text
                if "quotaId" in raw_text or "quotaValue" in raw_text or "Quota exceeded" in raw_text:
                    raise Exception("QUOTA_EXHAUSTED: Google Gemini 10 RPM Rate Limit hit.")
                
                # Pre-process: some models return Python-style single-quote dicts
                # Try ast.literal_eval first before repair_json to handle this case
                parsed = None
                import ast, json as _json
                try:
                    py_obj = ast.literal_eval(raw_text)
                    if isinstance(py_obj, dict):
                        parsed = py_obj
                except Exception:
                    pass
                
                if parsed is None:
                    parsed = repair_json(raw_text)
                    
                if parsed is None:
                    raise Exception(f"JSON repair failed. Snippet: {str(raw_text)[:150]}")
                return AgentResponse(**parsed)

            except Exception as e:
                last_error = str(e)
                err_str = str(e).lower()

                # Try fallback model if primary fails
                if not fallback_attempted and (
                    "not found" in err_str or "invalid" in err_str
                ):
                    fallback_attempted = True
                    fb_models = FALLBACK_MODELS.get(self.provider, [])
                    if fb_models:
                        self.model = fb_models[0]
                        # Re-check key for fallback model
                        self.api_key = self._get_provider_key()
                        continue

                if "rate_limit" in err_str or "429" in err_str:
                    await asyncio.sleep(2**attempt)
                    continue
                else:
                    break

        raise Exception(f"LLM call failed: {last_error}")

    async def complete_raw(self, messages: List[Dict[str, str]]) -> str:
        """Bare litellm call returning raw string for Syntract summarization."""
        if self.auth_type == "bridge":
            return execute_bridge_call(messages, self.model, self.provider)
            
        kwargs = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "timeout": cfg.API_TIMEOUT,
        }

        if self.provider == "google" and "vertex_ai/" in self.model:
            kwargs["vertex_project"] = self.api_key
            kwargs.pop("api_key", None)

        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content

    async def critique(
        self,
        history: List[Dict[str, str]],
        prompt: str,
        system_override: Optional[str] = None,
    ):
        """Critique a single prompt with structured scoring or custom system override."""
        sys_content = (
            system_override
            if system_override
            else "You are VibeHack's internal quality scorer. Return ONLY a JSON object with: score (0-10), feedback (string <50 chars), and issues (array)."
        )

        # Build context from history
        history_text = (
            "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-3:]])
            if history
            else ""
        )

        messages = [
            {
                "role": "system",
                "content": sys_content,
            },
            {
                "role": "user",
                "content": f"Context:\n{history_text}\n\nCommand to evaluate:\n{prompt[:500]}",
            },
        ]
        result = await self.complete_raw(messages)

        if system_override:
            # Security Warden mode: return None if "null", otherwise return string critique
            if "null" in result.strip().lower()[:10] or result.strip() == "":
                return None
            return result.strip()

        # Original mode
        import re

        match = re.search(r"\{[^}]+\}", result, re.DOTALL)
        if match:
            import json

            return json.loads(match.group(0))
        return {"score": 5, "feedback": "Parse failed", "issues": []}
