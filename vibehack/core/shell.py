import subprocess
import os
from typing import NamedTuple, Optional

class ShellResult(NamedTuple):
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool

def execute_shell(
    command: str,
    timeout: int = 120,
    truncate_limit: int = 2500,
    env: Optional[dict] = None
) -> ShellResult:
    from vibehack.config import cfg
    from vibehack.core.sandbox import CONTAINER_NAME
    """
    Executes a raw shell command and returns the results.
    Ensures output is truncated for LLM token efficiency.
    """
    try:
        # We use shell=True to support piping and shell builtins as per PRD v1.7
        # The HitL and Regex engines are responsible for safety before this is called.
        
        target_command = command
        if cfg.SANDBOX_ENABLED:
            import shlex
            # Route to docker. Provide env vars explicitly if needed, but for simplicity
            # we rely on the container's environment + mounted ~/.vibehack/bin
            # Ensure PATH includes /root/.vibehack/bin inside the container
            target_command = f"docker exec -e PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.vibehack/bin -i {CONTAINER_NAME} bash -c {shlex.quote(command)}"
            
        process = subprocess.run(
            target_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,  # Injects ~/.vibehack/bin into PATH (effective only on host)
            executable='/bin/bash' if os.path.exists('/bin/bash') else None
        )
        
        stdout = process.stdout or ""
        stderr = process.stderr or ""
        exit_code = process.returncode
        
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if e.stdout else ""
        stderr = (e.stderr.decode() if e.stderr else "") + "\n[VibeHack Error] Command timed out."
        exit_code = 124 # Common timeout exit code
    except Exception as e:
        stdout = ""
        stderr = f"[VibeHack Error] Execution failed: {str(e)}"
        exit_code = 1

    truncated = False
    if len(stdout) > truncate_limit:
        stdout = stdout[:truncate_limit] + "\n... [Output Truncated by VibeHack]"
        truncated = True
        
    if len(stderr) > truncate_limit:
        stderr = stderr[:truncate_limit] + "\n... [Error Truncated by VibeHack]"
        truncated = True

    return ShellResult(stdout, stderr, exit_code, truncated)
