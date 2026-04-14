<p align="center">
  <img src="docs/assets/logo.png" width="160" alt="VibeHack Logo">
</p>

<h1 align="center">🌪️ VibeHack v4.3</h1>

<p align="center">
  <strong>The Industry-Leading Autonomous AI security agent for offensive security automation and stateful simulation.</strong>
</p>

<p align="center">
  <a href="https://github.com/rasyiqi-code/VibeHack/stargazers"><img src="https://img.shields.io/github/stars/rasyiqi-code/VibeHack?style=for-the-badge&color=blue" alt="Stars"></a>
  <a href="https://github.com/rasyiqi-code/VibeHack/releases"><img src="https://img.shields.io/github/v/release/rasyiqi-code/VibeHack?style=for-the-badge&color=green" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/rasyiqi-code/VibeHack?style=for-the-badge" alt="License"></a>
  <a href="https://vibehack.crediblemark.com/"><img src="https://img.shields.io/badge/DOCS-LIVE-orange?style=for-the-badge" alt="Docs"></a>
</p>

---

VibeHack is more than a tool; it is a **Body** for AI **Souls**. It provides the infrastructure—a hardened sandbox, a persistent shell, and long-term memory—while empowering the AI to autonomously discover, provision, and execute its own technical methodology without pre-defined dictates.

## ⚡ Key Capabilities

| Feature | Description |
| :--- | :--- |
| **🌫️ Tabula Rasa** | No hardcoded tool registries. The AI is the master of its own technical stack. |
| **🔍 Path Discovery** | Dynamically scans `$PATH` to reveal 2000+ available system tools instantly. |
| **🎯 Auto-Provisioning** | Autonomous installation of `apt`, `pip`, `git`, or source tools based on target discovery. |
| **🐚 Stateful Heart** | Long-running `bash` sessions that survive restarts. Arsenal building lives on. |
| **🛡️ AST Guardrails** | Advanced Python AST and shell analysis to keep the host system safe while allowing tactical freedom. |

## 🚀 Quick Start

Launch the **Trinity Auth Wizard** or start an audit in seconds:

```bash
# Install (Recommended)
curl -sSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/install.sh | bash

# Run interactive REPL
vibehack

# Start session with a target
vibehack --target https://example.com
```

## 🛠️ Installation Modes

### Option 1: Automatic Setup
Ideal for fresh systems. Automatically prepares Python3, Git, and Docker.
```bash
curl -sSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/install.sh | bash
```

### Option 2: Developer Mode
```bash
git clone https://github.com/rasyiqi-code/VibeHack.git
cd VibeHack
pip install -e .
```

## 🗺️ Roadmap to Swarm Intelligence

- [x] **v4.0: Stateful Engine** — Persistent Shell & Memory.
- [x] **v4.2: Agnostic Autonomy** — Tool-specific registries removed.
- [x] **v4.3: Tabula Rasa** — Universal patterns and AST-based safety gate.
- [ ] **v4.8: Evidence Capture** — Screenshot & media analysis for reporting.
- [ ] **v5.0: Swarm Intelligence** — Multi-target collaborative auditing.

## 📚 Resources & Support

- 🌐 **[Official Website & Docs](https://vibehack.crediblemark.com/)**
- 📖 **[User Guide](./docs/manual/INDEX.md)**
- 🛡️ **[Ethical Framework](./docs/manual/GOVERNANCE.md)**

---

<p align="center">
  Built by <a href="https://crediblemark.com/">CredibleMark</a>. Authorized Testing Only.<br>
  <i>Empowering the next generation of offensive AI security.</i>
</p>
