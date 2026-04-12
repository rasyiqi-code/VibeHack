import os
from rich.console import Console
from rich.prompt import Prompt
from vibehack.config import cfg
from vibehack.ui.tui import get_masked_input
from vibehack.core.auth import start_google_login
from vibehack.core.discovery import (
    get_gemini_info,
    get_claude_info,
    get_codex_info,
    get_github_info,
    get_opencode_info
)

console = Console()

def _setup_wizard():
    """VibeHack Multi-Provider Setup Wizard."""
    console.print("\n[bold yellow]🤖 Vibe_Hack Configuration Wizard[/bold yellow]")
    console.print("Choose your setup path:\n")
    
    paths = {
        "1": "⚡ [bold cyan]CLI Auth Hijacking[/bold cyan] (Import from Gemini/Claude/etc)",
        "2": "🌐 [bold blue]Login via Browser[/bold blue] (Fresh Sign-in for Google)",
        "3": "🔑 [bold green]Manual API Key[/bold green] (Standard Provider Setup)",
        "4": "🛠️  [bold magenta]Custom / Local Model[/bold magenta] (Ollama/LM Studio/Custom API)",
    }
    
    for k, v in paths.items():
        console.print(f"  {k}. {v}")
        
    path_choice = Prompt.ask("\n➤ Select path", choices=list(paths.keys()), default="1")
    
    final_env = {}
    p_name = "Custom"
    
    if path_choice == "1":
        # ── Jalur 1: CLI Auth Hijacking ──────────────────────────────────
        providers = {
            "1": ("google", "Google Gemini", get_gemini_info),
            "2": ("anthropic", "Anthropic Claude", get_claude_info),
            "3": ("openai", "ChatGPT Codex", get_codex_info),
            "4": ("github", "GitHub Copilot", get_github_info),
            "5": ("opencode", "OpenCode", get_opencode_info),
        }
        console.print("\n[bold cyan]Select CLI to hijack:[/bold cyan]")
        for k, v in providers.items():
            console.print(f"  {k}. {v[1]}")
        sub_choice = Prompt.ask("➤ Select", choices=list(providers.keys()), default="1")
        pid, p_name, discovery_fn = providers[sub_choice]
        
        info = discovery_fn()
        if not info["key"]:
            console.print(f"[bold red]ERROR: No active session found for {p_name}.[/bold red]")
            return _setup_wizard() # Restart
            
        console.print(f"\n[bold green]⚡ Found session for {p_name}![/bold green]")
        if info["mode"] == "oauth":
            console.print(f"   Mode: Authorized Session (OAuth)")
            final_env["VH_AUTH_TYPE"] = "oauth"
            final_env["VH_AUTH_FILE"] = info["auth_file"]
            if pid == "google":
                info["model"] = info["model"] or "vertex_ai/gemini-1.5-pro-latest"
        else:
            console.print(f"   Mode: Static API Key")
            final_env["VH_AUTH_TYPE"] = "key"
            
        final_env["VH_PROVIDER"] = pid
        final_env["VH_API_KEY"] = info["key"]
        final_env["VH_MODEL"] = info["model"] or "auto"
        
    elif path_choice == "2":
        # ── Jalur 2: Login via Browser ───────────────────────────────────
        console.print("\n[bold blue]Opening Google Sign-in flow...[/bold blue]")
        auth_path = cfg.HOME / "google_auth.json"
        info = start_google_login(auth_path)
        
        if not info:
            console.print("[bold red]ERROR: Login failed or cancelled.[/bold red]")
            return _setup_wizard()
            
        final_env = {
            "VH_PROVIDER": "google",
            "VH_API_KEY": info["access_token"],
            "VH_MODEL": "vertex_ai/gemini-1.5-pro-latest",
            "VH_AUTH_TYPE": "oauth",
            "VH_AUTH_FILE": str(auth_path)
        }
        p_name = "Google Gemini (Browser Auth)"

    elif path_choice == "3":
        # ── Jalur 3: Manual API Key ──────────────────────────────────────
        providers = {
            "1": ("openrouter", "OpenRouter (Recommended)", "OPENROUTER_API_KEY", "openrouter/anthropic/claude-3.5-sonnet"),
            "2": ("google", "Google Gemini", "GEMINI_API_KEY", "gemini/gemini-1.5-pro-latest"),
            "3": ("anthropic", "Anthropic Claude", "ANTHROPIC_API_KEY", "anthropic/claude-3-5-sonnet-20240620"),
            "4": ("openai", "OpenAI / ChatGPT", "OPENAI_API_KEY", "openai/gpt-4o"),
        }
        for k, v in providers.items():
            console.print(f"  {k}. {v[1]}")
        sub_choice = Prompt.ask("\n➤ Select provider", choices=list(providers.keys()), default="1")
        pid, p_name, p_env, p_model = providers[sub_choice]
        
        key = get_masked_input(f"[bold cyan]➤ Enter your {p_env}[/bold cyan]")
        if not key:
             return None # Cancelled
        
        final_env = {
            "VH_PROVIDER": pid,
            "VH_API_KEY": key,
            "VH_MODEL": p_model,
            "VH_AUTH_TYPE": "key"
        }

    elif path_choice == "4":
        # ── Jalur 4: Custom / Local Model ────────────────────────────────
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
        p_name = f"Custom ({model})"

    if final_env:
        # Save to ~/.vibehack/.env
        lines = []
        # Keep old values but override VH_* ones
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
        
        # Sync runtime config
        cfg.API_KEY = final_env.get("VH_API_KEY", "")
        cfg.MODEL = final_env.get("VH_MODEL", "")
        cfg.PROVIDER = final_env.get("VH_PROVIDER", "custom")
        cfg.AUTH_TYPE = final_env.get("VH_AUTH_TYPE", "key")
        cfg.AUTH_FILE = final_env.get("VH_AUTH_FILE", "")
        cfg.API_BASE = final_env.get("VH_API_BASE", "")
        
        return cfg.API_KEY
    
    return None
