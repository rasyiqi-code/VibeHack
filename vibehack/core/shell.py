import os
import re
import asyncio
import subprocess
from typing import NamedTuple, Optional, List

class ShellResult(NamedTuple):
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool

class PersistentSession:
    """
    The Heart of v4.0: maintains a continuous bash process inside the sandbox.
    Allows for stateful commands like 'cd', 'export', and interactive behavior.
    """
    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.container_name: Optional[str] = None
        self.lock = asyncio.Lock()

    async def start(self):
        from vibehack.core.sandbox import CONTAINER_NAME
        from vibehack.config import cfg
        self.container_name = CONTAINER_NAME
        
        # We start a direct bash session inside the docker container
        sandbox_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/vibehack/bin"
        
        cmd = [
            "docker", "exec", "-i", "-u", "root",
            "-e", f"PATH={sandbox_path}",
            "-w", "/root/workspace",
            self.container_name, 
            "bash", "--noprofile", "--norc"
        ]
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        except Exception as e:
            # Fallback for local testing if docker fails
            pass

    async def execute(self, command: str, timeout: int = 120, callback=None, interrupter=None) -> ShellResult:
        """Executes a command in the persistent shell and captures output."""
        if not self.process:
            await self.start()

        async with self.lock:
            # We use a unique delimiter to know when the command finishes
            delimiter = f"VIBEHACK_DONE_{os.urandom(4).hex()}"
            # We wrap the command to capture exit code and delimiter
            full_cmd = f"{command}\necho $? && echo {delimiter}\n"
            
            try:
                self.process.stdin.write(full_cmd.encode())
                await self.process.stdin.drain()

                stdout_lines = []
                exit_code = 0
                
                # Read until delimiter
                while True:
                    line = await self.process.stdout.readline()
                    if not line: break
                    line_str = line.decode(errors="replace").strip()
                    if interrupter and interrupter() if callable(interrupter) else interrupter:
                        # Kill the current bash command if interrupted
                        self.process.stdin.write(b"\x03") # Send Ctrl+C to the bash session
                        await self.process.stdin.drain()
                        break

                    if line_str == delimiter:
                        if stdout_lines:
                            exit_code_str = stdout_lines.pop()
                            try:
                                exit_code = int(exit_code_str)
                            except:
                                exit_code = 1
                        break
                    
                    if callback:
                        # Feed the raw line (with newline) to callback
                        callback(line.decode(errors="replace"), False)
                    
                    stdout_lines.append(line_str)
                
                stdout = "\n".join(stdout_lines)
                return ShellResult(
                    stdout=_sanitize_output(stdout),
                    stderr="",
                    exit_code=exit_code,
                    truncated=False
                )
            except Exception as e:
                return ShellResult("", f"Internal Pipe Error: {str(e)}", 1, False)

# Global session instance
_SESSION = PersistentSession()

async def execute_shell(command: str, timeout: int = 120, truncate_limit: int = 2500, env=None, output_callback=None, interrupter=None) -> ShellResult:
    """Facade for the persistent session or stateless fallback."""
    from vibehack.config import cfg
    if not cfg.SANDBOX_ENABLED:
        return await _execute_stateless(command, timeout, env)
    
    res = await _SESSION.execute(command, timeout, callback=output_callback, interrupter=interrupter)
    
    # Handle truncation
    stdout = res.stdout
    truncated = False
    if len(stdout) > truncate_limit:
        half = truncate_limit // 2
        stdout = stdout[:half] + f"\n... [Truncated {len(stdout)-truncate_limit} bytes] ...\n" + stdout[-half:]
        truncated = True
    
    return ShellResult(stdout, res.stderr, res.exit_code, truncated)

async def _execute_stateless(command: str, timeout: int, env=None) -> ShellResult:
    """Fallback stateless execution for host OS (use with caution)."""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return ShellResult(
            _sanitize_output(stdout.decode(errors="replace")),
            _sanitize_output(stderr.decode(errors="replace")),
            process.returncode or 0,
            False
        )
    except Exception as e:
        return ShellResult("", f"Execution Error: {str(e)}", 1, False)

def _sanitize_output(text: str) -> str:
    """Redacts secrets and cleans triggers."""
    if not text: return ""
    text = re.sub(r"(sk-[a-zA-Z0-9]{30,})", "sk-***", text)
    text = re.sub(r"(AIza[a-zA-Z0-9_-]{30,})", "AIza***", text)
    # Basic trigger scrubbing
    for trigger in ["System:", "User:", "Assistant:"]:
        text = text.replace(trigger, f"[Sanitized {trigger}]")
    return text
