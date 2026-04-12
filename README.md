# 🔥 Vibe_Hack v2.0 — The Autonomous Weapon Update

> **Agentic Security Co-Pilot for Red Teams, Blue Teams, and Security-Conscious Developers.**

Vibe_Hack is a CLI tool that pairs an LLM reasoning engine with **direct raw shell access**, enabling AI-driven security audits with a mandatory Human-in-the-Loop (HitL) approval matrix as the ultimate safety gate.

---

## ⚡ Quick Start

### 1. Requirements
- Python 3.11+ with `uv` package manager

### 2. Install (One-Command)
```bash
curl -fsSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/install.sh | bash
```

### 3. Configure API Key
```bash
cp .env.example .env
# Edit .env → VH_API_KEY=sk-or-xxxxxxxxxxxx
# Get a key at: https://openrouter.ai
```

### 4. Run
```bash
# Open interactive REPL (primary UX — like Claude Code, but for hacking)
vibehack

# Start with Docker Sandbox Isolation (Auto-installs engine if missing)
vibehack --sandbox

# Pre-load a target
vibehack http://localhost:3000

# Pro mode (no educational tips)
vibehack http://10.0.0.5:8080 --mode pro

# Unchained (regex guardrails disabled, requires waiver)
vibehack --unchained
```

### 5. Inside the REPL
Once inside, just type naturally:
```
you> check localhost:3000 for common web vulnerabilities
you> now fuzz the /api endpoints
you> run a nuclei scan on it
you> /findings     ← list confirmed findings
you> /report       ← generate Markdown report
you> /exit
```


| Command | Description |
|---|---|
| `vibehack start <target>` | Begin an agentic security session |
| `vibehack resume <session_id>` | Resume a previously saved session |
| `vibehack report <session_id>` | Generate a Markdown audit report |
| `vibehack sessions` | List all saved sessions |
| `vibehack check` | Health-check the Security Toolkit |
| `vibehack version` | Show version info |

### Start Flags
| Flag | Description |
|---|---|
| `--mode [dev-safe\|pro]` | Dev-safe adds inline educational tips |
| `--unchained` | Disable regex guardrails (requires liability waiver) |
| `--no-memory` | Skip Long-Term Memory for this session |
| `--model <model>` | Override LLM (e.g. `openai/gpt-4o`) |

---

## 🔒 Safety Architecture

Vibe_Hack uses a **layered safety approach with HitL as the ultimate firewall**:

```
Command Proposed by AI
        │
        ▼
[Regex Blacklist] ──── Blocked? ──→ Loop rejected, AI rethinks
        │ Passed
        ▼
[Target Sanity Check] ─ Blocked? ─→ Session cannot start
        │ Passed
        ▼
[HitL: y / n / a] ──── n? ──→ AI rethinks with your note
        │ y or a
        ▼
[execute_shell()]
        │
        ▼
[Output → LLM → Next Turn]
```

### Approval Matrix
| Key | Behavior |
|---|---|
| `y` | Execute once |
| `n` | Reject (AI must rethink) |
| `a` | Auto-allow for session (suspended on destructive commands) |

### Unchained Mode
Activated with `--unchained`. **Disables the Regex Blacklist.** Requires typing the exact phrase:
```
I ACCEPT THE RISKS OF HOST COMPROMISE
```

> ⚠️ Run as non-root. AI hallucinations under `sudo` can cause irreversible damage.

---

## 🧠 Long-Term Memory (LTM)

At the end of each session, successful and failed payloads are stored locally in:
```
~/.vibehack/memory.db
```

When starting a new session against a similar technology stack, Vibe_Hack retrieves relevant experiences and injects them into the LLM system prompt. Vector-based RAG search is planned for v1.0 (Q1 2027).

---

## 🛡 Security Toolkit

Vibe_Hack is designed to work with the following tools. Run `vibehack check` to see your current status:

| Category | Tools |
|---|---|
| Recon & Web | `subfinder`, `httpx`, `dnsx`, `amass` |
| Port Scanning | `rustscan`, `nmap` |
| Fuzzing | `ffuf`, `gobuster`, `feroxbuster` |
| Vulnerability | `nuclei`, `nikto` |
| Exploitation | `sqlmap`, `searchsploit`, `commix` |
| Network | `nc`, `socat`, `curl` |
| Cloud | `cloudfox`, `pacu`, `trivy` |
| AD / Internal | `impacket-scripts`, `netexec` |
| SAST / RE | `semgrep`, `jadx` |

Missing tools are auto-downloadable to `~/.vibehack/bin/` for Go/Rust tools.

---

## 🧪 Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_guardrails.py -v
pytest tests/test_shell.py -v
```

---

## 📋 Roadmap

| Quarter | Milestone |
|---|---|
| **Q3 2026** | Alpha: Raw Shell Engine, Regex Blacklist, HitL Matrix |
| **Q4 2026** | Beta: Unchained Mode GA, Markdown Reporting, Playwright stub |
| **Q1 2027** | v1.0: Vector-based LTM (ChromaDB), Ollama local model support, Gated API |

---

## 🗑️ Uninstallation

If you wish to completely remove VibeHack:
```bash
curl -fsSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/uninstall.sh | bash
```
This will remove the core engine, the isolated environment, and your local memory database.

---

## ⚠️ Legal Notice

Vibe_Hack is a **gated, professional security research tool**. Use only on systems you own or have explicit written authorization to test. Unauthorized use against third-party systems is illegal in most jurisdictions. The developers are not liable for misuse.
