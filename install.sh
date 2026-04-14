#!/bin/bash

# VibeHack v4.3 — Automated Agnostic Setup Script
# Works on Ubuntu/Debian/WSL2

set -e

# Professional Styling
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "█     █  █  █▀▀█  █▀▀  █  █  █▀▀█  █▀▀  █ █"
echo " █   █   █  █▀▀▄  █▀▀  █▀▀█  █▄▄█  █    █▀▄"
echo "  █ █    █  █▄▄█  █▄▄  █  █  █  █  █▄▄  █ █"
echo -e "${NC}"
echo -e "${YELLOW}🌪️  Initiating One-Command Tabula Rasa Installation...${NC}\n"

# Function to check if a command exists
exists() {
  command -v "$1" >/dev/null 2>&1
}

# 1. Check/Install Git
if ! exists git; then
    echo -e "${YELLOW}📦 Git not found. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y git
else
    echo -e "${GREEN}✓ Git is already installed.${NC}"
fi

# 2. Check/Install Python3 & Venv
if ! exists python3; then
    echo -e "${YELLOW}🐍 Python3 not found. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
elif ! python3 -m venv --help >/dev/null 2>&1; then
    echo -e "${YELLOW}📦 Python3-venv missing. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y python3-venv
else
    echo -e "${GREEN}✓ Python3 is already installed.${NC}"
fi

# 3. Check/Install Docker
if ! exists docker; then
    echo -e "${YELLOW}🐳 Docker not found. Installing Docker Engine (Community)...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${YELLOW}ℹ️  NOTE: You might need to restart your session to use Docker without sudo.${NC}"
else
    echo -e "${GREEN}✓ Docker is already installed.${NC}"
fi

# 4. Clone/Update VibeHack
if [ ! -d "VibeHack" ]; then
    echo -e "${BLUE}📡 Cloning VibeHack repository...${NC}"
    git clone https://github.com/rasyiqi-code/VibeHack.git
    cd VibeHack
else
    echo -e "${BLUE}📂 VibeHack directory already exists. Pulling latest...${NC}"
    cd VibeHack
    git pull origin main
fi

# 5. Virtual Environment & Python Install
echo -e "${BLUE}🛠️  Configuring environment and dependencies...${NC}"
python3 -m venv .venv

# Fix activation and install quietly
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -e . --quiet

# 6. Create Global Wrapper (Experimental)
BIN_PATH="$HOME/.local/bin/vibehack"
mkdir -p "$HOME/.local/bin"
cat <<EOF > "$BIN_PATH"
#!/bin/bash
source $(pwd)/.venv/bin/activate
$(pwd)/.venv/bin/python3 $(pwd)/vibehack/cli.py "\$@"
EOF
chmod +x "$BIN_PATH"

echo -e "\n${GREEN}✅ VibeHack v4.2.0 installed successfully!${NC}"
echo -e "--------------------------------------------------------"
echo -e "You can now run VibeHack from anywhere by typing:"
echo -e "  ${YELLOW}vibehack${NC}"
echo -e "--------------------------------------------------------"
echo -e "${YELLOW}Note: Run '/auth' inside VibeHack to set your API Key.${NC}\n"

# Clean Exit: Deactivate and return to original folder
deactivate
cd - > /dev/null
