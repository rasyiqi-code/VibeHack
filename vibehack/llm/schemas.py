"""
vibehack/llm/schemas.py — Data models for LLM interactions.
"""
from typing import Optional, List
from pydantic import BaseModel, Field

class Finding(BaseModel):
    """Represents a confirmed security vulnerability."""
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
    mission_goals: Optional[List[str]] = Field(None, description="List of mission objectives")
