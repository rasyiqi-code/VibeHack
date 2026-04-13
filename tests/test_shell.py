"""
Tests for the Raw Shell execution engine.
"""

import pytest

from vibehack.core.shell import ShellResult, execute_shell


class TestShellExecution:

    def test_basic_command_stdout(self):
        result = execute_shell("echo 'hello vibehack'")
        assert result.exit_code == 0
        assert "hello vibehack" in result.stdout
        assert result.stderr == ""
        assert result.truncated is False

    def test_stderr_captured(self):
        result = execute_shell("ls /nonexistent_path_xyz")
        assert result.exit_code != 0
        assert result.stderr != ""

    def test_pipe_support(self):
        """Raw shell must support bash piping."""
        result = execute_shell("echo -e 'port 80\\nport 443' | grep 443")
        assert result.exit_code == 0
        assert "443" in result.stdout

    def test_output_truncation(self):
        """Output exceeding the limit must be truncated."""
        # Generate a large output (>2500 chars)
        result = execute_shell("python3 -c \"print('A' * 5000)\"", truncate_limit=2500)
        assert result.truncated is True
        # Original output is 5001 chars (5000 'A' + newline). Truncated stdout uses original len.
        removed_bytes = 5001 - 2500
        truncation_msg = (
            f"\n... [Truncated Middle: {removed_bytes} bytes removed by VibeHack] ...\n"
        )
        assert len(result.stdout) <= 2500 + len(truncation_msg) + 5

    def test_timeout_handling(self):
        """A hanging command must be killed after timeout."""
        result = execute_shell("sleep 60", timeout=1)
        assert result.exit_code == 124  # Timeout exit code
        assert "timed out" in result.stderr.lower()

    def test_exit_code_propagation(self):
        result = execute_shell(
            "exit 42",
        )
        assert result.exit_code == 42

    def test_env_path_injection(self):
        """Confirm that a custom env with modified PATH is respected."""
        import os

        env = os.environ.copy()
        env["TEST_VH_VAR"] = "injected_by_vibehack"
        result = execute_shell("echo $TEST_VH_VAR", env=env)
        assert "injected_by_vibehack" in result.stdout

    def test_result_is_namedtuple(self):
        result = execute_shell("echo test")
        assert isinstance(result, ShellResult)
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")
        assert hasattr(result, "exit_code")
        assert hasattr(result, "truncated")


import asyncio
import os
import unittest.mock

import pytest

from vibehack.config import cfg
from vibehack.core.shell import execute_shell, execute_shell_async


class TestSandboxShellExecution:
    @pytest.fixture(autouse=True)
    def setup_sandbox(self):
        # Temporarily enable sandbox
        original_sandbox_enabled = cfg.SANDBOX_ENABLED
        cfg.SANDBOX_ENABLED = True
        yield
        cfg.SANDBOX_ENABLED = original_sandbox_enabled

    @unittest.mock.patch("subprocess.run")
    def test_sandbox_execute_shell(self, mock_run):
        # Mock the run to just return a dummy completed process
        # because docker isn't running in our test env.
        import subprocess

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="test out", stderr=""
        )

        result = execute_shell("echo 'hello' | grep hello")

        assert result.exit_code == 0
        assert "test out" in result.stdout

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        called_cmd = args[0]

        # Verify it passed a list and shell=False
        assert isinstance(called_cmd, list)
        assert called_cmd[0] == "docker"
        assert called_cmd[-2] == "-c"
        assert called_cmd[-1] == "echo 'hello' | grep hello"
        assert kwargs.get("shell") is False

    @pytest.mark.asyncio
    @unittest.mock.patch("asyncio.create_subprocess_exec")
    async def test_sandbox_execute_shell_async(self, mock_exec):
        # We need to mock create_subprocess_exec to return a mock process
        class MockProcess:
            def __init__(self):
                self.returncode = 0

            async def wait(self):
                return self.returncode

            def kill(self):
                pass

        class MockStreamReader:
            def __init__(self, data):
                self._data = [data.encode()] if data else []

            async def readline(self):
                if self._data:
                    return self._data.pop(0)
                return b""

        mock_proc = MockProcess()
        mock_proc.stdout = MockStreamReader("async out\n")
        mock_proc.stderr = MockStreamReader("")
        mock_exec.return_value = mock_proc

        result = await execute_shell_async("echo 'hello' | grep hello")

        assert result.exit_code == 0
        assert "async out" in result.stdout

        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args

        # args are the expanded *target_command list
        assert args[0] == "docker"
        assert args[-2] == "-c"
        assert args[-1] == "echo 'hello' | grep hello"
