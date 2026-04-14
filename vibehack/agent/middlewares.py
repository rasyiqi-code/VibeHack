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
            ctx.warning = f"Tool '{base_cmd}' is missing from the environment. You must provision it yourself (e.g., via apt, pip, or git)."
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
    """Detects high-risk payloads and warns the AI/User instead of rewriting."""
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.command:
            return ctx
            
        # High-risk patterns that usually trigger AV/EDR
        patterns = [
            (r"bash -i >& /dev/tcp/.* 0>&1", "Unencrypted Reverse Shell"),
            (r"nc -e /bin/bash .*", "Classic Netcat Backdoor"),
            (r"curl .* \| bash", "Direct Pipe-to-Shell")
        ]
        
        for pattern, label in patterns:
            if re.search(pattern, ctx.command):
                # We inject a warning into the next turn or metadata, 
                # but we DO NOT overwrite the command.
                ctx.warning = f"TACTICAL ALERT: Proposed command matches '{label}' pattern. High risk of EDR detection."
                break
        return ctx

class SkillMiddleware:
    """Injects high-level 'Skills' (expert playbooks) based on context."""
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        from pathlib import Path
        import os
        
        # Check ~/.vibehack/skills/ or local internal skills
        skill_dirs = [
            Path(__file__).parent.parent / "skills",
            Path.home() / ".vibehack" / "skills"
        ]
        
        skills_found = []
        techs = ctx.metadata.get("technologies", [])
        thought = ctx.thought.lower()
        
        for s_dir in skill_dirs:
            if not s_dir.exists(): continue
            for skill_file in s_dir.glob("*.md"):
                # Simple matching: if filename (e.g. auth_bypass) is in techs or thought
                skill_name = skill_file.stem.lower()
                clean_name = skill_name.replace("_", " ")
                
                # Check for trigger keywords inside the file
                try:
                    content = skill_file.read_text()
                    trigger_line = content.split("\n")[1] if len(content.split("\n")) > 1 else ""
                    triggers = [t.strip().lower() for t in trigger_line.replace("# Trigger:", "").split(",")] if "Trigger:" in trigger_line else []
                    
                    match = any(t in techs for t in triggers) or any(t in thought for t in triggers) or (skill_name in thought)
                    
                    if match:
                        skills_found.append(f"--- Skill: {skill_name.upper()} ---\n{content}\n")
                except Exception:
                    continue
                    
        if skills_found:
            ctx.metadata["skills_context"] = "\n".join(skills_found)
            
        return ctx

class HoneypotMiddleware:
    """Detects if the target is a honeypot and warns the AI."""
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        from vibehack.guardrails.honeypot import analyze_honeypot_risk
        
        techs = ctx.metadata.get("technologies", [])
        ports = ctx.metadata.get("open_ports", [])
        last_out = ctx.metadata.get("last_output", "")
        
        risk = analyze_honeypot_risk(techs, ports, last_out)
        if risk:
            ctx.metadata["honeypot_risk"] = risk
            # Inject warning into AI internal thought if appropriate, 
            # or just keep it for the loop to display to user.
            
        return ctx
