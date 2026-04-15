"""
Test for Docker container debugging.
"""

import pytest
import subprocess
import os


def is_docker_available():
    """Check if Docker is available."""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_container_running():
    """Check if vibehack_sandbox is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=vibehack_sandbox"],
            capture_output=True,
            timeout=5,
        )
        return result.stdout.strip() != b""
    except Exception:
        return False


@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
class TestContainerDebug:
    """Test container state and permissions."""

    def test_container_exists(self):
        """Test that vibehack_sandbox container exists."""
        result = subprocess.run(
            ["docker", "ps", "-a", "-q", "-f", "name=vibehack_sandbox"],
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() != "", "Container vibehack_sandbox should exist"

    def test_container_running(self):
        """Test that container is running."""
        if not is_container_running():
            pytest.skip("Container not running - will auto-start on use")

        result = subprocess.run(
            ["docker", "exec", "vibehack_sandbox", "id"], capture_output=True, text=True
        )
        assert "root" in result.stdout, "Should run as root inside container"

    def test_workspace_writable(self):
        """Test that workspace directory is writable."""
        if not is_container_running():
            pytest.skip("Container not running")

        result = subprocess.run(
            [
                "docker",
                "exec",
                "vibehack_sandbox",
                "bash",
                "-c",
                "echo test > /root/workspace/test.txt && cat /root/workspace/test.txt",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Workspace should be writable"
        assert "test" in result.stdout, "Test file should be readable"

    def test_readonly_enforced(self):
        """Test that root filesystem is read-only (except workspace)."""
        if not is_container_running():
            pytest.skip("Container not running")

        result = subprocess.run(
            ["docker", "exec", "vibehack_sandbox", "touch", "/test.txt"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Root filesystem should be read-only"
        assert "Read-only" in result.stderr or "Permission denied" in result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
