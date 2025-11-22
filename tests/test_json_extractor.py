"""
Tests for JSON extraction utilities.
"""

import pytest
from nicheiq.utils.parsing.json_extractor import extract_json_array_from_text


class TestExtractJsonArrayFromText:
    """Tests for extract_json_array_from_text function."""

    def test_fast_path_clean_json_array(self):
        """Test fast path: direct JSON parse when text starts with [."""
        text = '[{"name": "test", "value": 123}, {"name": "test2", "value": 456}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "test"
        assert result[0]["value"] == 123

    def test_fast_path_with_whitespace(self):
        """Test fast path handles leading/trailing whitespace."""
        text = '  \n  [{"key": "value"}]  \n  '
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["key"] == "value"

    def test_medium_path_with_prefix_text(self):
        """Test medium path: regex extraction when JSON has prefix."""
        text = 'Here is the list of results: [{"item": "A"}, {"item": "B"}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 2
        assert result[0]["item"] == "A"
        assert result[1]["item"] == "B"

    def test_medium_path_with_suffix_text(self):
        """Test medium path: regex extraction with suffix text."""
        text = '[{"data": "value"}] and that is the end'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["data"] == "value"

    def test_slow_path_nested_brackets_in_strings(self):
        """Test slow path: manual bracket matching with brackets in strings."""
        text = '[{"text": "contains [nested] brackets", "value": 1}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["text"] == "contains [nested] brackets"
        assert result[0]["value"] == 1

    def test_slow_path_escaped_quotes_in_strings(self):
        """Test slow path: handle escaped quotes correctly."""
        text = r'[{"text": "quote with \"escaped\" characters", "id": 42}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert 'escaped' in result[0]["text"]
        assert result[0]["id"] == 42

    def test_empty_array(self):
        """Test extraction of empty array."""
        text = "[]"
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 0

    def test_multiple_arrays_returns_first(self):
        """Test that multiple arrays returns only the first one."""
        text = '[{"first": 1}] some text [{"second": 2}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["first"] == 1
        assert "second" not in result[0]

    def test_malformed_json_returns_none(self):
        """Test that malformed JSON returns None."""
        text = '[{"incomplete": true'  # Missing closing brackets
        result = extract_json_array_from_text(text)

        assert result is None

    def test_no_array_in_text_returns_none(self):
        """Test that text without array returns None."""
        text = "This is just plain text without any JSON arrays"
        result = extract_json_array_from_text(text)

        assert result is None

    def test_nested_arrays(self):
        """Test extraction of array containing nested arrays."""
        text = '[{"items": ["a", "b", "c"]}, {"items": ["d", "e"]}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 2
        assert result[0]["items"] == ["a", "b", "c"]
        assert result[1]["items"] == ["d", "e"]

    def test_nested_objects(self):
        """Test extraction of array with nested objects."""
        text = '[{"outer": {"inner": {"value": 123}}}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["outer"]["inner"]["value"] == 123

    def test_unicode_characters(self):
        """Test extraction with Unicode characters."""
        text = '[{"name": "Café", "emoji": "🚀", "chinese": "你好"}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Café"
        assert result[0]["emoji"] == "🚀"
        assert result[0]["chinese"] == "你好"

    def test_json_with_newlines_and_indentation(self):
        """Test extraction of formatted JSON with newlines."""
        text = """[
            {
                "name": "test",
                "value": 123
            },
            {
                "name": "test2",
                "value": 456
            }
        ]"""
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "test"

    def test_json_with_boolean_and_null_values(self):
        """Test extraction with boolean and null values."""
        text = '[{"active": true, "deleted": false, "data": null}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["active"] is True
        assert result[0]["deleted"] is False
        assert result[0]["data"] is None

    def test_json_with_numbers(self):
        """Test extraction with various number formats."""
        text = '[{"int": 42, "float": 3.14, "negative": -10, "scientific": 1.5e10}]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 1
        assert result[0]["int"] == 42
        assert result[0]["float"] == 3.14
        assert result[0]["negative"] == -10
        assert result[0]["scientific"] == 1.5e10

    def test_complex_llm_response(self):
        """Test realistic LLM response with explanatory text."""
        text = """I'll help you with that. Here's the JSON array you requested:

        [
            {
                "query": "AI tools content creators",
                "type": "problem_discovery",
                "platform": "reddit"
            },
            {
                "query": "content creation automation frustrated",
                "type": "pain_point",
                "platform": "twitter"
            }
        ]

        These queries should help you find relevant discussions."""

        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 2
        assert result[0]["query"] == "AI tools content creators"
        assert result[1]["platform"] == "twitter"

    def test_json_object_not_array_returns_none(self):
        """Test that JSON object (not array) returns None."""
        text = '{"key": "value", "number": 123}'
        result = extract_json_array_from_text(text)

        assert result is None

    def test_array_of_primitives(self):
        """Test extraction of array containing primitive values."""
        text = '["string1", "string2", "string3"]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 3
        assert result == ["string1", "string2", "string3"]

    def test_mixed_primitive_array(self):
        """Test extraction of array with mixed primitive types."""
        text = '[1, "two", 3.0, true, null]'
        result = extract_json_array_from_text(text)

        assert result is not None
        assert len(result) == 5
        assert result[0] == 1
        assert result[1] == "two"
        assert result[2] == 3.0
        assert result[3] is True
        assert result[4] is None
