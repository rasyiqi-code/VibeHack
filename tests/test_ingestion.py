import pytest
from unittest.mock import patch
from vibehack.memory.ingestion import detect_technology, ingest_session
from vibehack.llm.schemas import Finding

class TestDetectTechnology:
    def test_detects_known_technologies(self):
        assert detect_technology("running express server") == "express"
        assert detect_technology("nginx/1.18.0") == "nginx"
        assert detect_technology("found wp-login.php") == "wordpress"
        assert detect_technology("spring-boot application") == "spring"

    def test_case_insensitive_matching(self):
        assert detect_technology("Running Express Server") == "express"
        assert detect_technology("NGINX/1.18.0") == "nginx"

    def test_unknown_technology(self):
        assert detect_technology("running some obscure custom server") == "unknown"
        assert detect_technology("") == "unknown"

class TestIngestSession:
    @patch("vibehack.memory.ingestion.record_experiences")
    def test_successful_command_with_finding(self, mock_record):
        # Mock record_experiences to return the number of items it was given
        mock_record.side_effect = lambda x: len(x)

        history = [
            {"role": "assistant", "content": '{"thought": "Try express exploit", "raw_command": "curl http://vuln/api"}'},
            {"role": "user", "content": "vuln data EXIT_CODE: 0"}
        ]
        finding = Finding(severity="high", title="vuln", description="test", evidence="curl http://vuln/api")

        recorded = ingest_session("http://target", history, [finding])

        assert recorded == 1
        mock_record.assert_called_once()
        experiences = mock_record.call_args[0][0]

        target, tech, command, score, summary = experiences[0]
        assert target == "http://target"
        assert tech == "express"
        assert command == "curl http://vuln/api"
        assert score == 1
        assert summary == "curl http://vuln/api... → exit:0"

    @patch("vibehack.memory.ingestion.record_experiences")
    def test_successful_command_without_finding_but_good_exit_code(self, mock_record):
        mock_record.side_effect = lambda x: len(x)

        history = [
            {"role": "assistant", "content": '{"thought": "scan", "raw_command": "nmap -p 80 target"}'},
            # Length of user content > 50 characters, and exit code 0
            {"role": "user", "content": "A" * 60 + " EXIT_CODE: 0"}
        ]

        recorded = ingest_session("target", history, [])

        assert recorded == 1
        experiences = mock_record.call_args[0][0]
        score = experiences[0][3]
        assert score == 1

    @patch("vibehack.memory.ingestion.record_experiences")
    def test_failed_command(self, mock_record):
        mock_record.side_effect = lambda x: len(x)

        history = [
            {"role": "assistant", "content": '{"thought": "bad command", "raw_command": "invalid"}'},
            {"role": "user", "content": "command not found EXIT_CODE: 127"}
        ]

        recorded = ingest_session("target", history, [])

        assert recorded == 1
        experiences = mock_record.call_args[0][0]
        score = experiences[0][3]
        assert score == -1

    @patch("vibehack.memory.ingestion.record_experiences")
    def test_ignores_invalid_json(self, mock_record):
        mock_record.side_effect = lambda x: len(x)

        history = [
            {"role": "assistant", "content": "This is not valid JSON"},
            {"role": "user", "content": "EXIT_CODE: 0"}
        ]

        recorded = ingest_session("target", history, [])

        assert recorded == 0
        mock_record.assert_called_once_with([])
