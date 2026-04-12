"""
vibehack/llm/provider.py — Universal LLM provider orchestrator via LiteLLM.
Modularized in v2.6.45 to separate Schemas, Repair, GoogleAuth, and Bridge logic.
"""
import os
import asyncio
from typing import Optional, List, Dict
from pydantic import ValidationError

import litellm
litellm.suppress_debug_info = True

from vibehack.config import cfg
from vibehack.llm.schemas import Finding, AgentResponse
from vibehack.llm.repair import repair_json
from vibehack.llm.google_auth import GoogleAuthHandler
from vibehack.llm.bridge import execute_bridge_call

class UniversalHandler:
    def __init__(self, api_key: str = None, model: str = None):
        self.provider = cfg.PROVIDER
        self.auth_type = cfg.AUTH_TYPE
        self.auth_file = cfg.AUTH_FILE
        self.api_key = api_key or cfg.API_KEY
        self.model = model or cfg.MODEL
        
        # Initialization defaults
        if not self.model or self.model == "auto":
            defaults = {
                "openrouter": "openrouter/anthropic/claude-3.5-sonnet",
                "google": "gemini/gemini-3-flash-preview",
                "anthropic": "anthropic/claude-3-5-sonnet-20240620",
                "openai": "openai/gpt-4o",
            }
            self.model = defaults.get(self.provider, "openrouter/anthropic/claude-3.5-sonnet")

        # LiteLLM routing prefixing
        if self.provider == "google" and not ("/" in self.model):
             prefix = "vertex_ai/" if self.auth_type == "oauth" else "gemini/"
             self.model = f"{prefix}{self.model}"

        self.api_base = cfg.API_BASE or None
        self.custom_headers = {}
        if self.model and self.model.startswith("openrouter/"):
            self.custom_headers = {"HTTP-Referer": "https://github.com/vibehack", "X-Title": "Vibe_Hack"}
            
        # Specialized Auth Handler
        self.google_auth = None
        if self.auth_type == "oauth" and self.provider == "google":
            self.google_auth = GoogleAuthHandler(self.auth_file)
            token = self.google_auth.initialize()
            if token: self.api_key = token

    def switch_model(self, model: str, api_key: str = None, provider: str = None, auth_type: str = "key"):
        """Seamlessly update model, provider and credentials."""
        if provider: self.provider = provider
        if api_key: self.api_key = api_key
        self.auth_type = auth_type
        self.model = model
        
        if self.provider == "google" and not ("/" in self.model):
             prefix = "vertex_ai/" if self.auth_type == "oauth" else "gemini/"
             self.model = f"{prefix}{self.model}"
        
        if self.auth_type == "oauth" and self.provider == "google":
            self.google_auth = GoogleAuthHandler(self.auth_file)
            token = self.google_auth.initialize()
            if token: self.api_key = token
            
        self.custom_headers = {}
        if self.model and self.model.startswith("openrouter/"):
            self.custom_headers = {"HTTP-Referer": "https://github.com/vibehack", "X-Title": "Vibe_Hack"}

    async def complete(self, messages: List[Dict[str, str]]) -> AgentResponse:
        """Call LLM and return validated AgentResponse."""
        # 1. Handle Bridge Mode
        if self.auth_type == "bridge":
            content = execute_bridge_call(messages, self.model, self.provider)
            parsed = repair_json(content)
            if parsed is None: raise Exception(f"Bridge JSON repair failed: {content[:400]}")
            return AgentResponse(**parsed)

        # 2. Refresh OAuth if needed
        if self.google_auth:
            token = self.google_auth.refresh_if_needed()
            if token: self.api_key = token

        # 3. Standard LiteLLM Call
        last_error = None
        for attempt in range(cfg.MAX_RETRIES):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "api_key": self.api_key,
                    "api_base": self.api_base,
                    "response_format": AgentResponse,
                    "timeout": cfg.API_TIMEOUT,
                    "headers": self.custom_headers,
                }
                if self.provider == "google" and "vertex_ai/" in self.model:
                   kwargs["vertex_project"] = os.getenv("VERTEX_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "gemini-cli"

                response = await litellm.acompletion(**kwargs)
                content = response.choices[0].message.content
                parsed = repair_json(content)
                if parsed is None: raise Exception(f"JSON repair failed: {content[:400]}")

                try:
                    return AgentResponse(**parsed)
                except ValidationError:
                    return AgentResponse(thought=str(parsed.get("thought", parsed))[:500])

            except Exception as e:
                last_error = e
                await asyncio.sleep(2 ** attempt)

        raise Exception(f"LLM call failed: {last_error}")

    async def complete_raw(self, messages: List[Dict[str, str]]) -> str:
        """Raw text completion (no JSON schema)."""
        if self.auth_type == "bridge":
            return execute_bridge_call(messages, self.model, self.provider)

        if self.google_auth:
            token = self.google_auth.refresh_if_needed()
            if token: self.api_key = token
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "timeout": cfg.API_TIMEOUT,
            "headers": self.custom_headers,
        }
        if self.model.startswith("vertex_ai/") and self.auth_type == "oauth":
            kwargs.pop("api_key", None) # Use ADC
        
        if self.provider == "google" and "vertex_ai/" in self.model:
            kwargs["vertex_project"] = os.getenv("VERTEX_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "gemini-cli"

        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content
