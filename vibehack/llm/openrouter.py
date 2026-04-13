import urllib.request
import json
import os
from vibehack.config import cfg

CACHE_FILE = cfg.HOME / "openrouter_models.json"

def get_openrouter_models(force_refresh=False):
    """Fetch OpenRouter models and cache them."""
    if not force_refresh and CACHE_FILE.exists():
        # Check if cache is older than 24h
        import time
        if time.time() - CACHE_FILE.stat().st_mtime < 86400:
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except:
                pass

    url = "https://openrouter.ai/api/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            models = [m["id"] for m in data.get("data", [])]
            # Save to cache
            with open(CACHE_FILE, "w") as f:
                json.dump(models, f)
            return models
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}")
        return []
