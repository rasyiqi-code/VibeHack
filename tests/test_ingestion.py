import pytest
from unittest.mock import patch
from vibehack.memory.ingestion import detect_technologies, ingest_session
from vibehack.llm.schemas import Finding

class TestDetectTechnologies:
    def test_detects_universal_banners(self):
        # The new engine detects "Name/Version" patterns dynamically
        assert "nginx" in detect_technologies("Server: nginx/1.18.0")
        assert "apache" in detect_technologies("Apache/2.4.41 (Ubuntu)")
        assert "openssh" in detect_technologies("SSH-2.0-OpenSSH_8.2p1")
        assert "php" in detect_technologies("X-Powered-By: PHP/7.4.3")

    def test_case_sensitivity(self):
        # Regex is case-insensitive for the name part
        assert "nginx" in detect_technologies("SERVER: NGINX/1.18.0")

    def test_unknown_technology(self):
        # Plain text without Version suffix is now ignored to avoid false positives
        assert detect_technologies("running some obscure custom server") == ["unknown"]
        assert detect_technologies("") == ["unknown"]

class TestIngestSession:
    @patch("vibehack.memory.ingestion.record_experiences")
    def test_successful_command_with_finding(self, mock_record):
        mock_record.side_effect = lambda x: len(x)

        # We use a banner-rich output to trigger technology detection
        # Command and evidence must match exactly for the score to be 1
        history = [
            {"role": "assistant", "content": '{"thought": "Check nginx", "raw_command": "curl -I http://target"}'},
            {"role": "user", "content": "HTTP/1.1 200 OK\nServer: nginx/1.18.0\nEXIT_CODE: 0"}
        ]
        finding = Finding(severity="high", title="vuln", description="test", evidence="curl -I http://target")

        recorded = ingest_session("http://target", history, [finding])

        assert recorded >= 1
        mock_record.assert_called_once()
        experiences = mock_record.call_args[0][0]

        target, tech, command, score, summary = experiences[0]
        assert target == "http://target"
        # We check that nginx was at least one of the detected techs
        all_techs = [e[1] for e in experiences]
        assert "nginx" in all_techs
        assert command == "curl -I http://target"
        assert score == 1
