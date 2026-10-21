import json
from unittest.mock import patch, MagicMock

from factoids import generate_factoids, parse_factoid_response, FactoidParseError

VALID_JSON = json.dumps([
    {"text": "Recorded in one take.", "category": "recording"},
    {"text": "Hit #1 in 7 countries.", "category": "chart"},
    {"text": "Director had 48 hours to shoot.", "category": "production"},
    {"text": "A", "category": "trivia"},
    {"text": "B", "category": "trivia"},
    {"text": "C", "category": "trivia"},
    {"text": "D", "category": "trivia"},
    {"text": "E", "category": "trivia"},
])


def test_parse_valid_json():
    result = parse_factoid_response(VALID_JSON)
    assert len(result) == 8
    assert result[0]["text"] == "Recorded in one take."
    assert result[0]["category"] == "recording"


def test_parse_strips_markdown_fences():
    wrapped = f"```json\n{VALID_JSON}\n```"
    result = parse_factoid_response(wrapped)
    assert len(result) == 8


def test_parse_strips_plain_code_fences():
    wrapped = f"```\n{VALID_JSON}\n```"
    result = parse_factoid_response(wrapped)
    assert len(result) == 8


def test_parse_raises_on_invalid_json():
    import pytest
    with pytest.raises(FactoidParseError):
        parse_factoid_response("not json at all")


def test_parse_raises_on_missing_text_key():
    import pytest
    bad = json.dumps([{"category": "trivia"}])
    with pytest.raises(FactoidParseError):
        parse_factoid_response(bad)


def test_parse_raises_on_empty_list():
    import pytest
    with pytest.raises(FactoidParseError):
        parse_factoid_response("[]")


def test_generate_factoids_retries_on_bad_json():
    """Second call returns valid JSON after first returns garbage."""
    bad_response = MagicMock()
    bad_response.content = [MagicMock(type="text", text="oops not json")]
    good_response = MagicMock()
    good_response.content = [MagicMock(type="text", text=VALID_JSON)]

    with patch("factoids.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [bad_response, good_response]
        result = generate_factoids("Alanis Morissette", "Ironic")
        assert len(result) == 8
        assert instance.messages.create.call_count == 2


def test_generate_factoids_raises_after_two_failures():
    """Raises FactoidParseError when both attempts return bad JSON."""
    import pytest
    bad_response = MagicMock()
    bad_response.content = [MagicMock(type="text", text="not json")]

    with patch("factoids.anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = bad_response
        with pytest.raises(FactoidParseError):
            generate_factoids("Artist", "Song")
        assert instance.messages.create.call_count == 2
