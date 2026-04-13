from typing import List, Dict, Any, Optional, Protocol
from pydantic import BaseModel

class PipelineContext(BaseModel):
    """Context passed through the agent pipeline."""
    target: str
    history: List[Dict[str, str]]
    thought: str
    command: Optional[str] = None
    confidence: float = 0.0
    risk: str = "low"
    metadata: Dict[str, Any] = {}
    stop_execution: bool = False
    warning: Optional[str] = None

class Middleware(Protocol):
    """Interface for agentic middleware."""
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        ...

class AgentPipeline:
    """
    Orchestrates the execution of multiple intelligence/security modules.
    Allows for "plug-and-play" features like Shadow Critic, Obfuscation, and RAG.
    """
    def __init__(self):
        self.middlewares: List[Middleware] = []

    def use(self, middleware: Middleware):
        self.middlewares.append(middleware)

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        for middleware in self.middlewares:
            if ctx.stop_execution:
                break
            ctx = await middleware(ctx)
        return ctx
