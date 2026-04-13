"""
vibehack/toolkit/provisioner.py — Auto-downloads security tool binaries from GitHub.

Strategy:
  - Go/Rust tools: GitHub Releases API → download tar.gz/zip → extract to ~/.vibehack/bin/
  - Python tools (impacket, sqlmap, semgrep): falls back to pip install guidance
  - apt tools: prints apt-get instruction for user approval

All downloads require no root access.
"""
import asyncio
import httpx
import os
import platform
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn
from vibehack.toolkit.manager import cfg, ensure_bin_dir, BIN_DIR

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Full tool registry with platform-aware asset patterns
# ─────────────────────────────────────────────────────────────────────────────
DOWNLOADABLE_TOOLS: dict[str, dict] = {
    # ProjectDiscovery suite — all support JSON output natively
    "nuclei": {
        "repo": "projectdiscovery/nuclei",
        "linux_amd64": "nuclei_{version}_linux_amd64.zip",
        "linux_arm64": "nuclei_{version}_linux_arm64.zip",
        "darwin_amd64": "nuclei_{version}_macOS_amd64.zip",
        "darwin_arm64": "nuclei_{version}_macOS_arm64.zip",
        "binary_name": "nuclei",
        "category": "vuln_scanning",
    },
    "httpx": {
        "repo": "projectdiscovery/httpx",
        "linux_amd64": "httpx_{version}_linux_amd64.zip",
        "linux_arm64": "httpx_{version}_linux_arm64.zip",
        "darwin_amd64": "httpx_{version}_macOS_amd64.zip",
        "darwin_arm64": "httpx_{version}_macOS_arm64.zip",
        "binary_name": "httpx",
        "category": "recon",
    },
    "subfinder": {
        "repo": "projectdiscovery/subfinder",
        "linux_amd64": "subfinder_{version}_linux_amd64.zip",
        "linux_arm64": "subfinder_{version}_linux_arm64.zip",
        "darwin_amd64": "subfinder_{version}_macOS_amd64.zip",
        "darwin_arm64": "subfinder_{version}_macOS_arm64.zip",
        "binary_name": "subfinder",
        "category": "recon",
    },
    "dnsx": {
        "repo": "projectdiscovery/dnsx",
        "linux_amd64": "dnsx_{version}_linux_amd64.zip",
        "linux_arm64": "dnsx_{version}_linux_arm64.zip",
        "darwin_amd64": "dnsx_{version}_macOS_amd64.zip",
        "darwin_arm64": "dnsx_{version}_macOS_arm64.zip",
        "binary_name": "dnsx",
        "category": "recon",
    },
    "ffuf": {
        "repo": "ffuf/ffuf",
        "linux_amd64": "ffuf_{version}_linux_amd64.tar.gz",
        "linux_arm64": "ffuf_{version}_linux_arm64.tar.gz",
        "darwin_amd64": "ffuf_{version}_macOS_amd64.tar.gz",
        "darwin_arm64": "ffuf_{version}_macOS_arm64.tar.gz",
        "binary_name": "ffuf",
        "category": "fuzzing",
    },
    "feroxbuster": {
        "repo": "epi052/feroxbuster",
        "linux_amd64": "x86_64-linux-feroxbuster.zip",
        "linux_arm64": "aarch64-linux-feroxbuster.zip",
        "darwin_amd64": "x86_64-macos-feroxbuster.zip",
        "darwin_arm64": "aarch64-macos-feroxbuster.zip",
        "binary_name": "feroxbuster",
        "category": "fuzzing",
        "versioned": False,  # Some tools use static asset names
    },
    "rustscan": {
        "repo": "bee-san/RustScan",
        "linux_amd64": "rustscan_{version}_x86_64-unknown-linux-musl.tar.gz",
        "linux_arm64": "rustscan_{version}_aarch64-unknown-linux-musl.tar.gz",
        "darwin_amd64": "rustscan_{version}_x86_64-apple-darwin.tar.gz",
        "darwin_arm64": "rustscan_{version}_aarch64-apple-darwin.tar.gz",
        "binary_name": "rustscan",
        "category": "port_scanning",
    },
    "trivy": {
        "repo": "aquasecurity/trivy",
        "linux_amd64": "trivy_{version}_Linux-64bit.tar.gz",
        "linux_arm64": "trivy_{version}_Linux-ARM64.tar.gz",
        "darwin_amd64": "trivy_{version}_macOS-64bit.tar.gz",
        "darwin_arm64": "trivy_{version}_macOS-ARM64.tar.gz",
        "binary_name": "trivy",
        "category": "cloud",
    },
    "cloudfox": {
        "repo": "BishopFox/cloudfox",
        "linux_amd64": "cloudfox-linux-amd64.zip",
        "linux_arm64": "cloudfox-linux-arm64.zip",
        "darwin_amd64": "cloudfox-macos-amd64.zip",
        "darwin_arm64": "cloudfox-macos-arm64.zip",
        "binary_name": "cloudfox",
        "category": "cloud",
        "versioned": False,
    },
    "naabu": {
        "repo": "projectdiscovery/naabu",
        "linux_amd64": "naabu_{version}_linux_amd64.zip",
        "linux_arm64": "naabu_{version}_linux_arm64.zip",
        "darwin_amd64": "naabu_{version}_macOS_amd64.zip",
        "darwin_arm64": "naabu_{version}_macOS_arm64.zip",
        "binary_name": "naabu",
        "category": "port_scanning",
    },
    "dalfox": {
        "repo": "hahwul/dalfox",
        "linux_amd64": "dalfox_{version}_linux_amd64.tar.gz",
        "linux_arm64": "dalfox_{version}_linux_arm64.tar.gz",
        "darwin_amd64": "dalfox_{version}_macOS_amd64.tar.gz",
        "darwin_arm64": "dalfox_{version}_macOS_arm64.tar.gz",
        "binary_name": "dalfox",
        "category": "web_exploit",
    },
    "semgrep": {
        "repo": None,
        "install_hint": "pip install semgrep",
        "binary_name": "semgrep",
        "category": "sast",
    },
    "sqlmap": {
        "repo": None,
        "install_hint": "pip install sqlmap",
        "binary_name": "sqlmap",
        "category": "web_exploit",
    },
    "impacket": {
        "repo": None,
        "install_hint": "pip install impacket",
        "binary_name": "secretsdump", # representative binary
        "category": "internal",
    },
}


# Tools NOT downloadable via GitHub — provide install hints
APT_TOOLS: dict[str, str] = {
    "nmap":         "apt-get install -y nmap",
    "gobuster":     "apt-get install -y gobuster",
    "nikto":        "apt-get install -y nikto",
    "sqlmap":       "apt-get install -y sqlmap",
    "nc":           "apt-get install -y netcat-openbsd",
    "socat":        "apt-get install -y socat",
    "searchsploit": "apt-get install -y exploitdb",
    "commix":       "apt-get install -y commix",
    "amass":        "apt-get install -y amass",
    "jadx":         "apt-get install -y jadx",
    "hydra":        "apt-get install -y hydra",
    "john":         "apt-get install -y john",
    "hashcat":      "apt-get install -y hashcat",
    "netexec":      "pipx install netexec",
    "impacket":     "pipx install impacket",  # suite: secretsdump, psexec, etc.
    "pacu":         "pip install pacu",         # AWS exploitation framework
    "enum4linux":   "apt-get install -y enum4linux",
    "smbclient":    "apt-get install -y smbclient",
    "crackmapexec": "pipx install crackmapexec",
}


def _get_platform_key() -> str:
    """Returns a key like 'linux_amd64' to look up the right asset pattern."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        arch = "amd64"
    return f"{system}_{arch}"


def _safe_extract(archive_path: Path, dest: Path):
    """
    Safely extracts a tar.gz or zip archive, preventing path traversal attacks.
    Replaces the deprecated tarfile.extractall() without a filter argument.
    """
    if str(archive_path).endswith(".tar.gz") or str(archive_path).endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                # Skip symlinks and hardlinks
                if member.issym() or member.islnk():
                    continue
                # Strip all path components — only extract the file, not directories
                member.name = Path(member.name).name
                if not member.name or member.name.startswith(".."):
                    continue
                tar.extract(member, path=dest)
    elif str(archive_path).endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for zip_info in zf.infolist():
                # Skip directories
                if zip_info.is_dir():
                    continue
                # Skip symlinks
                is_symlink = False
                if zip_info.create_system == 3:  # UNIX
                    is_symlink = stat.S_ISLNK(zip_info.external_attr >> 16)
                if is_symlink:
                    continue

                zip_info.filename = Path(zip_info.filename).name
                if not zip_info.filename or zip_info.filename.startswith(".."):
                    continue
                zf.extract(zip_info, path=dest)


async def download_tool(tool_name: str) -> bool:
    """
    Downloads a tool binary from GitHub Releases and installs it to ~/.vibehack/bin/.
    Returns True on success.
    """
    if tool_name not in DOWNLOADABLE_TOOLS:
        if tool_name in APT_TOOLS:
            from vibehack.core.shell import execute_shell
            from vibehack.config import cfg
            
            install_cmd = APT_TOOLS[tool_name]
            if cfg.SANDBOX_ENABLED:
                console.print(f"[cyan]📦 Sandbox detected. Auto-installing system package: {tool_name}...[/cyan]")
                # Inside sandbox we are root, no sudo needed
                res = await execute_shell(install_cmd)
                if res.exit_code == 0:
                    console.print(f"[bold green]✅ {tool_name} installed via apt.[/bold green]")
                    return True
                else:
                    console.print(f"[red]Failed to install {tool_name} via apt.[/red]")
                    return False
            else:
                console.print(f"[yellow]'{tool_name}' is an apt/system package.[/yellow]")
                console.print(f"[dim]Install with: sudo {install_cmd}[/dim]")
                return False
        else:
            console.print(f"[red]No download definition for '{tool_name}'.[/red]")
            return False

    tool = DOWNLOADABLE_TOOLS[tool_name]

    # Handle Python/pip tools
    if tool.get("repo") is None or "pip" in tool.get("install_hint", ""):
        hint = tool.get("install_hint", "")
        if "pip install" in hint:
            console.print(f"[cyan]🐍 Python Tool detected. Installing via pip: {hint}...[/cyan]")
            # We execute the install command directly
            from vibehack.core.shell import execute_shell
            res = await execute_shell(hint)
            if res.exit_code == 0:
                console.print(f"[bold green]✅ {tool_name} installed via pip.[/bold green]")
                return True
            else:
                console.print(f"[red]Failed to install {tool_name} via pip.[/red]")
                return False
        
        console.print(f"[yellow]'{tool_name}' requires manual setup:[/yellow] {hint}")
        return False

    ensure_bin_dir()
    platform_key = _get_platform_key()
    asset_pattern = tool.get(platform_key)

    if not asset_pattern:
        console.print(f"[red]No asset found for platform: {platform_key}[/red]")
        return False

    # Fetch latest release metadata
    api_url = f"https://api.github.com/repos/{tool['repo']}/releases/latest"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Vibe_Hack/1.7"}

    try:
        async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
            resp = await client.get(api_url)
            if resp.status_code not in (200, 301, 302):
                console.print(f"[red]GitHub API error {resp.status_code} for {tool_name}[/red]")
                return False

            release_data = resp.json()
            version = release_data["tag_name"].lstrip("v")

            versioned = tool.get("versioned", True)
            target_filename = asset_pattern.format(version=version) if versioned else asset_pattern

            asset_url = None
            for asset in release_data.get("assets", []):
                if target_filename in asset["name"] or asset["name"] == target_filename:
                    asset_url = asset["browser_download_url"]
                    break

            if not asset_url:
                # Fuzzy match fallback
                binary = tool["binary_name"]
                for asset in release_data.get("assets", []):
                    name = asset["name"].lower()
                    if binary in name and platform_key.replace("_", "-") in name:
                        asset_url = asset["browser_download_url"]
                        break

            if not asset_url:
                console.print(f"[red]Could not find asset '{target_filename}' in release for {tool_name}[/red]")
                console.print(f"[dim]Available: {[a['name'] for a in release_data.get('assets', [])]}[/dim]")
                return False

            # Download with progress bar
            archive_path = cfg.BIN_DIR / target_filename
            console.print(f"[cyan]⬇  Downloading {tool_name} v{version}...[/cyan]")

            async with client.stream("GET", asset_url, follow_redirects=True) as stream:
                total = int(stream.headers.get("content-length", 0))
                with open(archive_path, "wb") as f:
                    downloaded = 0
                    async for chunk in stream.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

        # Extract
        _safe_extract(archive_path, cfg.BIN_DIR)
        archive_path.unlink(missing_ok=True)

        # Set executable bit
        bin_path = cfg.BIN_DIR / tool["binary_name"]
        if bin_path.exists():
            bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            console.print(f"[bold green]✅ {tool_name} installed → {bin_path}[/bold green]")
            return True
        else:
            console.print(f"[red]Binary '{tool['binary_name']}' not found after extraction.[/red]")
            return False

    except httpx.RequestError as e:
        console.print(f"[red]Network error downloading {tool_name}: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Unexpected error installing {tool_name}: {e}[/red]")
        return False


async def provision_missing(tool_names: list[str]) -> dict[str, bool]:
    """Download multiple tools concurrently. Returns a dict of results."""
    tasks = {name: download_tool(name) for name in tool_names}
    results = {}
    for name, coro in tasks.items():
        results[name] = await coro
    return results


def get_install_hint(tool_name: str) -> str:
    """Returns a human-readable install instruction for a given tool."""
    if tool_name in DOWNLOADABLE_TOOLS and DOWNLOADABLE_TOOLS[tool_name].get("repo"):
        return f"vibehack install {tool_name}"
    if tool_name in APT_TOOLS:
        return f"sudo {APT_TOOLS[tool_name]}"
    if tool_name in DOWNLOADABLE_TOOLS:
        return DOWNLOADABLE_TOOLS[tool_name].get("install_hint", "Manual install required")
    return "Manual install required"
