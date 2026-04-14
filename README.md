<p align="center">
  <img src="docs/assets/logo.png" width="120" alt="VibeHack Logo">
</p>

# 🌪️ VibeHack v4.3 — The Tabula Rasa Update

> **The Blank Slate for Autonomous AI Security Agents.**

VibeHack is more than a tool; it is a **Body** for AI **Souls**. It provides the infrastructure—a hardened sandbox, a persistent shell, and long-term memory—while empowering the AI to autonomously discover, provision, and execute its own technical methodology without pre-defined dictates.

---

## ⚡ Ultra-Agnostic Highlights

-   **🌫️ Tabula Rasa Philosophy**: No hardcoded tool registries. No prescriptive methodologies. The AI is the master of its technical stack.
-   **🔍 Live Path Discovery**: Dynamically scans `$PATH` to reveal thousands of available system tools (2000+) to the AI without manual configuration.
-   **🎯 Autonomous Provisioning**: The AI identifies, fetches, and installs its own tools (`apt`, `pip`, `git`, or source compilation) based on targets.
-   **🐚 Stateful Persistence**: Long-running `bash` sessions inside a persistent Docker volume (`Vibe_Box`). Arsenal building survives restarts.
-   **🧠 Universal Pattern Recon**: Dynamic technology detection via generic banner and header analysis. No pre-defined tech fingerprints.
-   **🛡️ AST-Based Guardrails**: Leads with safety. Advanced Python AST and recursive shell analysis protect the host while allowing tactical freedom.
-   **💸 Token-Efficiency**: Optimized discovery commands (`check --tool <name>`) and smart output truncation to conserve expensive context windows.
-   **📂 Hot-Resumption**: Resume or swap previous audit sessions instantly with `/sessions`.

## 🚀 Installation

```bash
# Clone and install the agnostic engine
git clone https://github.com/rasyiqi-code/VibeHack.git
cd VibeHack
pip install -e .
```

## 🛠️ Quick Start

Just run `vibehack` to launch the **Trinity Auth Wizard**.

```bash
vibehack              # Start interactive REPL
vibehack /target <url> # Start a session with a target
vibehack check         # View health and discovered tool count
```

## 🚀 Roadmap
VibeHack has achieved its primary goal of total agnosticism. Here is our next vector:
- [x] **v4.0: Stateful Core** — Persistent Shell sessions.
- [x] **v4.2: Tool-Agnostic Autonomy** — Removed registries; AI-driven provisioning.
- [x] **v4.3: Tabula Rasa** — Universal patterns, Path discovery & AST-based safety gate.
- [ ] **v4.8: Multi-Modal Evidence** — Support for screenshot and media analysis in reporting.
- [ ] **v5.0: Swarm Intelligence** — Distributed Master/Slave agents for multi-target audits.

## 📚 Documentation

For a deep dive into the agnostic engine:
👉 **[Read the User Guide](./docs/manual/INDEX.md)**

---
*VibeHack provides the infrastructure; the AI provides the intelligence. Use responsibly.*
