# ✨ Core Features

## ⚡ Authentication & Profile Switching
VibeHack supports multiple providers simultaneously. You can switch models mid-session without re-entering credentials.
- **Automatic key detection**: VibeHack scans your environment.
- **Fast switching**: Use `/auth` to swap between Gemini, OpenAI, and Anthropic in seconds.

## 🎮 The Interactive TUI
The VibeHack interface is designed to reduce cognitive load while maintaining maximum control.
- **Mission Orchestration**: Real-time goal tracking. You'll see exactly what the AI is planning and what it has finished.
- **Live Streaming Output**: See `stdout`/`stderr` from tools (like `ffuf` or `nmap`) as it happens.
- **HitL Approval**: Secure modal dialogs for every command to prevent accidental destruction.

## 🗺️ Attack Surface Mapping (`/map`)
Visualize your target. VibeHack parses all tool outputs into a structured tree:
- **Ports & Services**: Hierarchy of open ports.
- **Tech Stack**: Automated technology fingerprinting.
- **Discovered API endpoints**: Clean list of mapped URL paths.
- **Vulnerability findings**: Confirmed vulnerabilities linked to the surface.
