import os
import re
import sys
import subprocess
import tempfile
from rich.console import Console
from vibehack.config import cfg

console = Console()

def ensure_playwright():
    try:
        import playwright
        return
    except ImportError:
        console.print("[dim yellow]Playwright missing. Auto-installing dependencies...[/dim yellow]", err=True)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            console.print("[dim green]Playwright installed successfully.[/dim green]", err=True)
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Failed to install playwright: {e}[/bold red]", err=True)
            sys.exit(1)

def run_browser_subagent(url: str, action: str):
    ensure_playwright()
    
    # We must construct the sub-agent prompt
    api_key = os.getenv("VH_API_KEY")
    model = os.getenv("VH_MODEL", "gpt-4o")
    
    if not api_key and not cfg.VH_API_BASE:
        console.print("[bold red]API Key (VH_API_KEY) or VH_API_BASE is required for sub-agent.[/bold red]", err=True)
        sys.exit(1)
        
    from litellm import acompletion
    import asyncio
    
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Action to perform: {action}"}
    ]

    async def _generate():
        import litellm
        
        # Strip openrouter if using native litellm aliases for certain endpoints
        target_model = model
        kwargs = {"model": target_model, "messages": messages}
        
        if cfg.VH_API_BASE: # Support local LLMs via OpenRouter/OpenAI drop-in format
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
            console.print(f"[bold red]LLM failed to generate script: {e}[/bold red]", err=True)
            sys.exit(1)
            
    content = asyncio.run(_generate())
    
    # Extract python code
    match = re.search(r"```python\n(.*?)\n```", content, re.DOTALL)
    if not match:
        # Fallback if the LLM forgot the code block
        script_code = content.replace("```python", "").replace("```", "").strip()
    else:
        script_code = match.group(1).strip()
        
    if not script_code.startswith("from") and not script_code.startswith("import"):
        console.print("[red]LLM generated invalid script.[/red]", err=True)
        console.print(script_code, err=True)
        sys.exit(1)
        
    # Execute script safely in a temp file
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write(script_code)
        temp_path = f.name
        
    console.print(f"[dim cyan]Executing Headless Script ({action})...[/dim cyan]", err=True)
    try:
        result = subprocess.run([sys.executable, temp_path], capture_output=True, text=True, timeout=60)
        output = result.stdout
        if result.stderr:
            output += f"\n[Browser Error]:\n{result.stderr}"
        if not output.strip():
            output = "[No stdout produced by browser script]"
        # Print actual stdout for the LLM pipeline
        print(output)
    except subprocess.TimeoutExpired:
        print("[Error] Playwright script execution timed out after 60 seconds.")
    finally:
        os.unlink(temp_path)

def main():
    if len(sys.argv) < 3:
        print("Usage: vibehack-browser <url> <action>")
        sys.exit(1)
    
    run_browser_subagent(sys.argv[1], " ".join(sys.argv[2:]))

if __name__ == "__main__":
    main()
