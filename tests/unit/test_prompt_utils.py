"""Tests for prompt utility functions."""
import pytest
from unittest.mock import patch

from nicheiq.utils.prompts import safe_format


class TestSafeFormat:
    def test_no_braces_passes_through(self):
        result = safe_format("Hello {name}, you are {age}.", name="Alice", age=30)
        assert result == "Hello Alice, you are 30."

    def test_escapes_curly_braces_in_string_values(self):
        """Braces in values are escaped so they survive a potential second .format() pass."""
        result = safe_format(
            "Content: {text}",
            text='Here is some JSON: {"key": "value"}',
        )
        # Escaping produces doubled braces in output (safe for re-formatting)
        assert '{"key": "value"}' not in result or "{{" in result

    def test_leaves_non_string_values_untouched(self):
        result = safe_format(
            "Count: {count}, Score: {score}",
            count=42,
            score=3.14,
        )
        assert result == "Count: 42, Score: 3.14"

    def test_handles_empty_string_values(self):
        result = safe_format("Value: {val}", val="")
        assert result == "Value: "

    def test_does_not_crash_on_braces_in_values(self):
        """Primary goal: no KeyError/ValueError from user content with braces."""
        # This must not raise any exception
        result = safe_format(
            "Solution: {name}, Details: {details}",
            name="TestApp",
            details='function() { return {x: 1}; }',
        )
        assert "TestApp" in result
        assert "function()" in result

    def test_no_crash_on_format_like_patterns(self):
        """Values that look like format placeholders must not crash."""
        result = safe_format(
            "Data: {data}",
            data="{unknown_key} and {another}",
        )
        assert "Data:" in result


class TestGetPromptWithSafeFormat:
    def test_get_prompt_does_not_crash_on_braces(self, tmp_path):
        """get_prompt should not crash on braces in values."""
        from nicheiq.utils.prompts import get_prompt

        yaml_content = "template: 'Solution: {solution_name}'"
        prompt_file = tmp_path / "test_prompt.yaml"
        prompt_file.write_text(yaml_content)

        with patch("nicheiq.utils.prompts.PROMPTS_DIR", tmp_path):
            # Must not raise — that's the key assertion
            result = get_prompt(
                "test_prompt",
                solution_name='My {fancy} Solution',
            )
            assert "Solution:" in result
            assert "My" in result
            assert "Solution" in result
