#!/usr/bin/env bash
# VibeHack Uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/uninstall.sh | bash

echo -e "\033[1;31m"
echo "╔══════════════════════════════════════════╗"
echo "║  🗑️  Vibe_Hack Uninstaller                ║"
echo "╚══════════════════════════════════════════╝"
echo -e "\033[0m"

confirm() {
    read -r -p "${1:-Are you sure? [y/N]} " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            true
            ;;
        *)
            false
            ;;
    esac
}

if confirm "This will remove VibeHack core, your memory database, and all session logs. Continue? [y/N]"; then
    echo "[+] Removing isolated environment (~/.vibehack-env)..."
    rm -rf "$HOME/.vibehack-env"

    echo "[+] Removing configuration and database (~/.vibehack)..."
    rm -rf "$HOME/.vibehack"

    echo "[+] Removing symlink (~/.local/bin/vibehack)..."
    rm -f "$HOME/.local/bin/vibehack"

    echo -e "\n\033[1;32m[✓] VibeHack has been completely removed from your system.\033[0m"
else
    echo "[i] Uninstallation cancelled."
fi
