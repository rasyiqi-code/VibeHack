"""
Tests for the Raw Shell execution engine.
"""

import pytest
import asyncio
import unittest.mock
import os
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
        result = await execute_shell("python3 -c \"print('A ' * 2500)\"", truncate_limit=2500)
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
        # Mock the process creation with specific sync/async boundaries
        class MockStream:
            def __init__(self, data, stdin_mock):
                self.data = data
                self.ptr = 0
                self.stdin = stdin_mock
                self.read = unittest.mock.AsyncMock(side_effect=self._read)
                self.readline = unittest.mock.AsyncMock(side_effect=self._readline)

            async def _read(self, n):
                # Only return real data IF something has been written to stdin
                # This bypasses the 'cleanup' loop which reads before writing
                if self.stdin.write.call_count == 0:
                    return b""
                
                if self.ptr >= len(self.data): return b""
                res = self.data[self.ptr]
                self.ptr += 1
                return res

            async def _readline(self):
                # Fallback for other tests if they use readline
                if self.ptr >= len(self.data): return b""
                res = self.data[self.ptr]
                self.ptr += 1
                return res

        class MockStdin:
            def __init__(self):
                self.write = unittest.mock.Mock()
                self.drain = unittest.mock.AsyncMock()

        class MockProcess:
            def __init__(self):
                self.returncode = 0
                self.stdin = MockStdin()
                self.stdout = MockStream([
                    b"test output\n",
                    b"0\n",
                    b"---VIBEHACK_BOUNDARY_53414c5453414c54---\n",
                    b""
                ], self.stdin)
                self.stderr = MockStream([b""], self.stdin)

            async def wait(self): return 0
            def kill(self): pass

        mock_proc = MockProcess()
        mock_exec.return_value = mock_proc

        # Use 8-byte salt as required by v4.0 shell logic
        with unittest.mock.patch("os.urandom", return_value=bytes.fromhex("53414c5453414c54")):
             result = await execute_shell("echo 'hello'")

        assert "test output" in result.stdout
        assert result.exit_code == 0
