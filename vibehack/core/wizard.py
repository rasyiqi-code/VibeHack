import os
from rich.console import Console
from rich.prompt import Prompt
from vibehack.config import cfg
from vibehack.ui.tui import get_masked_input
from vibehack.core.auth import manual_google_login
from vibehack.core.discovery import (
    get_gemini_info,
    get_claude_info,
    get_codex_info,
    get_github_info,
    get_opencode_info
)

console = Console()

def _save_and_sync(final_env):
    """Helper to save and sync environment."""
    lines = []
    if cfg.GLOBAL_ENV.exists():
        with open(cfg.GLOBAL_ENV, "r") as f:
            for line in f:
                if not line.startswith("VH_"):
                    lines.append(line)
    
    for k, v in final_env.items():
        lines.append(f"{k}={v}\n")
        
    with open(cfg.GLOBAL_ENV, "w") as f:
        f.writelines(lines)
        
    console.print(f"\n[bold green]✓ Configuration saved to {cfg.GLOBAL_ENV}[/bold green]")
    
    for k, v in final_env.items():
        os.environ[k] = str(v)
        
    cfg.API_KEY = final_env.get("VH_API_KEY", "")
    cfg.MODEL = final_env.get("VH_MODEL", "")
    cfg.PROVIDER = final_env.get("VH_PROVIDER", "custom")
    cfg.AUTH_TYPE = final_env.get("VH_AUTH_TYPE", "key")
    cfg.AUTH_FILE = final_env.get("VH_AUTH_FILE", "")
    cfg.API_BASE = final_env.get("VH_API_BASE", "")
    return cfg.API_KEY

def _setup_wizard():
    """VibeHack Multi-Provider Setup Wizard."""
    console.print("\n[bold yellow]🤖 Vibe_Hack Configuration Wizard[/bold yellow]")
    console.print("Choose your setup path:\n")
    
    console.print("  1. ⚡ [bold cyan]Auth CLI[/bold cyan] (Domestic/Hijacking)")
    console.print("  2. 🔑 [bold green]API Key[/bold green] (Standard Provider Setup)")
    console.print("  3. 🛠️  [bold magenta]Custom / Local Model[/bold magenta] (Ollama/LM Studio/Custom API)")
        
    path_choice = Prompt.ask("\n➤ Select path [1/2/3]", choices=["1", "2", "3"], default="1")
    
    if path_choice == "1":
        # ── Jalur 1: Auth CLI (Domestic) ──────────────────────────────────
        providers = {
            "1": ("google", "Google Gemini CLI", get_gemini_info),
            "2": ("anthropic", "Anthropic Claude Code", get_claude_info),
            "3": ("openai", "ChatGPT Codex", get_codex_info),
            "4": ("github", "GitHub Copilot CLI", get_github_info),
            "5": ("opencode", "OpenCode", get_opencode_info),
        }
        console.print("\n[bold cyan]Select CLI Provider:[/bold cyan]")
        for k, v in providers.items():
            console.print(f"  {k}. {v[1]}")
        sub_choice = Prompt.ask("➤ Select", choices=list(providers.keys()), default="1")
        pid, p_name, discovery_fn = providers[sub_choice]
        
        if pid == "google":
            # ── Gemini CLI: Langsung Direct ke Manual Redirect (OpenClaw Style) ──
            auth_path = cfg.HOME / "google_auth.json"
            info = manual_google_login(auth_path)
            
            if not info: 
                return _setup_wizard()
            
            final_env = {
                "VH_PROVIDER": "google",
                "VH_API_KEY": info["access_token"],
                "VH_MODEL": "vertex_ai/gemini-1.5-pro-latest",
                "VH_AUTH_TYPE": "oauth",
                "VH_AUTH_FILE": str(auth_path)
            }
            return _save_and_sync(final_env)
        
        else:
            # ── Logic for other CLIs (Claude, GitHub, etc) ───────────────
            info = discovery_fn()
            if not info["key"]:
                console.print(f"[bold red]ERROR: No active session found for {p_name}.[/bold red]")
                return _setup_wizard()
                
            final_env = {
                "VH_PROVIDER": pid,
                "VH_API_KEY": info["key"],
                "VH_MODEL": info["model"] or "auto",
                "VH_AUTH_TYPE": "oauth" if info["mode"] == "oauth" else "key"
            }
            if info["mode"] == "oauth":
                final_env["VH_AUTH_FILE"] = info["auth_file"]
            
            return _save_and_sync(final_env)

    elif path_choice == "2":
        # ── Jalur 2: API Key (Standard) ──────────────────────────────────
        providers = {
            "1": ("openrouter", "OpenRouter (Recommended)", "OPENROUTER_API_KEY", "openrouter/anthropic/claude-3.5-sonnet"),
            "2": ("google", "Google Gemini", "GEMINI_API_KEY", "gemini/gemini-1.5-pro-latest"),
            "3": ("anthropic", "Anthropic Claude", "ANTHROPIC_API_KEY", "anthropic/claude-3-5-sonnet-20240620"),
            "4": ("openai", "OpenAI / ChatGPT", "OPENAI_API_KEY", "openai/gpt-4o"),
        }
        console.print("\n[bold cyan]Select Provider:[/bold cyan]")
        for k, v in providers.items():
            console.print(f"  {k}. {v[1]}")
        sub_choice = Prompt.ask("\n➤ Select provider", choices=list(providers.keys()), default="1")
        pid, p_name, p_env, p_model = providers[sub_choice]
        
        key = get_masked_input(f"[bold cyan]➤ Enter your {p_env}[/bold cyan]")
        if not key: return _setup_wizard()
        
        final_env = {
            "VH_PROVIDER": pid,
            "VH_API_KEY": key,
            "VH_MODEL": p_model,
            "VH_AUTH_TYPE": "key"
        }
        return _save_and_sync(final_env)

    elif path_choice == "3":
        # ── Jalur 3: Custom / Local Model ────────────────────────────────
        console.print("\n[bold magenta]Custom / Local Model Setup[/bold magenta]")
        api_base = Prompt.ask("➤ API Base URL", default="http://localhost:11434/v1")
        api_key = Prompt.ask("➤ API Key (optional)", default="ollama")
        model = Prompt.ask("➤ Model name", default="llama3")
        
        final_env = {
            "VH_PROVIDER": "custom",
            "VH_API_KEY": api_key,
            "VH_API_BASE": api_base,
            "VH_MODEL": model,
            "VH_AUTH_TYPE": "key"
        }
        return _save_and_sync(final_env)
    
    return None
