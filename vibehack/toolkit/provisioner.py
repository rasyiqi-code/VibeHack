"""
vibehack/toolkit/provisioner.py — Pure Agnostic Tool Provisioner.

The registry has been purged. VibeHack no longer maintains a list of official tools.
The AI is now solely responsible for discovering installation methods via apt, pip, git,
or other means using its own internal knowledge and learned skills.
"""
from typing import Optional
from rich.console import Console

console = Console()

# Registry: PURGED. 
# AI must use shell commands (apt install, pip install, etc) directly.
DOWNLOADABLE_TOOLS = {}
APT_TOOLS = {}

def get_install_hint(tool_name: str) -> Optional[str]:
    """
    In the agnostic world, we don't give hints. 
    The AI knows how to install things or must figure it out.
    """
    return None

async def download_tool(tool_name: str) -> bool:
    """Legacy stub for compatibility with AI calls that might still try it."""
    console.print(f"[yellow]Auto-provisioner is retired. AI should install '{tool_name}' via shell.[/yellow]")
    return False
