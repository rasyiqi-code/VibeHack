# 🔥 VibeHack v2.6.44 — The Autonomous Weapon Update

> **The Agentic Security Co-Pilot. Built for Offensive Security and Developer Safety.**

VibeHack is an advanced AI-powered security assistant that bridges the gap between raw LLM intelligence and low-level shell execution. Unlike standard chatbots, VibeHack understands security tools, maps attack surfaces, and follows strategic goals autonomously while keeping a human in the loop.

---

## ⚡ Key Highlights

-   **🎯 Mission Orchestration**: AI-driven task management. It doesn't just run commands; it pursues goals.
-   **🗺️ Attack Surface Mapping**: Visualise ports, tech stacks, and endpoints in a hierarchical tree via `/map`.
-   **📝 Live Streaming Engine**: Real-time terminal output streaming with zero UI freeze.
-   **🔑 Profile Switching**: Seamlessly swap between various AI providers (Claude, OpenAI, Gemini) mid-session.
-   **🛡️ Security Gate (HitL)**: Keyboard-driven modal dialogs for safety-first command execution.
-   **📦 Sandbox Isolation**: Runs tools in isolated Docker containers to protect your host OS.

## 🚀 Installation

```bash
# Clone and install in development mode
git clone https://github.com/rasyiqi-code/VibeHack.git
cd VibeHack
uv pip install -e .
```

## 🛠️ Quick Start

Just run `vibehack` to launch the **Trinity Auth Wizard**.

```bash
vibehack              # Start interactive REPL
vibehack /target <url> # Start a session with a target
```

## 📚 Documentation

For a deep dive into commands, configurations, and best practices, check out our full documentation:

👉 **[Read the User Guide](./doc/INDEX.md)**

---
*VibeHack is intended for legal, authorised security auditing only. Use responsibly.*
