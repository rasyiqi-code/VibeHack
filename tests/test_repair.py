import pytest
from vibehack.llm.provider import _repair_json

def test_repair_json_valid_direct():
    """Test parsing a perfectly valid JSON string directly."""
    text = '{"key": "value", "number": 42}'
    result = _repair_json(text)
    assert result == {"key": "value", "number": 42}

def test_repair_json_with_whitespace():
    """Test parsing a valid JSON string with leading/trailing whitespace."""
    text = '\n   {"key": "value"} \t\n'
    result = _repair_json(text)
    assert result == {"key": "value"}

def test_repair_json_markdown_fences():
    """Test parsing JSON wrapped in markdown fences."""
    text = '```json\n{"key": "value"}\n```'
    result = _repair_json(text)
    assert result == {"key": "value"}

    text_no_json = '```\n{"key": "value"}\n```'
    result = _repair_json(text_no_json)
    assert result == {"key": "value"}

def test_repair_json_leading_trailing_prose():
    """Test parsing JSON embedded within leading and trailing text."""
    text = 'Here is the JSON you requested:\n\n{"key": "value", "nested": {"a": 1}}\n\nI hope this helps!'
    result = _repair_json(text)
    assert result == {"key": "value", "nested": {"a": 1}}

def test_repair_json_markdown_with_prose():
    """Test parsing JSON wrapped in markdown and surrounded by prose."""
    text = 'Sure, here it is:\n```json\n{"key": "value"}\n```\nDone.'
    result = _repair_json(text)
    assert result == {"key": "value"}

def test_repair_json_invalid_json_format():
    """Test parsing an invalid JSON format inside valid braces."""
    # Note: Currently _repair_json just does json.loads on the {...} block.
    # If the block itself is invalid JSON, it returns None.
    text = '{"key": "value", }'  # trailing comma makes it invalid JSON
    result = _repair_json(text)
    assert result is None

def test_repair_json_no_json():
    """Test parsing a string with no JSON-like structures."""
    text = 'This is just a regular string without any brackets.'
    result = _repair_json(text)
    assert result is None

def test_repair_json_empty_string():
    """Test parsing an empty string."""
    text = ''
    result = _repair_json(text)
    assert result is None

def test_repair_json_malformed_unrecoverable():
    """Test parsing where braces exist but it is fundamentally not JSON."""
    text = 'Here is a block { not valid json }'
    result = _repair_json(text)
    assert result is None
