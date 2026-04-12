# 🛡️ Governance & Technical Details

## 🏗️ Core Architecture: The ReAct Loop
VibeHack operates on a **Reason → Act → Observe** loop.
- **Reason**: AI analyzes goals and target state.
- **Act**: AI proposes shell commands.
- **Observe**: VibeHack captures, truncates, and parses output.

## 🕹️ Operation Modes
- **Agent Mode**: The default autonomous behavior. The AI actively probes and exploits.
- **Ask Mode**: Security consultant behavior. AI explains concepts and answers questions.

## 🎭 Personas
- **Dev-Safe**: Focused on educational output and actionable code fixes.
- **Pro**: Minimalist expert mode for seasoned security researchers.

## 🛡️ Guardrails & Safety
- **Sandbox Mode**: Optional Docker-based execution to protect the host.
- **Regex Guardrails**: Mandatory blacklist for destructive bash patterns.
- **Middle-Out Truncation**: Intelligently trims tool output to prioritize headers and conclusions, maximizing the AI's efficiency.

## 🧠 Long-Term Memory (LTM)
Persistent cross-session learning using `~/.vibehack/memory.db`. VibeHack remembers what worked on a target yesterday to speed up today's audit.

## 🔧 Troubleshooting
- **LLM JSON Repair**: Automatic fixing of malformed AI responses.
- **Timeouts**: Configurable via `VH_CMD_TIMEOUT` for intensive scans.
- **Bridge Auth**: Redirection logic for using system-installed Gemini CLI.
