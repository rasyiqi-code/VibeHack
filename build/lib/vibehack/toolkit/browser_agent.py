import os
import re
import sys
import subprocess
import tempfile
import asyncio
import importlib.util
from rich.console import Console
from vibehack.config import cfg

console = Console()


def ensure_playwright():
    if importlib.util.find_spec("playwright") is not None:
        return

    else:
        console.print(
            "[dim yellow]Playwright missing. Auto-installing dependencies...[/dim yellow]",
            err=True,
        )
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True
            )
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"], check=True
            )
            console.print(
                "[dim green]Playwright installed successfully.[/dim green]", err=True
            )
        except subprocess.CalledProcessError as e:
            console.print(
                f"[bold red]Failed to install playwright: {e}[/bold red]", err=True
            )
            sys.exit(1)


def _build_messages(url: str, action: str) -> list[dict[str, str]]:
    system_prompt = f"""You are VibeHack's Headless Browser Sub-Agent.
Your job is to translate the user's high-level action into a synchronous Python script using Playwright.
The script MUST navigate to: {url}

RULES:
1. ONLY return valid Python code enclosed in ```python ... ```. No prose, no markdown output outside the block.
2. Use `from playwright.sync_api import sync_playwright`.
3. Use a headless Chromium browser.
4. Set a generous timeout (e.g., 10 seconds wait) to let SPAs load.
5. Extract whatever information the user requested, and `print()` it clearly so it can be read via stdout.
6. If the target is a login bypass or XSS injection, perform the `fill` and `click`, then print the resulting URL or alert triggers.
7. Always gracefully close the browser and context at the end.
"""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Action to perform: {action}"},
    ]


async def _generate_script_content(url: str, action: str) -> str:
    from litellm import acompletion

    api_key = os.getenv("VH_API_KEY")
    model = os.getenv("VH_MODEL", "gpt-4o")

    if not api_key and not cfg.VH_API_BASE:
        console.print(
            "[bold red]API Key (VH_API_KEY) or VH_API_BASE is required for sub-agent.[/bold red]",
            err=True,
        )
        sys.exit(1)

    messages = _build_messages(url, action)
    kwargs = {"model": model, "messages": messages}

    if cfg.VH_API_BASE:
        kwargs["api_base"] = cfg.VH_API_BASE
        if not api_key:
            kwargs["api_key"] = "dummy"
    else:
        kwargs["api_key"] = api_key
        if not "/" in model:
            kwargs["model"] = f"openrouter/{model}"

    try:
        response = await acompletion(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        console.print(
            f"[bold red]LLM failed to generate script: {e}[/bold red]", err=True
        )
        sys.exit(1)


def _safe_run(coro):
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


def _extract_python_code(content: str) -> str:
    match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
    if not match:
        script_code = content.replace("```python", "").replace("```", "").strip()
    else:
        script_code = match.group(1).strip()

    if not script_code.startswith("from") and not script_code.startswith("import"):
        console.print("[red]LLM generated invalid script.[/red]", err=True)
        console.print(script_code, err=True)
        sys.exit(1)

    return script_code


def _execute_script(script_code: str, action: str):
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write(script_code)
        temp_path = f.name

    console.print(
        f"[dim cyan]Executing Headless Script ({action})...[/dim cyan]", err=True
    )
    try:
        result = subprocess.run(
            [sys.executable, temp_path], capture_output=True, text=True, timeout=60
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[Browser Error]:\n{result.stderr}"
        if not output.strip():
            output = "[No stdout produced by browser script]"
        print(output)
    except subprocess.TimeoutExpired:
        print("[Error] Playwright script execution timed out after 60 seconds.")
    finally:
        os.unlink(temp_path)


def run_browser_subagent(url: str, action: str):
    ensure_playwright()
    content = _safe_run(_generate_script_content(url, action))
    script_code = _extract_python_code(content)
    _execute_script(script_code, action)


def main():
    if len(sys.argv) < 3:
        print("Usage: vibehack-browser <url> <action>")
        sys.exit(1)

    run_browser_subagent(sys.argv[1], " ".join(sys.argv[2:]))


if __name__ == "__main__":
    main()
