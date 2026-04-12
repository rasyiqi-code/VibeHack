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

# 2. Setup Directories
INSTALL_DIR="$HOME/.vibehack-env"
BIN_DIR="$HOME/.local/bin"

echo "[+] Setting up isolated Python environment in $INSTALL_DIR..."
python3 -m venv "$INSTALL_DIR"

echo "[+] Installing VibeHack core..."
# We install directly from the remote repository
"$INSTALL_DIR/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/bin/pip" install git+https://github.com/rasyiqi-code/VibeHack.git -q

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
