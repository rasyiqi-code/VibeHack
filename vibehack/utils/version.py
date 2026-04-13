import urllib.request
import re
from typing import Optional

def get_remote_version() -> Optional[str]:
    """Fetch the latest version string from GitHub's pyproject.toml."""
    url = "https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/pyproject.toml"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            content = response.read().decode('utf-8')
            match = re.search(r'version = "(.*)"', content)
            if match:
                return match.group(1)
    except Exception:
        return None
