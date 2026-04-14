"""
Tests for the Raw Shell execution engine.
"""

import pytest
import asyncio
import unittest.mock
from vibehack.core.shell import ShellResult, execute_shell
from vibehack.config import cfg

@pytest.mark.asyncio
class TestShellExecution:

    async def test_basic_command_stdout(self):
        result = await execute_shell("echo 'hello vibehack'")
        assert result.exit_code == 0
        assert "hello vibehack" in result.stdout
        assert result.truncated is False

    async def test_stderr_captured(self):
        # Note: PersistentSession redirects stderr to stdout or captures it via delimit
        # For stateless fallback it captures stderr
        result = await execute_shell("ls /nonexistent_path_xyz")
        assert result.exit_code != 0
        assert result.stdout != "" or result.stderr != ""

    async def test_pipe_support(self):
        """Raw shell must support bash piping."""
        result = await execute_shell("echo 'port 80\nport 443' | grep 443")
        assert result.exit_code == 0
        assert "443" in result.stdout

    async def test_output_truncation(self):
        """Output exceeding the limit must be truncated."""
        result = await execute_shell("python3 -c \"print('A' * 5000)\"", truncate_limit=2500)
        assert result.truncated is True
        assert len(result.stdout) < 5000

    async def test_exit_code_propagation(self):
        result = await execute_shell("exit 42")
        assert result.exit_code == 42


@pytest.mark.asyncio
class TestSandboxShellExecution:
    @pytest.fixture(autouse=True)
    def setup_sandbox(self):
        # Temporarily enable sandbox
        original_sandbox_enabled = cfg.SANDBOX_ENABLED
        cfg.SANDBOX_ENABLED = True
        yield
        cfg.SANDBOX_ENABLED = original_sandbox_enabled

    @unittest.mock.patch("asyncio.create_subprocess_exec")
    async def test_sandbox_execute_shell(self, mock_exec):
        # Mock the process creation
        class MockProcess:
            def __init__(self):
                self.returncode = 0
                # stdin.write is synchronous in asyncio, but drain is async
                self.stdin = unittest.mock.MagicMock()
                self.stdin.drain = unittest.mock.AsyncMock()
                self.stdout = unittest.mock.AsyncMock()
                self.stderr = unittest.mock.AsyncMock()

            async def wait(self): return 0
            def kill(self): pass

        mock_proc = MockProcess()
        # Mock readline to return delimiter eventually
        mock_proc.stdout.readline.side_effect = [
            b"test output\n",
            b"0\n",
            b"---VIBEHACK_COMMAND_BOUNDARY_SALT---\n",
            b""
        ]
        mock_exec.return_value = mock_proc

        # We need to mock the salt generation to match our side_effect
        with unittest.mock.patch("os.urandom", return_value=bytes.fromhex("53414c54")):
             result = await execute_shell("echo 'hello'")

        assert "test output" in result.stdout
        assert result.exit_code == 0
