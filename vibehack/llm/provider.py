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
        self.api_key = api_key or os.getenv("VH_API_KEY", "")
        self.model = model or cfg.MODEL
        
        # Determine base API. If not set, litellm defaults appropriately per provider prefix.
        self.api_base = cfg.API_BASE if cfg.API_BASE else None

        # For OpenRouter specifically, we want to inject headers for openrouter formatting
        self.custom_headers = {}
        if self.model.startswith("openrouter/"):
            self.custom_headers = {
                "HTTP-Referer": "https://github.com/vibehack",
                "X-Title": "Vibe_Hack",
            }

    async def complete(self, messages: List[Dict[str, str]]) -> AgentResponse:
        """
        Call the LLM and parse the response into a validated AgentResponse.
        Includes JSON repair for slightly malformed responses.
        Retries up to cfg.MAX_RETRIES on transient errors.
        """
        last_error = None
        for attempt in range(cfg.MAX_RETRIES):
            try:
                # Tell LiteLLM to ask for JSON output if supported
                response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    api_key=self.api_key,
                    api_base=self.api_base,
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
        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            api_base=self.api_base,
            timeout=cfg.API_TIMEOUT,
            headers=self.custom_headers,
        )
        return response.choices[0].message.content
