# 📟 Command Reference (v4.3 — Tabula Rasa)

## CLI Commands
| Command | Usage | Description |
| :--- | :--- | :--- |
| `vibehack` | `vibehack [options]` | Start the interactive REPL. |
| `sessions` | `vibehack sessions` | List all previous saved sessions. |
| `resume` | `vibehack resume <id>` | Resume a specific session by ID. |
| `report` | `vibehack report <id>` | Export a session to a Markdown report. |
| `check` | `vibehack check [--tool <name>]` | Health check: tool discovery & optional surgical tool lookup. |
| `update` | `vibehack update` | Self-update from GitHub. |
| `version` | `vibehack version` | Show version and build info. |

### CLI Options
- `--target, -t`: Set initial target correctly (Internal targets like `localhost` allowed).
- `--persona, -p`: Set persona (`dev-safe` | `pro`).
- `--unchained`: Bypass regex guardrails (requires tactical waiver).
- **`--sandbox`**: [Recommended] Run LLM shell commands in a persistent, agnostic Docker session.
- `--model`: Specific LLM model override.

---

## REPL Slash Commands (v4.3)
| Command | Description |
| :--- | :--- |
| `/help` | Show REPL command help. |
| `/target <url>` | Set or change the current attack target. |
| `/status` | Show session status, AI context, and Raga health. |
| `/map` | Visualise the discovered attack surface as a **Real-Time Tree**. |
| `/history` | Show a clean summary of the current session's ReAct chain. |
| `/sessions` | List and interactive resume previous sessions via **Hot-Swap**. |
| `/memory` | Search Long-Term Memory (RAG context). |
| `/tokens` | Manage context window and output truncation limits. |
| `/skills` | Manage, edit, or learn expert security patterns. |
| `/exit` | Terminate session, ingest memory, and save evidence. |

### Tool-Agnostic Management
VibeHack v4.3 does not maintain a hardcoded tool registry. The AI Agent is responsible for its own environment. 
- **Auto-Discovery**: VibeHack dynamically scans `$PATH` during the session.
- **Surgical Check**: Use `check --tool <name>` for lightweight verification.
- **Self-Provisioning**: To install utilities, the AI uses standard shell commands (`apt install`, `git clone`, `pip install`) directly inside the persistent sandbox volume. Use `check` to see the summary of discovered tools.

---
*Vibe_Hack: Total Autonomy, Zero Prescriptive Bias.*
