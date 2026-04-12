"""
Tests for session persistence (save / load / list).
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch


@pytest.fixture(autouse=True)
def temp_sessions_dir(tmp_path):
    """Redirect sessions to a temp directory."""
    sessions_dir = tmp_path / "sessions"
    with patch("vibehack.session.persistence.SESSIONS_DIR", sessions_dir):
        yield sessions_dir


class TestSessionPersistence:

    def _make_state(self, session_id="test_session_001", target="http://localhost:3000"):
        return {
            "session_id": session_id,
            "target": target,
            "mode": "dev-safe",
            "unchained": False,
            "history": [
                {"role": "system", "content": "You are a security agent..."},
                {"role": "assistant", "content": '{"thought": "start recon", "raw_command": "nmap localhost", "is_destructive": false}'},
                {"role": "user", "content": "STDOUT:\nPORT   STATE SERVICE\n80/tcp open  http"},
            ],
            "findings": [
                {"severity": "high", "title": "Open Port 80", "description": "HTTP open", "evidence": None, "remediation": None}
            ],
            "auto_allow": False,
        }

    def test_save_creates_file(self, temp_sessions_dir):
        from vibehack.session.persistence import save_session
        state = self._make_state()
        path = save_session("test_session_001", state)
        assert path.exists()

    def test_load_returns_correct_state(self, temp_sessions_dir):
        from vibehack.session.persistence import save_session, load_session
        state = self._make_state()
        save_session("test_session_001", state)

        loaded = load_session("test_session_001")
        assert loaded is not None
        assert loaded["target"] == "http://localhost:3000"
        assert loaded["mode"] == "dev-safe"
        assert len(loaded["history"]) == 3
        assert len(loaded["findings"]) == 1

    def test_load_nonexistent_returns_none(self, temp_sessions_dir):
        from vibehack.session.persistence import load_session
        result = load_session("does_not_exist_xyz")
        assert result is None

    def test_list_sessions(self, temp_sessions_dir):
        from vibehack.session.persistence import save_session, list_sessions
        save_session("alpha_session", self._make_state("alpha_session"))
        save_session("beta_session", self._make_state("beta_session"))

        sessions = list_sessions()
        assert "alpha_session" in sessions
        assert "beta_session" in sessions
        assert len(sessions) == 2

    def test_overwrite_session(self, temp_sessions_dir):
        from vibehack.session.persistence import save_session, load_session
        state = self._make_state()
        save_session("test_session_001", state)

        # Modify and save again
        state["auto_allow"] = True
        save_session("test_session_001", state)

        loaded = load_session("test_session_001")
        assert loaded["auto_allow"] is True
