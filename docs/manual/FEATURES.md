# ✨ VibeHack Core Features (v4.3)

## 🌫️ Tabula Rasa (The Agnostic Engine)
VibeHack v4.3 introduces a "Blank Slate" philosophy where the agent is no longer constrained by hardcoded tool lists.
- **Dynamic Discovery Engine**: The agent automatically discovers over 2000+ binaries available in the system `$PATH`. No more manual tool registration.
- **Provider-Neutral Autonomy**: Whether the AI chooses `nmap`, `rustscan`, or a custom script, VibeHack provides the bridge without prescriptive bias.
- **Universal Technology Detection**: Technology stacks (e.g., `nginx/1.18`, `OpenSSH_8.2`) are detected via generic banner patterns, enabling larning on any target.

## 🐚 Stateful Persistence
VibeHack maintains a "Body" with a persistent heart.
- **Persistent Shell Sessions**: All shell commands run in a long-lived `bash` process inside the `Vibe_Box` sandbox. State (e.g., `cd`, env vars) is maintained throughout the audit.
- **Hot-Resumption**: Switching between audit sessions is instant via `/sessions`. Swap entire knowledge, target, and history states without restarts.

## 🧬 Intelligence Pipeline & Memory
- **Autonomous Provisioning**: If a tool is missing, the AI is empowered to install it themselves (`apt`, `git`, `pip`) into the persistent `/root/.vibehack/bin` toolbox.
- **LTM (Long-Term Memory)**: Every successful tactic is indexed by technology stack. When the AI sees a familiar banner, it recalls historical successes.
- **Shadow Critic**: A background reasoning process peer-reviews tactical decisions to prevent logic loops and strategic dead-ends.

## 🛡️ Hardened Security & Guardrails
- **Inverted Guardrails**: v4.3 flips the security model — internal targets (localhost, private subnets) are prioritized for audit, while public domains are restricted by default.
- **AST-Based Kill Switch**: Advanced Python AST parsing and recursive shell analysis detect and block dangerous commands (e.g., `rm -rf /`, `mkfs`) even when obfuscated.
- **Credential Masking**: Automated redacting of API keys and secrets in all tool outputs and logs.

## 👾 Terminal Aesthetics (TUI)
- **Rich Visualization**: Real-time hierarchical attack surface mapping via `/map`.
- **Token-Efficient Reports**: The `check` command provides truncated tool lists and surgical tool verification to preserve the LLM context window.
- **Multi-Model Support**: Native integration with LiteLLM for switching between providers (OpenAI, Anthropic, Gemini, DeepSeek) on the fly.

---

## 🧪 Community Participation
VibeHack v4.3 is a leap toward truly autonomous security agents.
- **Skill Playbooks**: Build and share `.md` skill files in `~/.vibehack/skills/` to teach the AI new tactical methodologies.
- **Experience Sharing**: Help us refine the LTM by sharing successful audit logs.

---
*The Infrastructure for the Soul.*
