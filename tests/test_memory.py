"""
Tests for the Long-Term Memory (LTM) SQLite backend.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture(autouse=True)
def temp_memory_db(tmp_path):
    """
    Redirects the memory DB to a temp path so tests don't pollute
    the user's real ~/.vibehack/memory.db.
    """
    mock_db = tmp_path / "memory.db"
    with patch("vibehack.memory.db.MEMORY_DB", mock_db):
        yield mock_db


class TestMemoryDB:

    def test_init_creates_db(self, temp_memory_db):
        from vibehack.memory.db import init_memory
        init_memory()
        assert temp_memory_db.exists()

    def test_record_and_retrieve_experience(self, temp_memory_db):
        from vibehack.memory.db import init_memory, record_experience, search_experience
        init_memory()

        record_experience(
            target="http://localhost:3000",
            tech="express.js",
            payload="curl -F 'file=@evil.sh' http://localhost:3000/api/upload",
            score=1,
            summary="Unrestricted File Upload on Express.js /api/upload"
        )

        results = search_experience("express")
        assert len(results) == 1
        payload, score, summary = results[0]
        assert "upload" in payload
        assert score == 1
        assert "Unrestricted" in summary

    def test_failed_experience_recorded(self, temp_memory_db):
        from vibehack.memory.db import init_memory, record_experience, search_experience
        init_memory()

        record_experience(
            target="http://10.0.0.5",
            tech="nginx",
            payload="' OR 1=1 --",
            score=-1,
            summary="SQLi attempt blocked by WAF"
        )

        results = search_experience("nginx")
        assert any(r[1] == -1 for r in results)

    def test_no_match_returns_empty(self, temp_memory_db):
        from vibehack.memory.db import init_memory, search_experience
        init_memory()

        results = search_experience("nonexistent_tech_xyz")
        assert results == []

    def test_limit_returns_max_5(self, temp_memory_db):
        from vibehack.memory.db import init_memory, record_experience, search_experience
        init_memory()

        for i in range(10):
            record_experience("target", "django", f"payload_{i}", 1, f"Finding {i}")

        results = search_experience("django")
        assert len(results) <= 5
