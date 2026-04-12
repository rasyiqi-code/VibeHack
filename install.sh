#!/usr/bin/env bash
# VibeHack One-Command Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/install.sh | bash

set -e

echo -e "\033[1;31m"
echo "╔══════════════════════════════════════════╗"
echo "║  🔥 Vibe_Hack v2.0 Installer             ║"
echo "╚══════════════════════════════════════════╝"
echo -e "\033[0m"

# 1. Dependency checks
if ! command -v python3 &> /dev/null; then
    echo "[!] Python3 is not installed. Please install Python 3.11+ first."
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "[!] Git is not installed. Please install Git first."
    exit 1
fi

# Utility function for spinner
spinner() {
    local pid=$1
    local delay=0.15
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# 2. Setup Directories
INSTALL_DIR="$HOME/.vibehack-env"
BIN_DIR="$HOME/.local/bin"

echo -n "[+] Setting up isolated Python environment in $INSTALL_DIR... "
python3 -m venv "$INSTALL_DIR" &
spinner $!
echo -e "\033[1;32mDone.\033[0m"

echo -n "[+] Upgrading pip inside environment... "
"$INSTALL_DIR/bin/pip" install --upgrade pip -q &
spinner $!
echo -e "\033[1;32mDone.\033[0m"

echo -n "[+] Downloading & Installing VibeHack core (this may take a minute)... "
"$INSTALL_DIR/bin/pip" install git+https://github.com/rasyiqi-code/VibeHack.git -q &
spinner $!
echo -e "\033[1;32mDone.\033[0m"

# 3. Create Symlink
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/bin/vibehack" "$BIN_DIR/vibehack"

echo ""
echo -e "\033[1;32m[✓] VibeHack successfully installed!\033[0m"
echo ""

# 4. Path verification
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\033[1;33m[!] WARNING: $BIN_DIR is NOT in your PATH.\033[0m"
    echo "To run VibeHack from anywhere, add this to your ~/.bashrc or ~/.zshrc:"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "Then run: source ~/.bashrc"
    echo ""
    echo "For now, you can run it via: $BIN_DIR/vibehack"
else
    echo "Launch it anytime by typing: vibehack"
fi
