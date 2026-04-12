"""
Tests for the Raw Shell execution engine.
"""
import pytest
from vibehack.core.shell import execute_shell, ShellResult


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
        assert len(result.stdout) <= 2500 + len("\n... [Output Truncated by VibeHack]") + 5

    def test_timeout_handling(self):
        """A hanging command must be killed after timeout."""
        result = execute_shell("sleep 60", timeout=1)
        assert result.exit_code == 124  # Timeout exit code
        assert "timed out" in result.stderr.lower()

    def test_exit_code_propagation(self):
        result = execute_shell("exit 42", )
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
