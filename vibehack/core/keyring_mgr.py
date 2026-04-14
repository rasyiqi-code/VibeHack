"""
vibehack/core/keyring_mgr.py — Secure storage for API keys.
"""
import os
from typing import Optional

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

SERVICE_NAME = "vibehack"

def set_api_key(provider: str, key: str):
    """Store an API key in the system keyring."""
    if KEYRING_AVAILABLE and key:
        try:
            keyring.set_password(SERVICE_NAME, provider.lower(), key)
            return True
        except Exception:
            return False
    return False

def get_api_key(provider: str) -> Optional[str]:
    """Retrieve an API key from the system keyring."""
    if KEYRING_AVAILABLE:
        try:
            return keyring.get_password(SERVICE_NAME, provider.lower())
        except Exception:
            return None
    return None

def delete_api_key(provider: str):
    """Remove an API key from the system keyring."""
    if KEYRING_AVAILABLE:
        try:
            keyring.delete_password(SERVICE_NAME, provider.lower())
            return True
        except Exception:
            return False
    return False
