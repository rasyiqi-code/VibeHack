import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock dependencies that might be missing in the environment
mock_dotenv = MagicMock()
sys.modules["dotenv"] = mock_dotenv

import pytest
from vibehack.toolkit.manager import ensure_bin_dir, get_toolkit_env, is_tool_installed, get_tool_path

@pytest.fixture
def mock_cfg(tmp_path):
    bin_dir = tmp_path / "bin"
    with patch("vibehack.toolkit.manager.cfg") as mock:
        mock.BIN_DIR = bin_dir
        yield mock

def test_ensure_bin_dir(mock_cfg):
    path = ensure_bin_dir()
    assert path == mock_cfg.BIN_DIR
    assert path.exists()
    assert path.is_dir()

def test_get_toolkit_env(mock_cfg):
    with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
        env = get_toolkit_env()
        bin_path = str(mock_cfg.BIN_DIR)
        assert env["PATH"].startswith(bin_path)
        assert "/usr/bin" in env["PATH"]

def test_get_toolkit_env_already_present(mock_cfg):
    bin_path = str(mock_cfg.BIN_DIR)
    with patch.dict(os.environ, {"PATH": f"{bin_path}{os.pathsep}/usr/bin"}):
        env = get_toolkit_env()
        # Should not double prepend
        assert env["PATH"] == f"{bin_path}{os.pathsep}/usr/bin"

def test_is_tool_installed_in_vh_bin(mock_cfg):
    mock_cfg.BIN_DIR.mkdir(parents=True)
    tool_path = mock_cfg.BIN_DIR / "mytool"
    tool_path.touch(mode=0o755)

    assert is_tool_installed("mytool") is True

def test_is_tool_installed_in_system_path(mock_cfg):
    # Ensure it's NOT in VH_BIN
    with patch("shutil.which", return_value="/usr/bin/git"):
        assert is_tool_installed("git") is True

def test_is_tool_not_installed(mock_cfg):
    with patch("shutil.which", return_value=None):
        assert is_tool_installed("nonexistent_tool_12345") is False

def test_get_tool_path_vh_bin(mock_cfg):
    mock_cfg.BIN_DIR.mkdir(parents=True)
    tool_path = mock_cfg.BIN_DIR / "mytool"
    tool_path.touch(mode=0o755)

    assert get_tool_path("mytool") == str(tool_path)

def test_get_tool_path_system(mock_cfg):
    with patch("shutil.which", return_value="/usr/bin/git"):
        assert get_tool_path("git") == "/usr/bin/git"

def test_get_tool_path_not_found(mock_cfg):
    with patch("shutil.which", return_value=None):
        assert get_tool_path("nonexistent_tool_12345") is None
