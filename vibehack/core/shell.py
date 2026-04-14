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
        sandbox_path = "/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"
        
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
            # If docker fails, we don't set self.process, and execute will handle it
            print(f"DEBUG: Failed to start persistent Docker session: {e}")
            self.process = None

    async def execute(self, command: str, timeout: int = 120, callback=None, interrupter=None) -> ShellResult:
        """Executes a command in the persistent shell and captures output."""
        if not self.process or self.process.returncode is not None:
            await self.start()
            
        if not self.process:
             return ShellResult("", "Error: Persistent Sandbox session could not be started. Ensure Docker is running.", 1, False)

        async with self.lock:
            # Robust delimiter with UUID-like randomness
            salt = os.urandom(8).hex()
            delimiter = f"---VIBEHACK_BOUNDARY_{salt}---"
            
            # Wrap command: 
            # 1. Disable history for this internal wrapper
            # 2. Execute command with stderr redirection to stdout
            # 3. Print exit code and delimiter
            full_cmd = f"{{ {command}; }} 2>&1\n_vh_ret=$?; printf \"\\n%s\\n%s\\n\" \"$_vh_ret\" \"{delimiter}\"\n"
            
            try:
                # Clear any leftover output before sending new command
                while True:
                    try:
                        # Increased timeout to ensuring clearing large leftover buffers
                        chunk = await asyncio.wait_for(self.process.stdout.read(4096), timeout=0.1)
                        if not chunk: break
                    except (asyncio.TimeoutError, Exception):
                        break

                self.process.stdin.write(full_cmd.encode())
                await self.process.stdin.drain()

                output_buffer = ""
                exit_code = 0
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    # Check for external interruption
                    if interrupter and (interrupter() if callable(interrupter) else interrupter):
                        self.process.stdin.write(b"\x03") # Send Ctrl+C
                        await self.process.stdin.drain()
                        return ShellResult(output_buffer + "\n[Interrupted]", "", 130, True)

                    # Check for timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        self.process.stdin.write(b"\x03")
                        await self.process.stdin.drain()
                        return ShellResult(output_buffer + "\n[Timeout]", "", 124, True)

                    try:
                        # Read chunk instead of line for better performance with large outputs
                        chunk = await asyncio.wait_for(self.process.stdout.read(4096), timeout=0.1)
                        if not chunk: break
                        
                        chunk_str = chunk.decode(errors="replace")
                        
                        # RAM Protection: Stop buffering if exceeds 5MB
                        if len(output_buffer) > 5 * 1024 * 1024:
                            output_buffer += "\n... [TRUNCATED BY VIBEHACK RAM PROTECTION] ...\n"
                            # We still need to find the delimiter or eventually timeout/error
                            # but we stop growing the main buffer.
                            # For simplicity in this stateful shell, we'll just return what we have.
                            return ShellResult(output_buffer, "Buffer Overflow: Output exceeded 5MB", 1, True)

                        output_buffer += chunk_str
                        
                        if callback:
                            callback(chunk_str, False)
                            
                        # Search for delimiter in the last part of the buffer
                        if delimiter in output_buffer:
                            parts = output_buffer.split(delimiter)
                            main_content = parts[0].rstrip()
                            
                            # The exit code should be the last non-empty line before the delimiter
                            content_lines = main_content.splitlines()
                            if content_lines:
                                try:
                                    exit_code = int(content_lines[-1])
                                    final_stdout = "\n".join(content_lines[:-1])
                                except:
                                    exit_code = 1
                                    final_stdout = main_content
                            else:
                                final_stdout = ""
                            
                            return ShellResult(
                                stdout=_sanitize_output(final_stdout),
                                stderr="",
                                exit_code=exit_code,
                                truncated=False
                            )
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        return ShellResult(output_buffer, f"Read Error: {e}", 1, False)

            except Exception as e:
                return ShellResult("", f"Internal Pipe Error: {str(e)}", 1, False)

# Global session instance
_SESSION = PersistentSession()

async def execute_shell(command: str, timeout: int = 120, truncate_limit: int = 2500, env=None, output_callback=None, interrupter=None) -> ShellResult:
    """Facade for the persistent session or stateless fallback."""
    from vibehack.config import cfg
    if not cfg.SANDBOX_ENABLED:
        # Allow host execution by default unless explicitly blocked (User requested permanent override)
        if os.getenv("VH_ALLOW_HOST", "true").lower() != "true":
            return ShellResult("", "Error: Host Execution is blocked. Set VH_ALLOW_HOST=true to override.", 1, False)
        res = await _execute_stateless(command, timeout, env, callback=output_callback)
    else:
        res = await _SESSION.execute(command, timeout, callback=output_callback, interrupter=interrupter)
    
    # Handle truncation (Configurable via VH_TRUNCATE_LIMIT)
    from vibehack.config import cfg
    limit = cfg.TRUNCATE_LIMIT
    stdout = res.stdout
    truncated = res.truncated
    if len(stdout) > limit:
        half = limit // 2
        removed_bytes = len(stdout) - limit
        stdout = stdout[:half] + f"\n... [Truncated Middle: {removed_bytes} bytes removed by VibeHack] ...\n" + stdout[-half:]
        truncated = True
    
    return ShellResult(stdout, res.stderr, res.exit_code, truncated)

async def _execute_stateless(command: str, timeout: int, env=None, callback=None) -> ShellResult:
    """Stateless execution for host OS with streaming support."""
    try:
        process = await asyncio.create_subprocess_exec(
            "bash", "-c", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout_buf = []
        stderr_buf = []

        async def _read_stream(stream, buf, is_err):
            while True:
                chunk = await stream.read(4096)
                if not chunk: break
                
                # RAM Protection: Stop buffering if exceeds 5MB
                if sum(len(c) for c in buf) > 5 * 1024 * 1024:
                    buf.append("\n... [Truncated by VibeHack Memory Protection] ...\n")
                    break
                text = chunk.decode(errors="replace")
                buf.append(text)
                if callback:
                    callback(text, is_err)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(process.stdout, stdout_buf, False),
                    _read_stream(process.stderr, stderr_buf, True)
                ),
                timeout=timeout
            )
            await process.wait()
        except asyncio.TimeoutError:
            try:
                process.kill()
            except:
                pass
            return ShellResult("".join(stdout_buf) + "\n[Timeout]", "".join(stderr_buf), 124, True)

        return ShellResult(
            _sanitize_output("".join(stdout_buf)),
            _sanitize_output("".join(stderr_buf)),
            process.returncode or 0,
            False
        )
    except Exception as e:
        return ShellResult("", f"Execution Error: {str(e)}", 1, False)

def _sanitize_output(text: str) -> str:
    """Redacts secrets, cleans triggers, and strips CLI noise like curl progress bars."""
    if not text: return ""
    
    # 1. Redact Secrets (Security Hardening)
    patterns = [
        (r"(sk-[a-zA-Z0-9]{30,})", "sk-***"),                           # OpenAI / Generic
        (r"(AIza[a-zA-Z0-9_-]{30,})", "AIza***"),                       # Google Gemini
        (r"(or-v1-[a-f0-9]{64,})", "or-v1-***"),                        # OpenRouter
        (r"(ghp_[a-zA-Z0-9]{36,})", "ghp_***"),                         # GitHub PAT
        (r"(xox[bap]-[a-zA-Z0-9-]{10,})", "slack-***"),                 # Slack
        (r"(['\"]?password['\"]?\s*[:=]\s*['\"]?)[^'\"\s]+(['\"]?)", r"\1***\2"), # Generic Passwords
        (r"(?:AKIA|ASIA)[A-Z0-9]{16}", "AWS-KEY-***"),                 # AWS Access Key
        (r"(?:\"|')?[a-zA-Z0-9/+=]{40}(?:\"|')?", "AWS-SECRET-***"),    # AWS Secret (Potential)
    ]
    for pattern, replacement in patterns:
        if isinstance(replacement, str):
            text = re.sub(pattern, replacement, text)
        else:
            text = re.sub(pattern, replacement, text)
    
    # 2. Strip CLI Noise (Progress Bars)
    text = re.sub(r"%.*?Total.*?%.*?Received.*?%.*?Xferd.*?Average.*?Speed.*?Time.*?Time.*?Time.*?Current\s+Dload.*?Upload.*?Total.*?Spent.*?Left.*?Speed", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\r?\n\s*\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+[\d:]+\s+[\d:]+\s+[\d:]+\s+[\d.]+[MkG]?", "", text)

    # 3. HTML Skeletonization (Extreme Token Saving)
    text = _skeletonize_html(text)
    
    # 4. Canonicalizing Whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text) # Collapse multiple spaces/tabs
    
    # 5. Clean Triggers to prevent prompt injection via command output
    for trigger in ["System:", "User:", "Assistant:", "Instruction:"]:
        text = text.replace(trigger, f"[Sanitized {trigger}]")
        
    return text.strip()

def _skeletonize_html(html: str) -> str:
    """Strips layout bloat (div, span, p, etc) while keeping security-relevant tags."""
    if "<html" not in html.lower() and "<form" not in html.lower() and "<input" not in html.lower():
        return html # Probably not HTML
        
    # Remove Scripts, Styles, and Comments first
    html = re.sub(r"<(script|style|svg|noscript|iframe|header|footer|nav).*?>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    # Keep only essential tags: form, input, button, select, textarea, a, meta, link
    # We strip the tags but keep the content for non-essential ones, 
    # OR we just strip the whole tag for generic containers.
    
    # 1. Strip generic containers entirely (both tag and content usually just text bloat)
    # Actually, keep the text inside but remove the tag.
    bloat_tags = ["div", "span", "p", "section", "article", "aside", "ul", "li", "ol", "br", "hr", "b", "i", "strong", "em"]
    for tag in bloat_tags:
        # Strip opening tag
        html = re.sub(f"<{tag}.*?>", "", html, flags=re.IGNORECASE)
        # Strip closing tag
        html = re.sub(f"</{tag}>", "", html, flags=re.IGNORECASE)

    # 2. Final cleanup of any tags that weren't in our "essential" list
    # Essential list: a, form, input, button, select, textarea, meta, title, head, body, html
    # But let's be even more aggressive: just keep a, form, input, button, title
    
    return html
