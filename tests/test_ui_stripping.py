import pytest
import re
from unittest.mock import MagicMock
from vibehack.ui.tui import log_to_pane

class MockBuffer:
    def __init__(self):
        self.text = ""
        self.cursor_position = 0

class MockREPL:
    def __init__(self):
        self.logs_buffer = MockBuffer()
        self.history_buffer = MockBuffer()

def test_rich_tag_stripping():
    repl = MockREPL()
    
    # Test single tags
    log_to_pane(repl, "logs", "Hello [bold]World[/bold]")
    assert "Hello World" in repl.logs_buffer.text
    
    # Test composite tags (the fix)
    log_to_pane(repl, "logs", "Session: [bold cyan]12345[/bold cyan]")
    assert "Session: 12345" in repl.logs_buffer.text
    
    # Test generic closing tag
    log_to_pane(repl, "logs", "Multiple tags [red][bold]here[/][/]")
    assert "Multiple tags here" in repl.logs_buffer.text
    
    # Test technical patterns that should NOT be stripped
    log_to_pane(repl, "logs", "Connecting to [127.0.0.1]")
    assert "[127.0.0.1]" in repl.logs_buffer.text
    
    log_to_pane(repl, "logs", "Status: [DEBUG]")
    assert "[DEBUG]" in repl.logs_buffer.text

def test_html_tag_stripping():
    repl = MockREPL()
    
    # Test prompt-toolkit style HTML tags
    log_to_pane(repl, "history", "User: <ansicyan><b>input</b></ansicyan>")
    assert "User: input" in repl.history_buffer.text
    
    # Test nested tags
    log_to_pane(repl, "history", "<i><u>Underlined Italic</u></i>")
    assert "Underlined Italic" in repl.history_buffer.text

def test_session_info_rendering():
    from vibehack.ui.tui import display_session_info
    from unittest.mock import patch
    
    # We just want to ensure it doesn't crash when called with typical inputs
    with patch('rich.console.Console.print') as mock_print:
        display_session_info("http://localhost", "dev-safe", False, "sess_123", 50)
        assert mock_print.called
        
        display_session_info("target", "unchained", True, "sess_456", 0)
        assert mock_print.call_count == 2
