<p align="center">
  <img src="docs/assets/logo.png" width="160" alt="VibeHack Logo">
</p>

<h1 align="center">🌪️ VibeHack v4.2</h1>

<p align="center">
  <strong>The Intelligence & Optimization Release — Hardened Autonomous AI Security Agent</strong>
</p>

<p align="center">
  <a href="https://github.com/rasyiqi-code/VibeHack/stargazers"><img src="https://img.shields.io/github/stars/rasyiqi-code/VibeHack?style=for-the-badge&color=blue" alt="Stars"></a>
  <a href="https://github.com/rasyiqi-code/VibeHack/releases"><img src="https://img.shields.io/github/v/release/rasyiqi-code/VibeHack?style=for-the-badge&color=green" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/rasyiqi-code/VibeHack?style=for-the-badge" alt="License"></a>
  <a href="https://vibehack.crediblemark.com/"><img src="https://img.shields.io/badge/DOCS-LIVE-orange?style=for-the-badge" alt="Docs"></a>
</p>

---

## 🔒 Security Hardening (v4.2)

| Feature | Description |
| :--- | :--- |
| **🏭 Mandatory Sandbox** | All commands execute inside Docker. No host fallback. |
| **🔐 Read-Only Root** | Container filesystem is read-only (except workspace). |
| **🛡️ Multi-Layer Injection Detection** | 4-layer risk analysis for prompt injection. |
| **🚫 Exfiltration Pre-Scan** | Prevents data exfiltration before command execution. |
| **🎭 Finding Validation** | Automatic hallucination detection for security findings. |
| **📊 Fuzzy Knowledge** | Robust technology extraction with fuzzy matching. |

### Sandbox Configuration

```
Memory:     512MB Limit
CPU:        0.5 Cores
Filesystem: Read-only (except /root/workspace)
Capability: NET_RAW only (NET_ADMIN removed)
Network:   Bridge isolated
```

---

## ⚡ Key Capabilities

| Feature | Description |
| :--- | :--- |
| **🌫️ Tabula Rasa** | No hardcoded tool registries. The AI is the master of its own technical stack. |
| **🔍 Path Discovery** | Dynamically scans `$PATH` to reveal 2000+ available system tools instantly. |
| **🎯 Auto-Provisioning** | Autonomous installation of `apt`, `pip`, `git`, or source tools based on target discovery. |
| **🐚 Stateful Heart** | Long-running `bash` sessions that survive restarts. Arsenal building lives on. |
| **🛡️ AST Guardrails** | Advanced Python AST and shell analysis to keep the host system safe while allowing tactical freedom. |

---

## 🚀 Quick Start

### Prerequisites
- Docker installed and running
- Python 3.11+ (via UV)

### Run

```bash
# Using the installed script (recommended)
vibehack

# Or directly with UV
cd /home/rasyiqi/Project/VibeHack
uv run vibehack

# With target
vibehack --target http://localhost:3000

# Health check
vibehack check
```

### Installation (if not installed)

```bash
# Install via UV (recommended)
uv pip install -e .

# Or manual
cp /home/rasyiqi/.local/bin/vibehack /home/rasyiqi/.local/bin/vibehack.new
chmod +x /home/rasyiqi/.local/bin/vibehack.new
```

---

## 🛠️ Usage Examples

```bash
# Start interactive REPL
vibehack

# Quick audit with target
vibehack --target http://192.168.1.100

# Resume previous session
vibehack resume <session-id>

# Generate report
vibehack report <session-id>

# Health check & tool discovery
vibehack check
```

---

## 📋 Supported Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VH_SANDBOX` | `false` | Enable sandbox mode (`true` to enable) |
| `VH_PROVIDER` | `openrouter` | LLM provider |
| `VH_API_KEY` | - | API key |
| `VH_MODEL` | `google/gemini-2.0-flash-exp:free` | Model to use |
| `VH_MAX_TURNS` | `20` | Conversation history limit |
| `VH_TRUNCATE_LIMIT` | `4000` | Output truncation limit |

---

## 🗺️ Roadmap

- [x] **v4.0: Stateful Engine** — Persistent Shell & Memory.
- [x] **v4.2: Intelligence & Optimization** — Security hardening, injection detection, hallucination validation.
- [ ] **v4.5: Evidence Capture** — Screenshot & media analysis for reporting.
- [ ] **v5.0: Swarm Intelligence** — Multi-target collaborative auditing.

---

## 📚 Resources & Support

- 🌐 **[Official Website & Docs](https://vibehack.crediblemark.com/)**
- 📖 **[User Guide](./docs/manual/INDEX.md)**
- 🛡️ **[Ethical Framework](./docs/manual/GOVERNANCE.md)**

---

## ⚠️ Important Notes

1. **Sandbox Required**: Set `VH_SANDBOX=true` in `.env` for hardened execution.
2. **Authorized Testing Only**: Use only on systems you own or have explicit authorization.
3. **Docker Needed**: The sandbox requires Docker to be installed and running.

---

<p align="center">
  Built by <a href="https://crediblemark.com/">CredibleMark</a>. Authorized Testing Only.<br>
  <i>Empowering the next generation of offensive AI security.</i>
</p>