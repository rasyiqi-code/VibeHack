<p align="center">
  <img src="docs/assets/logo.png" width="120" alt="VibeHack Logo">
</p>

# 🔥 VibeHack v4.1 — The Autonomous Heart Update

> **The Agentic Security Co-Pilot. Built for Offensive Security and Developer Safety.**

VibeHack is an advanced AI-powered security assistant that bridges the gap between raw LLM intelligence and low-level shell execution. Unlike standard chatbots, VibeHack understands security tools, maps attack surfaces, and follows strategic goals autonomously while keeping a human in the loop.

---

## ⚡ Key Highlights

-   **🐚 Stateful Persistence**: Long-running `bash` sessions inside Docker. No more "one-shot" limitations.
-   **🎯 Mission Orchestration**: AI-driven task management. It doesn't just run commands; it pursues goals.
-   **📦 Autonomous Provisioning**: VibeHack automatically installs Go, Rust, and Python tools when needed.
-   **🗺️ Attack Surface Mapping**: Visualise ports, tech stacks, and endpoints in a hierarchical tree via `/map`.
-   **📝 Live Streaming Engine**: Real-time terminal output streaming with zero UI freeze.
-   **🔑 Profile Switching**: Seamlessly swap between various AI providers mid-session.
-   **📂 Hot-Resumption**: Resume or swap previous audit sessions instantly with `/sessions`.
-   **🛡️ Security Gate (HitL)**: Keyboard-driven modal dialogs for safety-first command execution.

## 🚀 Installation

```bash
# Clone and install
git clone https://github.com/rasyiqi-code/VibeHack.git
cd VibeHack
pip install -e .  # Or use 'uv pip install -e .' for 10x speed
```

## 🛠️ Quick Start

Just run `vibehack` to launch the **Trinity Auth Wizard**.

```bash
vibehack              # Start interactive REPL
vibehack /target <url> # Start a session with a target
```

## 🚀 Roadmap
VibeHack is evolving rapidly. Here is our current vector:
- [x] **v4.0: Stateful Core** — Persistent Shell sessions & Autonomous Tool Provisioning.
- [x] **v4.1: Smart Resume** — Interactive Session Manager & Hot-Swapping.
- [ ] **v4.2: Universal Bridges** — Stable support for Claude Code & ChatGPT CLI bridges.
- [ ] **v4.5: Structured Recon** — Deep parsers for Nmap/Nuclei JSON for better reasoning.
- [ ] **v5.0: Swarm Intelligence** — Distributed Master/Slave agents for multi-target audits.

## 🧪 Call for Testers (Alpha-Phase)
VibeHack v4 is a massive architectural leap and needs more community testing:
- **Test the Sandbox**: Report any container escapes or path leaks.
- **Battle-Test Provisioning**: Let us know if your favorite tool fails to install autonomously.
- **Strategic Feedback**: Is the AI making logical loops? Share your logs in the Issues!
- **Contributions**: PRs for new Middlewares or Tool Drivers are highly welcome.

## 📚 Documentation

For a deep dive into commands, configurations, and best practices:
👉 **[Read the User Guide](./docs/manual/INDEX.md)**

---
*VibeHack is intended for legal, authorised security auditing only. Use responsibly.*
