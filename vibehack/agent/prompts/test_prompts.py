import os
import pytest
from vibehack.agent.prompts.options import PromptOptions
from vibehack.agent.prompts.sections import (
    render_identity, render_planning, render_task_tracker,
    render_mindset, render_safety, render_context, render_sandbox,
    render_knowledge, render_findings, render_context_hints, render_schema
)
from vibehack.agent.prompts.builder import build_system_prompt

def test_render_identity():
    # Modern Interactive
    opt = PromptOptions(interactive=True, model_tier="modern")
    out = render_identity(opt)
    assert "Vibe_Hack" in out
    assert "authorized security audit" in out
    assert "Compatibility Mode" not in out
    
    # Legacy Non-Interactive
    opt = PromptOptions(interactive=False, model_tier="legacy")
    out = render_identity(opt)
    assert "Compatibility Mode" in out
    assert "directed security audit" in out

def test_render_planning():
    # Modern
    opt = PromptOptions(planning=True, model_tier="modern")
    out = render_planning(opt)
    assert "Planning Methodology" in out
    assert "technical hypothesis" in out
    
    # Off
    opt = PromptOptions(planning=False)
    assert render_planning(opt) == ""

def test_render_task_tracker():
    # With goals
    opt = PromptOptions(task_tracker=True, mission_goals=["[DONE] Recon", "[IN_PROGRESS] Scan"])
    out = render_task_tracker(opt)
    assert "Mission Tracker" in out
    assert "[DONE] Recon" in out
    
    # Empty
    opt = PromptOptions(mission_goals=[])
    assert render_task_tracker(opt) == ""

def test_render_sandbox():
    # On
    opt = PromptOptions(sandbox=True)
    out = render_sandbox(opt)
    assert "Docker container" in out
    
    # Off
    opt = PromptOptions(sandbox=False)
    assert render_sandbox(opt) == ""

def test_builder_composition():
    opt = PromptOptions(
        target="http://test.local",
        tools=["nmap", "curl"],
        mission_goals=["[DONE] Start"]
    )
    prompt = build_system_prompt(opt)
    
    # Check order/inclusion
    assert prompt.startswith("You are Vibe_Hack")
    assert "Planning Methodology" in prompt
    assert "Mission Tracker" in prompt
    assert "Security mandates" in prompt
    assert prompt.endswith("No markdown decoration (**, *, _, `).")

def test_builder_overrides():
    opt = PromptOptions(target="test")
    overrides = {"identity": "CUSTOM IDENTITY"}
    prompt = build_system_prompt(opt, overrides=overrides)
    assert "CUSTOM IDENTITY" in prompt
    assert "You are Vibe_Hack" not in prompt

def test_variable_substitution():
    opt = PromptOptions(target="TARGET_VAR", tools=["TOOL_VAR"])
    overrides = {"identity": "Testing ${target} with ${tools}"}
    prompt = build_system_prompt(opt, overrides=overrides)
    assert "Testing TARGET_VAR with TOOL_VAR" in prompt

def test_debug_export(tmp_path):
    # Mock cfg.HOME to use tmp_path
    from vibehack.config import cfg
    original_home = cfg.HOME
    cfg.HOME = tmp_path
    
    os.environ["VH_DEBUG_PROMPT"] = "1"
    opt = PromptOptions(target="debug-test")
    build_system_prompt(opt)
    
    debug_file = tmp_path / "debug_prompt.md"
    assert debug_file.exists()
    assert "debug-test" in debug_file.read_text()
    
    # Cleanup
    cfg.HOME = original_home
    del os.environ["VH_DEBUG_PROMPT"]
