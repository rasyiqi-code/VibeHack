"""
VibeHack LLM Module - Universal LLM provider integration.

Exports:
- UniversalHandler: Main LLM orchestrator
- Finding: Security finding schema
- AgentResponse: Agent output schema
- repair_json: JSON repair utility
- GoogleAuthHandler: Google OAuth handler
"""

from vibehack.llm.provider import UniversalHandler
from vibehack.llm.schemas import Finding, AgentResponse
from vibehack.llm.repair import repair_json
from vibehack.llm.google_auth import GoogleAuthHandler
from vibehack.llm.bridge import execute_bridge_call

__all__ = [
    "UniversalHandler",
    "Finding",
    "AgentResponse",
    "repair_json",
    "GoogleAuthHandler",
    "execute_bridge_call",
]
