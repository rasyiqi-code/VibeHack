# ✨ Core Features

## 🤖 The Autonomous Agent Loop
VibeHack v2.7.0 introduces a true non-stop agentic loop.
- **Autonomous Reasoning**: After a tool (like `nmap` or `curl`) executes, the agent automatically ingests the output, analyzes it, and proposes the next logical step without waiting for user input.
- **Goal Persistence**: The agent maintains an internal "Mission Plan" that updates in real-time as objectives are met.

## 🧠 Long-Term Memory (LTM)
VibeHack never forgets a successful payload or a discovered technology.
- **Experience Ingestion**: Every session is analyzed at exit. Successes (findings discovered) and failures (blocked commands) are stored in a persistent SQLite database (`~/.vibehack/memory.db`).
- **Tactical Recall**: When targeting a similar technology in the future, the agent automatically retrieves relevant past experiences to bypass initial trial-and-error.

## 🕹️ Operation Modes & Personas
- **Agent Mode**: Fully autonomous penetration testing.
- **Ask Mode**: Interactive security consultant; explains concepts without executing code.
- **Personas**: Switch between `dev-safe` (educational/verbose) and `pro` (minimalist/expert).

## 🎮 The Interactive TUI
- **Live Streaming Output**: See `stdout`/`stderr` from tools in real-time.
- **HitL Approval**: Mandatory "ultimate firewall" for every command to ensure you remain in control.
- **Token Economy**: Granular control over context window and sliding history via `/tokens`.

## 📦 Sanitized Sandbox Execution
Run untrusted AI-generated commands safely.
- **Docker Isolation**: Optional `--sandbox` mode routes all shell commands into an ephemeral container.
- **Injection Protection**: Automatic `shlex.quote` sanitization on all command arguments.

## 🗺️ Attack Surface Mapping (`/map`)
Visualize your target as a structured tree:
- **Ports & Services**: Hierarchy of open ports.
- **Tech Stack**: Automated technology fingerprinting.
- **Endpoints**: Clean list of mapped URL paths.
- **Findings**: Confirmed vulnerabilities linked to the attack surface.
