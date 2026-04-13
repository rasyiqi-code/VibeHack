# 🏗️ Lifecycle & Installation (v4.0)

## 1. Prerequisites
VibeHack v4.0 requires **Docker** for the best and safest experience.
- **Docker Engine**: Required for **Persistent Session Mode**. Download at [docs.docker.com](https://docs.docker.com/get-docker/).
- **Linux/Darwin**: Optimized for POSIX systems.

## 2. Installation
VibeHack can be installed in two ways:
- **Production (Isolated)**:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/install.sh | bash
  ```
- **Development (Editable)**:
  ```bash
  git clone https://github.com/rasyiqi-code/VibeHack.git
  cd VibeHack
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e .
  ```

## 3. Persistent Session Configuration
By default, VibeHack v4.0 uses a stateful sandbox. Ensure Docker is running before starting a mission:
```bash
# Verify docker is accessible
docker ps
```
If Docker is not available, VibeHack will fallback to **Stateless Mode** (host execution), which is discouraged for security reasons.

## 4. Updates & Maintenance
Keep your core engine up to date:
```bash
git pull origin main
# Update templates and tools
vibehack provision --all
```

## 5. Uninstallation
To completely remove VibeHack:
```bash
# Remove configuration, reports, and AI memory
rm -rf ~/.vibehack
# Remove the development folder
rm -rf path/to/VibeHack
```

> [!CAUTION]
> **Data Loss Warning**: Deleting the `~/.vibehack` folder will permanently erase your **Long-Term Memory (LTM)**, session history, and audit reports.
