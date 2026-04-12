# 🏗️ Lifecycle & Installation

## 1. Installation
Depending on your use case, VibeHack can be installed in two ways:
- **Production (Isolated)**:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/install.sh | bash
  ```
- **Development (Editable)**:
  ```bash
  git clone https://github.com/rasyiqi-code/VibeHack.git
  cd VibeHack
  uv pip install -e .
  ```

## 2. Updating VibeHack
Keep your core engine up to date with the latest features from GitHub:
```bash
vibehack update
```
*Note: Restart any active sessions to apply updates.*

## 3. Resetting Configuration
If you want to clear your API keys or switch providers without reinstalling:
```bash
rm ~/.vibehack/.env
```
Running `vibehack` again will trigger the Setup Wizard.

## 4. Uninstallation
To completely remove VibeHack and all its data from your system:
```bash
# Remove the isolated environment
rm -rf ~/.vibehack-env

# Remove the binary link
rm ~/.local/bin/vibehack

# [CAUTION] Remove configuration, reports, and AI memory
rm -rf ~/.vibehack
```

> [!CAUTION]
> **Data Loss Warning**: Deleting the `~/.vibehack` folder will permanently erase your **Long-Term Memory (LTM)**, saved session history, and generated audit reports.
