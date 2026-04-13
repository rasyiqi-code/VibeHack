import shutil
import re
import json
from typing import Optional
from vibehack.agent.pipeline import PipelineContext, Middleware
from vibehack.toolkit.discovery import check_tool_exists
from vibehack.memory.db import get_memory_context

class ExperienceMiddleware:
    """Injects past successful tactics into the context."""
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        from vibehack.agent.knowledge import extract_knowledge
        # Use detected technologies to find memories
        techs = ctx.metadata.get("technologies", [])
        if techs:
            memories = []
            for tech in techs:
                mem = get_memory_context(tech)
                if mem:
                    memories.append(mem)
            if memories:
                ctx.metadata["experience_context"] = "\n".join(memories)
        return ctx

class ToolValidationMiddleware:
    """Ensures the proposed tool is available, or suggests provisioning."""
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        from vibehack.toolkit.discovery import get_tool_status
        from vibehack.toolkit.provisioner import get_install_hint
        
        if not ctx.command:
            return ctx
            
        base_cmd = ctx.command.split()[0]
        status = get_tool_status(base_cmd)
        
        if status == "missing":
            ctx.warning = f"Tool '{base_cmd}' is completely missing and cannot be auto-provisioned."
            ctx.stop_execution = True
        elif status == "provisionable":
            hint = get_install_hint(base_cmd)
            ctx.warning = (
                f"Tool '{base_cmd}' is not installed, but I can provision it. "
                f"Action required: As the user if I should run '{hint}' before proceeding."
            )
            ctx.stop_execution = True
            
        return ctx

class ShadowCriticMiddleware:
    """Lead Agent peer-review."""
    def __init__(self, handler):
        self.handler = handler

    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.command or ctx.stop_execution:
            return ctx
            
        critique = await self.handler.critique(ctx.history, ctx.command)
        if critique:
            ctx.warning = critique
            ctx.stop_execution = True
        return ctx

class ChameleonMiddleware:
    """Automatically obfuscates high-risk payloads."""
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.command:
            return ctx
            
        # Detect reverse shells or sensitive patterns
        patterns = [
            (r"bash -i >& /dev/tcp/.* 0>&1", "Base64 Obfuscation"),
            (r"nc -e /bin/bash .*", "Hex Encoding"),
            (r"curl .* \| bash", "URL Encoding Bypass")
        ]
        
        for pattern, label in patterns:
            if re.search(pattern, ctx.command):
                # Simple example: Base64 wrapping
                cmd = ctx.command
                import base64
                b64_cmd = base64.b64encode(cmd.encode()).decode()
                ctx.command = f"echo {b64_cmd} | base64 -d | bash"
                ctx.metadata["obfuscation"] = label
                break
        return ctx
