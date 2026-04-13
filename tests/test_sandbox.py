import pytest
import subprocess
from unittest.mock import patch
from vibehack.core.sandbox import check_docker

@patch("subprocess.run")
def test_check_docker_success(mock_run):
    """Test that check_docker returns True when subprocess.run succeeds."""
    # Mocking successful run (does not raise an exception)
    mock_run.return_value = subprocess.CompletedProcess(args=["docker", "info"], returncode=0)

    assert check_docker() is True
    mock_run.assert_called_once_with(["docker", "info"], capture_output=True, check=True)

@patch("subprocess.run")
def test_check_docker_called_process_error(mock_run):
    """Test that check_docker returns False when docker command fails."""
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["docker", "info"])

    assert check_docker() is False
    mock_run.assert_called_once_with(["docker", "info"], capture_output=True, check=True)

@patch("subprocess.run")
def test_check_docker_file_not_found(mock_run):
    """Test that check_docker returns False when docker CLI is not found."""
    mock_run.side_effect = FileNotFoundError()

    assert check_docker() is False
    mock_run.assert_called_once_with(["docker", "info"], capture_output=True, check=True)
