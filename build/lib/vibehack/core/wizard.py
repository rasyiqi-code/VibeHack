import os
from rich.console import Console
from rich.prompt import Prompt
from vibehack.config import cfg
from vibehack.ui.tui import get_masked_input
from vibehack.core.auth import (
    manual_google_login,
    is_cli_installed,
    verify_gemini_cli_bridge
)
from vibehack.core.discovery import (
    get_gemini_info,
    get_claude_info,
    get_codex_info,
    get_github_info,
    get_opencode_info
)

console = Console()

def _pick_openrouter_model():
    """Interactive searchable model selection using prompt-toolkit."""
    from vibehack.llm.openrouter import get_openrouter_models
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import WordCompleter
    
    with console.status("[bold cyan]Fetching OpenRouter models...[/bold cyan]"):
        models = get_openrouter_models()
        
    if not models:
        console.print("[red]⚠ Could not fetch models. Fallback to manual entry.[/red]")
        return None
        
    completer = WordCompleter(models, ignore_case=True, match_middle=True)
    console.print(f"[dim]Found {len(models)} models. Start typing to filter, Use TAB to cycle candidates.[/dim]")
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass

    try:
        choice = prompt("➤ Model Search: ", completer=completer)
        return choice.strip()
    except (KeyboardInterrupt, EOFError):
        return None

def _save_and_sync(final_env):
    """Helper to save and sync environment."""
    import collections
    env_dict = collections.OrderedDict()
    
    if cfg.GLOBAL_ENV.exists():
        with open(cfg.GLOBAL_ENV, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.startswith("VH_"):
                        continue
                    env_dict[k] = v
    
    for k, v in final_env.items():
        env_dict[k] = v
        
    with open(cfg.GLOBAL_ENV, "w") as f:
        for k, v in env_dict.items():
            f.write(f"{k}={v}\n")
        
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

def _setup_auth_cli():
    # ── Jalur 1: Auth CLI (Domestic) ──────────────────────────────────
    providers = {
        "1": ("google", "Google CLI Bridge [bold green](Stable)[/bold green]", get_gemini_info),
        "2": ("anthropic", "Anthropic Claude Code [bold yellow](Coming Soon)[/bold yellow]", get_claude_info),
        "3": ("openai", "ChatGPT Codex [bold yellow](In Development)[/bold yellow]", get_codex_info),
        "4": ("github", "GitHub Copilot CLI [bold yellow](Experimental)[/bold yellow]", get_github_info),
        "5": ("opencode", "OpenCode [dim](Draft)[/dim]", get_opencode_info),
    }
    console.print("\n[bold cyan]Select CLI Provider:[/bold cyan]")
    for k, v in providers.items():
        console.print(f"  {k}. {v[1]}")
    sub_choice = Prompt.ask("➤ Select", choices=list(providers.keys()), default="1")
    pid, p_name, discovery_fn = providers[sub_choice]

    if pid == "google":
        # ── Smart Detection for Gemini CLI ───────────────────────────
        if is_cli_installed("gemini"):
            if verify_gemini_cli_bridge():
                console.print("\n[bold green]✓ Bridge detected and active![/bold green]")
                use_bridge = Prompt.ask("➤ Use active session (Seamless Bridge Mode)?", choices=["y", "n", "Y", "N"], default="Y")

                if use_bridge.upper() == "Y":
                    final_env = {
                        "VH_PROVIDER": "google",
                        "VH_API_KEY": "BRIDGE_MODE",
                        "VH_MODEL": cfg.DEFAULT_MODELS.get("google"),
                        "VH_AUTH_TYPE": "bridge"
                    }
                    return _save_and_sync(final_env)
            else:
                console.print("\n[bold cyan]Google Auth Options:[/bold cyan]")
        console.print("  1. Titan Auth (Manual Redirect - No CLI required)")
        console.print("  2. Use System CLI Bridge (Recommended)")

        sub_choice = Prompt.ask("➤ Select", choices=["1", "2"], default="1")

        if sub_choice == "2":
            console.print("\n[bold yellow]Untuk menginstal Gemini CLI, jalankan:[/bold yellow]")
            console.print("  [white]npm install -g @google/gemini-cli[/white]")
            console.print("  [white]gemini auth login[/white]\n")
            Prompt.ask("Tekan ENTER jika sudah selesai, atau kembali")
            return _setup_wizard()

        auth_path = cfg.HOME / "google_auth.json"
        info = manual_google_login(auth_path)

        if not info:
            return _setup_wizard()

        final_env = {
            "VH_PROVIDER": "google",
            "VH_API_KEY": info["access_token"],
            "VH_MODEL": cfg.DEFAULT_MODELS.get("google"),
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

def _setup_api_key():
    # ── Jalur 2: API Key (Standard) ──────────────────────────────────
    providers = {
        "1": ("openrouter", "OpenRouter (Recommended)", "OPENROUTER_API_KEY", cfg.DEFAULT_MODELS.get("openrouter")),
        "2": ("google", "Google Gemini", "GEMINI_API_KEY", cfg.DEFAULT_MODELS.get("google")),
        "3": ("anthropic", "Anthropic Claude", "ANTHROPIC_API_KEY", cfg.DEFAULT_MODELS.get("anthropic")),
        "4": ("openai", "OpenAI / ChatGPT", "OPENAI_API_KEY", cfg.DEFAULT_MODELS.get("openai")),
    }
    console.print("\n[bold cyan]Select Provider:[/bold cyan]")
    for k, v in providers.items():
        console.print(f"  {k}. {v[1]}")
    sub_choice = Prompt.ask("\n➤ Select provider", choices=list(providers.keys()), default="1")
    pid, p_name, p_env, p_model = providers[sub_choice]

    key = ""
    existing_key = os.getenv(p_env)
    if not existing_key and cfg.GLOBAL_ENV.exists():
        with open(cfg.GLOBAL_ENV, "r") as f:
            for line in f:
                if line.startswith(f"{p_env}="):
                    existing_key = line.strip().split("=", 1)[1]
                    break

    if existing_key:
        use_exist = Prompt.ask(f"\n[bold green]➤ Existing {p_env} found.[/bold green] Use existing?", choices=["y", "n"], default="y")
        if use_exist.lower() == "y":
            key = existing_key

    if not key:
        key = get_masked_input(f"\n[bold cyan]➤ Enter your {p_env}[/bold cyan]")

    if not key: return _setup_wizard()

    # ── Model Selection Logic ──────────────────────────────────────────
    console.print(f"\n[bold cyan]Model Selection:[/bold cyan]")
    
    # Custom logic for OpenRouter (Interactive Search)
    if pid == "openrouter":
        console.print(f"  Current default: [green]{p_model}[/green]")
        choice = Prompt.ask("➤ Search & Pick from OpenRouter list?", choices=["y", "n"], default="y")
        if choice.lower() == "y":
            fetched_model = _pick_openrouter_model()
            if fetched_model:
                p_model = fetched_model
            else:
                # Manual entry if search fails/cancelled
                p_model = Prompt.ask(f"➤ Enter custom model string (e.g. {cfg.MODEL_EXAMPLE})")
        else:
             p_model = Prompt.ask(f"➤ Enter custom model string (e.g. {cfg.MODEL_EXAMPLE})")
    else:
        # Standard logic for others
        console.print(f"  Default is [green]{p_model}[/green]")
        choice = Prompt.ask("➤ Use default model?", choices=["y", "n"], default="y")
        if choice.lower() == "n":
            p_model = Prompt.ask(f"➤ Enter custom model string (e.g. {cfg.MODEL_EXAMPLE})")

    final_env = {
        p_env: key,
        "VH_PROVIDER": pid,
        "VH_API_KEY": key,
        "VH_MODEL": p_model,
        "VH_AUTH_TYPE": "key"
    }
    return _save_and_sync(final_env)

def _setup_custom_model():
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

def _setup_wizard():
    """VibeHack Multi-Provider Setup Wizard."""
    console.print("\n[bold yellow]🤖 Vibe_Hack Configuration Wizard[/bold yellow]")
    console.print("Choose your setup path:\n")
    
    console.print("  1. ⚡ [bold cyan]Bridge Mode[/bold cyan] (via System CLI - [green]Google Stable[/green] / [dim]Others Coming Soon[/dim])")
    console.print("  2. 🔑 [bold green]API Key[/bold green] (Direct Provider Access - OpenAI/Anthropic/Google)")
    console.print("  3. 🛠️  [bold magenta]Custom / Local Model[/bold magenta] (Ollama / Custom API)")
        
    path_choice = Prompt.ask("\n➤ Select path [1/2/3]", choices=["1", "2", "3"], default="1")
    
    if path_choice == "1":
        return _setup_auth_cli()
    elif path_choice == "2":
        return _setup_api_key()
    elif path_choice == "3":
        return _setup_custom_model()
    
    return None
