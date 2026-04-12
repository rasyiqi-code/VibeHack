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
        half = truncate_limit // 2
        stdout = stdout[:half] + f"\n... [Truncated Middle: {len(stdout)-truncate_limit} bytes removed by VibeHack] ...\n" + stdout[-half:]
        truncated = True
        
    if len(stderr) > truncate_limit:
        half = truncate_limit // 2
        stderr = stderr[:half] + f"\n... [Error Truncated Middle: {len(stderr)-truncate_limit} bytes removed by VibeHack] ...\n" + stderr[-half:]
        truncated = True

    return ShellResult(stdout, stderr, exit_code, truncated)

async def execute_shell_async(
    command: str,
    timeout: int = 120,
    truncate_limit: int = 2500,
    env: Optional[dict] = None,
    output_callback = None
) -> ShellResult:
    import asyncio
    from vibehack.config import cfg
    from vibehack.core.sandbox import CONTAINER_NAME

    target_command = command
    if cfg.SANDBOX_ENABLED:
        import shlex
        target_command = f"docker exec -e PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.vibehack/bin -i {CONTAINER_NAME} bash -c {shlex.quote(command)}"
        
    try:
        process = await asyncio.create_subprocess_shell(
            target_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            executable='/bin/bash' if os.path.exists('/bin/bash') else None
        )
    except Exception as e:
        return ShellResult("", f"[VibeHack Error] Execution failed: {str(e)}", 1, False)

    stdout_buf = []
    stderr_buf = []

    async def read_stream(stream, buffer, is_stderr):
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode(errors='replace')
            buffer.append(text)
            if output_callback:
                output_callback(text, is_stderr)

    try:
        await asyncio.wait_for(
            asyncio.gather(
                read_stream(process.stdout, stdout_buf, False),
                read_stream(process.stderr, stderr_buf, True)
            ),
            timeout=timeout
        )
        await process.wait()
        exit_code = process.returncode
    except asyncio.TimeoutError:
        try:
            process.kill()
        except OSError:
            pass
        stderr_buf.append("\n[VibeHack Error] Command timed out.")
        exit_code = 124

    stdout = "".join(stdout_buf)
    stderr = "".join(stderr_buf)

    truncated = False
    if len(stdout) > truncate_limit:
        half = truncate_limit // 2
        stdout = stdout[:half] + f"\n... [Truncated Middle: {len(stdout)-truncate_limit} bytes removed by VibeHack] ...\n" + stdout[-half:]
        truncated = True
        
    if len(stderr) > truncate_limit:
        half = truncate_limit // 2
        stderr = stderr[:half] + f"\n... [Error Truncated Middle: {len(stderr)-truncate_limit} bytes removed by VibeHack] ...\n" + stderr[-half:]
        truncated = True

    return ShellResult(stdout, stderr, exit_code, truncated)
