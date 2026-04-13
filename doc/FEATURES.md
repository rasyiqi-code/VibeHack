# ✨ VibeHack Core Features (v4.0)

## 🐚 Stateful Persistence (Heart of v4.0)
VibeHack v4.0 transcends "one-shot" execution with a persistent heart.
- **Persistent Shell Sessions**: All shell commands now run in a long-lived `bash` process inside the sandbox. This allows the AI to maintain state (e.g., `cd`, environment variables) across turns.
- **Hot-Resumption (Session Manager)**: Switching between audit sessions is now instant via `/sessions`. Users can "hot-swap" their entire knowledge, target, and history state without restarting the tool.
- **Contextual Awareness**: The AI "remembers" where it is in the filesystem, allowing for professional multi-step exploitation chains.

## 🧬 Intelligence Pipeline (Middleware Stack)
The agent loop is now powered by a modular intelligence pipeline.
- **Shadow Critic (Dual-Brain)**: A secondary LLM process peer-reviews every tactical decision to prevent loops and strategic errors.
- **Chameleon Obfuscation**: High-risk payloads (like reverse shells) are automatically obfuscated into Base64/Hex formats to evade detection.
- **RAG-Lite Tactical Recall**: Proactive memory retrieval that injects past successful tactics into the AI's current strategic context.

## 🛠️ Autonomous Provisioning
The agent can now manage its own toolbox.
- **Pre-Flight Validation**: Every command is verified against the system's `$PATH` before approval.
- **Self-Healing Environment**: If a tool is missing but provisionable (supported Go/Rust/Apt tools), the agent suggests automatic installation from GitHub or system packages.

## 👾 Attack Surface Real-Time Tree
A vibrant, hierarchical visualization of the target.
- **Real-Time Mapping**: The attack tree updates instantly based on AI "thoughts" and raw tool outputs.
- **Color-Coded Findings**: Critical, high, and medium vulnerabilities are visually linked to specific ports or endpoints.

## 🧠 Long-Term Memory (LTM)
VibeHack never forgets a successful tactic.
- **Experience Indexing**: Every finding and successful command is indexed by technology stack for future recall.
- **Tactical RAG**: Automatically provides historical context when a known technology (e.g., Spring, Apache) is detected.

## 🛡️ Hardened Sandbox & Security
- **Deep Docker Isolation**: Binaries are mounted Read-Only, while the workspace is Read-Write, preventing persistence attacks.
- **Structural Guardrails**: Advanced `shlex` parsing prevents shell-metacharacter injection.
- **Output Sanitization**: Automated masking of API keys and PII in tool results.
