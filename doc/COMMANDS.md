# 📟 Command Reference

## CLI Commands
These commands are executed directly from your terminal.

| Command | Usage | Description |
| :--- | :--- | :--- |
| `vibehack` | `vibehack [options]` | Start the interactive REPL. |
| `start` | `vibehack start <target>` | Quick one-shot targeting (non-interactive). |
| `sessions` | `vibehack sessions` | List all previous saved sessions. |
| `resume` | `vibehack resume <id>` | Resume a specific session by ID. |
| `report` | `vibehack report <id>` | Export a session to a Markdown/PDF report. |
| `check` | `vibehack check` | Health check: tool discovery & LTM stats. |
| `install` | `vibehack install <tool>` | External tool provisioner (e.g. `nmap`). |
| `update` | `vibehack update` | Self-update from GitHub. |
| `version` | `vibehack version` | Show version and build info. |

### CLI Options
- `--target, -t`: Set initial target.
- `--op-mode`: Set operation mode (`agent` | `ask`).
- `--persona, -p`: Set persona (`dev-safe` | `pro`).
- `--unchained`: Bypass regex guardrails (requires waiver).
- `--sandbox`: Run LLM shell commands in Docker.
- `--model`: Specific LLM model override.

---

## REPL Slash Commands
These commands are used **inside** the VibeHack interaction loop.

| Command | Description |
| :--- | :--- |
| `/help` | Show REPL command help. |
| `/target <url>` | Set or change the current attack target. |
| `/mode <name>` | **[New]** Switch operational mode: `agent` (autonomous) \| `ask` (consultant). |
| `/status` | Show current session & system status. |
| `/persona <name>`| **[New]** Switch persona: `dev-safe` (educational) \| `pro` (minimalist). |
| `/ask <text>` | **[New]** Ask a theory question without executing anything. |
| `/map` | Visualise the discovered attack surface as a Tree. |
| `/auth` | Reconfigure AI provider / API keys (Wizard mode). |
| `/switch <model>`| **[New]** Seamlessly swap AI model without losing message history. |
| `/install <tool>` | Install a missing security tool to `~/.vibehack/bin`. |
| `/findings` | List all confirmed security vulnerabilities. |
| `/knowledge` | Show raw extracted intelligence (ports, tech, etc.). |
| `/unchained` | Toggle restricted/unrestricted mode (Guardrail bypass). |
| `/clear` | Clear conversation history (keeps knowledge & findings). |
| `/report` | Generate report from the current active session. |
| `/memory` | Browse or search Long-Term Memory (`list` \| `search <keyword>`). |
| `/tokens` | **[New]** Manage context window (`status` \| `limit <n>` \| `turns <n>`). |
| `/tools` | Show discovered security and LotL tools in PATH. |
| `/exit` | Save session and quit. |
