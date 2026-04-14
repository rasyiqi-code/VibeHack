import subprocess
import os
import atexit
from rich.console import Console
from vibehack.config import cfg

console = Console()

CONTAINER_NAME = "vibehack_sandbox"
IMAGE_NAME = "kalilinux/kali-rolling"

def check_docker() -> bool:
    """Check if docker CLI is available and daemon is running."""
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_docker_engine():
    """Prompts and attempts to auto-install Docker natively using apt."""
    from rich.prompt import Confirm
    import sys
    
    console.print("\n[bold yellow]📦 Sandbox Engine Missing[/bold yellow]")
    console.print("Vibe_Hack requires Docker for Sandbox execution.")
    console.print("I can safely auto-install it via system apt-get (requires sudo password).")
    
    if not Confirm.ask("Install Docker now?"):
        console.print("[dim]Sandbox cancelled.[/dim]")
        sys.exit(1)
        
    try:
        # Step 1: Update
        console.print("[cyan]Running: sudo apt-get update[/cyan]")
        subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)
        
        # Step 2: Install
        console.print("[cyan]Running: sudo apt-get install -y docker.io[/cyan]")
        subprocess.run(["sudo", "apt-get", "install", "-y", "docker.io"], check=True)
        
        # Step 3: Add user to docker group
        # Doing this prevents the need for sudo when calling docker explicitly
        user = os.environ.get("USER")
        if user:
            console.print(f"[cyan]Adding user '{user}' to docker group...[/cyan]")
            subprocess.run(["sudo", "usermod", "-aG", "docker", user], check=True)
            console.print("[bold yellow]Note: You may need to restart your terminal or type 'newgrp docker' for group changes to take effect if permission denied errors occur.[/bold yellow]")
            
        console.print("[bold green]✅ Docker successfully installed.[/bold green]\n")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Installation failed: {e}[/bold red]")
        sys.exit(1)
    except FileNotFoundError:
        console.print("[bold red]ERROR: sudo or apt-get not found. Only Debian/Ubuntu/Kali bases are supported for auto-install.[/bold red]")
        sys.exit(1)

def pull_image_if_needed():
    """Pulls the kali image if not present."""
    with console.status(f"[dim]Checking docker image {IMAGE_NAME}...[/dim]"):
        try:
            # Check if image exists
            res = subprocess.run(["docker", "image", "inspect", IMAGE_NAME], capture_output=True)
            if res.returncode != 0:
                console.print(f"[dim]Pulling sandbox image: {IMAGE_NAME} (this may take a minute)[/dim]")
                subprocess.run(["docker", "pull", IMAGE_NAME], check=True)
        except Exception as e:
            console.print(f"[bold red]Failed to pull sandbox image: {e}[/bold red]")
            raise

def is_container_running() -> bool:
    """Checks if the sandbox container is currently running."""
    res = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={CONTAINER_NAME}"],
        capture_output=True,
        text=True
    )
    return bool(res.stdout.strip())

def is_container_exists() -> bool:
    """Checks if the sandbox container exists (even if stopped)."""
    res = subprocess.run(
        ["docker", "ps", "-a", "-q", "-f", f"name={CONTAINER_NAME}"],
        capture_output=True,
        text=True
    )
    return bool(res.stdout.strip())

def start_sandbox():
    """Initializes the docker sandbox environment."""
    if not cfg.SANDBOX_ENABLED:
        return

    if not check_docker():
        install_docker_engine()
        # Verify it works now
        if not check_docker():
            console.print("[bold red]Docker still not detected after installation attempt. Exiting.[/bold red]")
            import sys; sys.exit(1)

    pull_image_if_needed()

    if is_container_running():
        # Already running
        return

    if is_container_exists():
        # Container exists but stopped, just remove it to get a fresh state
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    with console.status("[dim]Starting Ephemeral Sandbox...[/dim]"):
        # 1. Create a dedicated workspace if it doesn't exist
        workspace_dir = cfg.HOME / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Mount Logic:
        # - Binaries (~/.vibehack/bin) -> Read-Only (ro)
        # - Workspace (~/.vibehack/workspace) -> Read-Write (rw)
        # We NO LONGER mount the root .vibehack to protect memory.db and sessions.
        
        cmd = [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "--memory", "512m",             # Limit memory usage
            "--cpus", "0.5",                # Limit CPU usage
            "--cap-drop", "ALL",            # Drop all capabilities
            "--cap-add", "NET_RAW",          # Keep NET_RAW for network scanning tools
            "--cap-add", "NET_ADMIN",
            "-v", f"{cfg.BIN_DIR.absolute()}:/usr/local/bin:rw",
            "-v", f"{workspace_dir.absolute()}:/root/workspace:rw",
            "-w", "/root/workspace",
            IMAGE_NAME,
            "tail", "-f", "/dev/null"
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Additional setup: ensure apt paths and base tools
            # We also add /usr/local/vibehack/bin to the system PATH inside container
            init_cmd = [
                "docker", "exec", CONTAINER_NAME,
                "bash", "-c",
                "apt-get update -qq && apt-get install -y -qq curl wget iputils-ping"
            ]
            subprocess.run(init_cmd, capture_output=True)
            
            console.print("[bold green]✓ Hardened Sandbox Ready[/bold green]")
            console.print("[dim]  Path: /root/workspace (RW), /usr/local/vibehack/bin (RO)[/dim]")
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Failed to start sandbox: {e.stderr.decode()}[/bold red]")
            raise

def stop_sandbox():
    """Kills and removes the sandbox container."""
    if not cfg.SANDBOX_ENABLED:
        return
        
    if is_container_exists():
        console.print("\n[dim]Cleaning up sandbox container...[/dim]")
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

# Automatically hook cleanup
atexit.register(stop_sandbox)
