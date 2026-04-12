# 🔥 Vibe_Hack v2.5.2 — The Trinity Auth Update

> **Agentic Security Co-Pilot for Red Teams, Blue Teams, and Security-Conscious Developers.**

Vibe_Hack is a weaponized AI co-pilot that can execute shell commands, perform reconnaissance, and find vulnerabilities autonomously with a Human-in-the-Loop (HitL) safety mechanism.

## ✨ Features (v2.5.2)

-   **Trinity Auth Wizard**: 3-way setup (CLI Auth Hijacking, Manual Keys, Custom Endpoints).
-   **CLI Auth Hijacking**: Import active authorized sessions from `gemini`, `claude-code`, `gh`, etc.
-   **Auto-Discovery Engine**: Detects keys and models from your local environment automatically.
-   **Premium TUI/REPL**: Autocomplete, slash commands, and real-time status bar.
-   **Self-Updating**: Keep your core engine up to date with a single command.
-   **Red Team Ready**: Full access to your local toolset (`nmap`, `ffuf`, `gobuster`, etc.).

## 🚀 Installation

```bash
curl -fsSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/install.sh | bash
```

## 🛠️ Setup

Just run `vibehack` for the first time to start the **Trinity Auth Wizard**.

1.  **⚡ CLI Auth Hijacking**: Use this if you already have `gemini` or `claude-code` configured.
2.  **🔑 Manual API Key**: Standard setup for OpenRouter, Anthropic, or Google.
3.  **🛠️ Custom / Local Model**: Connect to your own Ollama or LM Studio instance.

## 📖 Usage

```bash
vibehack              # Start interactive REPL
vibehack start <url>  # Quick one-shot targeting
vibehack update       # Update to latest version
vibehack --help       # See all commands
```

---
*Created by the VibeHack Team.*
