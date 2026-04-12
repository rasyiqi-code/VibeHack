# 📟 Command Reference

## CLI Commands
These commands are executed directly from your terminal.

| Command | Usage | Description |
| :--- | :--- | :--- |
| `vibehack` | `vibehack` | Start the interactive REPL. |
| `start` | `vibehack start <target>` | Quick one-shot targeting (non-interactive). |
| `sessions` | `vibehack sessions` | List all previous saved sessions. |
| `resume` | `vibehack resume <id>` | Resume a specific session by ID. |
| `report` | `vibehack report <id>` | Export a session to a Markdown/PDF report. |
| `check` | `vibehack check` | Health check: tool discovery & LTM stats. |
| `install` | `vibehack install <tool>` | External tool provisioner (e.g. `nmap`). |
| `update` | `vibehack update` | Self-update from GitHub. |
| `version` | `vibehack version` | Show version and build info. |

---

## REPL Slash Commands
These commands are used **inside** the VibeHack interaction loop.

| Command | Description |
| :--- | :--- |
| `/help` | Show REPL command help. |
| /target <url> | Set or change the current attack target. |
| /status | **[New]** Show current session & system status. |
| /map | Visualise the discovered attack surface as a Tree. |
| /auth | Reconfigure AI provider / API keys (Wizard mode). |
| /switch | **[New]** Seamlessly swap AI model without losing context. |
| /install <tool> | Install a missing security tool. |
| `/findings` | List all confirmed security vulnerabilities. |
| `/knowledge` | Show raw extracted intelligence (ports, tech, etc.). |
| `/unchained` | Toggle restricted/unrestricted mode. |
| `/clear` | Clear conversation history (keeps knowledge). |
| `/report` | Generate report from the current active session. |
| `/memory` | Browse or search Long-Term Memory (`list` \| `search <tech>`). |
| `/tools` | Show discovered security and LotL tools in PATH. |
| `/exit` | Save session and quit. |
