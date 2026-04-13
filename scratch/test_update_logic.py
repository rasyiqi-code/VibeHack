import urllib.request
import re
from packaging import version

__version__ = "2.7.1"
url = "https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/vibehack/__init__.py"

print(f"Checking for updates at {url}...")
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        content = response.read().decode('utf-8')
        print(f"Content: {content}")
        match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
        if not match:
            print("Error: Could not parse remote version file.")
        else:
            remote_version = match.group(1)
            print(f"Remote version: {remote_version}")
            print(f"Local version: {__version__}")
            if version.parse(remote_version) > version.parse(__version__):
                print(f"A new version of VibeHack is available: {remote_version}")
            else:
                print(f"VibeHack is up to date (v{__version__}).")
except Exception as e:
    print(f"Update check failed: {e}")
