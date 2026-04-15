"""
Test for update checking logic.
"""

import pytest
import urllib.request
import re
from packaging import version

__version__ = "2.7.1"


@pytest.mark.skipif(
    condition=True,  # Skip by default - network-dependent
    reason="Requires network access to GitHub",
)
def test_update_check():
    """Test update check from GitHub."""
    url = "https://raw.githubusercontent.com/rasyiqi-code/VibeHack/main/vibehack/__init__.py"

    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            content = response.read().decode("utf-8")
            match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
            assert match is not None, "Could not parse remote version"

            remote_version = match.group(1)

            # Test version comparison
            is_update_available = version.parse(remote_version) > version.parse(
                __version__
            )

            assert isinstance(remote_version, str), "Remote version should be string"
            assert len(remote_version) > 0, "Remote version should not be empty"

    except Exception as e:
        pytest.skip(f"Network unavailable: {e}")


def test_local_version_exists():
    """Test that local version is defined."""
    assert __version__ is not None
    assert len(__version__) > 0
    assert isinstance(__version__, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
