# 📟 Command Reference (v4.0)

## CLI Commands
| Command | Usage | Description |
| :--- | :--- | :--- |
| `vibehack` | `vibehack [options]` | Start the interactive REPL. |
| `start` | `vibehack start <target>` | Quick one-shot targeting (non-interactive). |
| `sessions` | `vibehack sessions` | List all previous saved sessions. |
| `resume` | `vibehack resume <id>` | Resume a specific session by ID. |
| `report` | `vibehack report <id>` | Export a session to a Markdown/PDF report. |
| `check` | `vibehack check` | Health check: tool discovery & LTM stats. |
| **`provision`**| `vibehack provision --all` | **[New]** Pre-install all supported Go/Rust/Apt tools. |
| `install` | `vibehack install <tool>` | External tool provisioner (e.g. `nmap`). |
| `update` | `vibehack update` | Self-update from GitHub. |
| `version` | `vibehack version` | Show version and build info. |

### CLI Options
- `--target, -t`: Set initial target.
- `--op-mode`: Set operation mode (`agent` | `ask`).
- `--persona, -p`: Set persona (`dev-safe` | `pro`).
- `--unchained`: Bypass regex guardrails (requires waiver).
- **`--sandbox`**: **[Required for v4.0]** Run LLM shell commands in a persistent Docker session.
- `--model`: Specific LLM model override.

---

## REPL Slash Commands (v4.0)
| Command | Description |
| :--- | :--- |
| `/help` | Show REPL command help. |
| `/target <url>` | Set or change the current attack target. |
| `/status` | Show session status, AI confidence, and **Shadow Critic** status. |
| `/map` | Visualise the discovered attack surface as a **Real-Time Tree**. |
| `/history` | **[New]** Show a clean summary of the current session's ReAct chain. |
| `/sessions` | **[New]** List and interactive resume previous sessions via **Hot-Swap**. |
| `/install <tool>` | Manually trigger the auto-provisioner. |
| `/memory` | Search Long-Term Memory (RAG-lite indexing). |
| `/pipeline` | **[New]** View the active middleware stack (Memory, Critique, Obfuscation). |
| `/exit` | Terminate session, ingest memory, and save evidence. |
