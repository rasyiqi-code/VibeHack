import os
import re
import asyncio
import subprocess
from typing import NamedTuple, Optional, List

# Exfiltration detection patterns (pre-execution)
EXFIL_PATTERNS = [
    (r"curl\s+.*(?:-d|--data|--data-binary).*\$\(", "curl data exfil"),
    (r"wget\s+.*(?:-O|--output-document)", "wget exfil"),
    (r"nc\s+.*(?:-e|--exec)", "netcat remote exec"),
    (r"python\s+-c.*urllib", "python exfil"),
    (r"cat\s+.*\|\s*(?:nc|wget|curl)", "pipe exfil"),
    (r"base64.*\|\s*(?:nc|wget|curl)", "base64 exfil"),
    (r"\.env|\.git/config|authorized_keys", "credential file access"),
]


def detect_exfiltration_risk(command: str) -> Optional[str]:
    """
    Pre-execution scan for data exfiltration patterns.
    Returns warning message if suspicious, None if clean.
    """
    command_lower = command.lower()
    detections = []

    for pattern, desc in EXFIL_PATTERNS:
        if re.search(pattern, command_lower, re.IGNORECASE):
            detections.append(desc)

    if detections:
        return f"DETECTED_EXFIL_RISK: {', '.join(detections)}"
    return None


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
            "docker",
            "exec",
            "-i",
            "-u",
            "root",
            "-e",
            f"PATH={sandbox_path}",
            "-w",
            "/root/workspace",
            self.container_name,
            "bash",
            "--noprofile",
            "--norc",
        ]

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            # If docker fails, we don't set self.process, and execute will handle it
            print(f"DEBUG: Failed to start persistent Docker session: {e}")
            self.process = None

    async def execute(
        self, command: str, timeout: int = 120, callback=None, interrupter=None
    ) -> ShellResult:
        """Executes a command in the persistent shell and captures output."""
        if not self.process or self.process.returncode is not None:
            await self.start()

        if not self.process:
            return ShellResult(
                "",
                "Error: Persistent Sandbox session could not be started. Ensure Docker is running.",
                1,
                False,
            )

        async with self.lock:
            # Robust delimiter with UUID-like randomness
            salt = os.urandom(8).hex()
            delimiter = f"---VIBEHACK_BOUNDARY_{salt}---"

            # 1. Disable history for this internal wrapper
            # 2. Encode command to Base64 to prevent Bash Parsing DoS (Unbalanced quotes/braces)
            # 3. Decode and eval
            import base64

            b64_cmd = base64.b64encode(command.encode()).decode()
            full_cmd = f'eval "$(echo \'{b64_cmd}\' | base64 -d)" 2>&1\n_vh_ret=$?; printf "\\n%s\\n%s\\n" "$_vh_ret" "{delimiter}"\n'

            try:
                # Clear any leftover output before sending new command
                while True:
                    try:
                        # Increased timeout to ensuring clearing large leftover buffers
                        chunk = await asyncio.wait_for(
                            self.process.stdout.read(4096), timeout=0.1
                        )
                        if not chunk:
                            break
                    except (asyncio.TimeoutError, Exception):
                        break

                self.process.stdin.write(full_cmd.encode())
                await self.process.stdin.drain()

                output_buffer = ""
                last_sent_len = 0
                exit_code = 0
                start_time = asyncio.get_event_loop().time()

                while True:
                    # Check for external interruption
                    if interrupter and (
                        interrupter() if callable(interrupter) else interrupter
                    ):
                        self.process.stdin.write(b"\x03")  # Send Ctrl+C
                        await self.process.stdin.drain()
                        return ShellResult(
                            output_buffer + "\n[Interrupted]", "", 130, True
                        )

                    # Check for timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        self.process.stdin.write(b"\x03")
                        await self.process.stdin.drain()
                        return ShellResult(output_buffer + "\n[Timeout]", "", 124, True)

                    try:
                        # Read chunk instead of line for better performance with large outputs
                        chunk = await asyncio.wait_for(
                            self.process.stdout.read(4096), timeout=0.1
                        )
                        if not chunk:
                            break

                        chunk_str = chunk.decode(errors="replace")

                        # RAM Protection: Stop buffering if exceeds 5MB
                        if len(output_buffer) > 5 * 1024 * 1024:
                            output_buffer += (
                                "\n... [TRUNCATED BY VIBEHACK RAM PROTECTION] ...\n"
                            )
                            # We still need to find the delimiter or eventually timeout/error
                            # but we stop growing the main buffer.
                            # For simplicity in this stateful shell, we'll just return what we have.
                            return ShellResult(
                                output_buffer,
                                "Buffer Overflow: Output exceeded 5MB",
                                1,
                                True,
                            )

                        output_buffer += chunk_str

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

                            if callback:
                                to_send = final_stdout[last_sent_len:]
                                if to_send:
                                    callback(to_send, False)

                            return ShellResult(
                                stdout=_sanitize_output(final_stdout),
                                stderr="",
                                exit_code=exit_code,
                                truncated=False,
                            )
                        else:
                            # Not found yet. Safe to send up to the margin to prevent partial delimiter leak.
                            if callback:
                                safe_len = max(0, len(output_buffer) - len(delimiter) - 10)
                                to_send = output_buffer[last_sent_len:safe_len]
                                if to_send:
                                    callback(to_send, False)
                                    last_sent_len += len(to_send)
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        return ShellResult(output_buffer, f"Read Error: {e}", 1, False)

            except Exception as e:
                return ShellResult("", f"Internal Pipe Error: {str(e)}", 1, False)


# Global session instance
_SESSION = PersistentSession()


async def execute_shell(
    command: str,
    timeout: int = 120,
    truncate_limit: int = 2500,
    env=None,
    output_callback=None,
    interrupter=None,
) -> ShellResult:
    """Facade for the persistent session - NO FALLBACK to host execution."""
    from vibehack.config import cfg
    from vibehack.core.sandbox import check_docker, is_container_running

    # --- Internal Tool Interception (v3.0) ---
    if command.strip().startswith("vibehack-"):
        from vibehack.core.editor import handle_internal_command

        output = handle_internal_command(command)
        return ShellResult(output, "", 0, False)

    # --- Pre-Execution Exfiltration Scan ---
    exfil_warning = detect_exfiltration_risk(command)
    if exfil_warning:
        console.print(f"[bold yellow]⚠️ {exfil_warning}[/bold yellow]")
        console.print(
            "[yellow]Command will be blocked. Add 'force' flag to override?[/yellow]"
        )
        # Still allow execution but log it heavily

    # --- Mandatory Sandbox Enforcement (Phase 1 Hardening) ---
    if not cfg.SANDBOX_ENABLED:
        return ShellResult(
            "",
            "CRITICAL ERROR: SANDBOX_ENABLED is false in config. Set VH_SANDBOX=true in .env to enable sandboxed execution.",
            1,
            False,
        )

    # Verify Docker is actually available before attempting execution
    if not check_docker():
        return ShellResult(
            "",
            "CRITICAL ERROR: Docker is not available. Please install Docker or run 'vibehack setup-sandbox'.",
            1,
            False,
        )

    if not is_container_running():
        from vibehack.core.sandbox import start_sandbox

        try:
            start_sandbox()
        except Exception as e:
            return ShellResult(
                "", f"CRITICAL ERROR: Failed to start sandbox: {str(e)}", 1, False
            )

    res = await _SESSION.execute(
        command, timeout, callback=output_callback, interrupter=interrupter
    )

    # Handle truncation (Configurable via VH_TRUNCATE_LIMIT)
    from vibehack.config import cfg

    limit = cfg.TRUNCATE_LIMIT
    stdout = res.stdout
    truncated = res.truncated
    if len(stdout) > limit:
        half = limit // 2
        removed_bytes = len(stdout) - limit
        stdout = (
            stdout[:half]
            + f"\n... [Truncated Middle: {removed_bytes} bytes removed by VibeHack] ...\n"
            + stdout[-half:]
        )
        truncated = True

    return ShellResult(stdout, res.stderr, res.exit_code, truncated)


async def _execute_stateless(
    command: str, timeout: int = 30, env=None, callback=None
) -> ShellResult:
    """
    DEPRECATED: Host execution has been permanently removed.
    This function exists only for backward compatibility and will always fail.
    """
    return ShellResult(
        "",
        "CRITICAL ERROR: Host execution is permanently disabled. All commands MUST run inside the Docker sandbox.",
        1,
        False,
    )


def _sanitize_output(text: str) -> str:
    """Redacts secrets, cleans triggers, and strips CLI noise like curl progress bars."""
    if not text:
        return ""

    # 1. Redact Secrets (Security Hardening)
    patterns = [
        (r"(sk-[a-zA-Z0-9]{30,})", "sk-***"),  # OpenAI / Generic
        (r"(AIza[a-zA-Z0-9_-]{30,})", "AIza***"),  # Google Gemini
        (r"(or-v1-[a-f0-9]{64,})", "or-v1-***"),  # OpenRouter
        (r"(ghp_[a-zA-Z0-9]{36,})", "ghp_***"),  # GitHub PAT
        (r"(xox[bap]-[a-zA-Z0-9-]{10,})", "slack-***"),  # Slack
        (
            r"(['\"]?password['\"]?\s*[:=]\s*['\"]?)[^'\"\s]+(['\"]?)",
            r"\1***\2",
        ),  # Generic Passwords
        (r"(?:AKIA|ASIA)[A-Z0-9]{16}", "AWS-KEY-***"),  # AWS Access Key
        (
            r"(?:\"|')?[a-zA-Z0-9/+=]{40}(?:\"|')?",
            "AWS-SECRET-***",
        ),  # AWS Secret (Potential)
    ]
    for pattern, replacement in patterns:
        if isinstance(replacement, str):
            text = re.sub(pattern, replacement, text)
        else:
            text = re.sub(pattern, replacement, text)

    # 2. Strip CLI Noise (Progress Bars)
    text = re.sub(
        r"%.*?Total.*?%.*?Received.*?%.*?Xferd.*?Average.*?Speed.*?Time.*?Time.*?Time.*?Current\s+Dload.*?Upload.*?Total.*?Spent.*?Left.*?Speed",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"\r?\n\s*\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+\d+\s+[\d.]+[MkG]?\s+[\d:]+\s+[\d:]+\s+[\d:]+\s+[\d.]+[MkG]?",
        "",
        text,
    )

    # 3. HTML Skeletonization (Extreme Token Saving)
    text = _skeletonize_html(text)

    # 4. Canonicalizing Whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)  # Collapse multiple spaces/tabs

    # 5. Clean Triggers to prevent prompt injection via command output
    for trigger in ["System:", "User:", "Assistant:", "Instruction:"]:
        text = text.replace(trigger, f"[Sanitized {trigger}]")

    return text.strip()


def _skeletonize_html(html: str) -> str:
    """Robust HTML strip using BeautifulSoup: only keeps attack-surface tags (form, input, a) with minimal attributes."""
    if (
        "<html" not in html.lower()
        and "<form" not in html.lower()
        and "<input" not in html.lower()
    ):
        return html  # Not HTML

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback to slightly less aggressive regex if BS4 is missing
        # 1. Strip style and script tags entirely
        html = re.sub(
            r"<(script|style|svg|noscript|iframe|header|footer|nav).*?>.*?</\1>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # 2. Preserve essential form/input attributes by placeholder (optional, complex for pure regex)
        # 3. Strip all other tags but keep content
        text = re.sub(r"<[^>]+>", " ", html)
        # 4. Collapse whitespace
        return re.sub(r"\s+", " ", text).strip()

    soup = BeautifulSoup(html, "html.parser")

    # 1. Nuke trash tags and their content
    for trash in soup(
        [
            "script",
            "style",
            "svg",
            "noscript",
            "iframe",
            "header",
            "footer",
            "nav",
            "aside",
            "head",
            "object",
            "embed",
            "canvas",
        ]
    ):
        trash.decompose()

    # 2. Extract essential tags
    essential_tags = [
        "form",
        "input",
        "button",
        "a",
        "select",
        "textarea",
        "title",
        "meta",
    ]
    essential_attrs = ["name", "value", "type", "action", "method", "href", "src"]

    # 3. Process every tag in the soup
    for tag in soup.find_all(True):
        if tag.name in essential_tags:
            # Keep the tag but strip attributes
            attrs = {}
            for attr in essential_attrs:
                if tag.has_attr(attr):
                    attrs[attr] = tag[attr]
            tag.attrs = attrs
        else:
            # For non-essential tags (div, span, p, etc), replace with their text content
            tag.unwrap()

    # 4. Clean up the resulting text
    result = soup.decode()

    # Remove excessive blank lines
    result = re.sub(r"\n\s*\n", "\n", result)
    return result.strip()
