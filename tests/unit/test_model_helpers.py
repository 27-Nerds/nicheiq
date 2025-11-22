"""
Tests for model compatibility helpers.
"""

import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel
from nicheiq.report.utils.model_helpers import safe_get_attr


class SampleModel(BaseModel):
    """Sample Pydantic model for testing."""
    name: str
    value: int
    active: bool = True


class TestSafeGetAttr:
    """Tests for safe_get_attr function."""

    def test_get_from_pydantic_model(self):
        """Test getting attribute from Pydantic model."""
        model = SampleModel(name="test", value=42)

        assert safe_get_attr(model, 'name') == "test"
        assert safe_get_attr(model, 'value') == 42
        assert safe_get_attr(model, 'active') is True

    def test_get_from_dict(self):
        """Test getting attribute from dict (checkpoint compatibility)."""
        data = {"name": "test", "value": 42, "active": False}

        assert safe_get_attr(data, 'name') == "test"
        assert safe_get_attr(data, 'value') == 42
        assert safe_get_attr(data, 'active') is False

    def test_missing_attribute_returns_default(self):
        """Test that missing attribute returns default value."""
        model = SampleModel(name="test", value=42)

        # Missing attribute with default
        assert safe_get_attr(model, 'missing', 'default_value') == 'default_value'
        assert safe_get_attr(model, 'nonexistent', None) is None

    def test_missing_key_in_dict_returns_default(self):
        """Test that missing key in dict returns default value."""
        data = {"name": "test"}

        assert safe_get_attr(data, 'missing', 'default') == 'default'
        assert safe_get_attr(data, 'value', 0) == 0

    def test_default_is_none_when_not_specified(self):
        """Test that default is None when not specified."""
        data = {}

        assert safe_get_attr(data, 'missing') is None

    def test_empty_dict_returns_default(self):
        """Test getting from empty dict returns default."""
        data = {}

        assert safe_get_attr(data, 'anything', 'fallback') == 'fallback'

    def test_type_preservation_string(self):
        """Test that string types are preserved."""
        data = {"text": "hello world"}

        result = safe_get_attr(data, 'text')
        assert isinstance(result, str)
        assert result == "hello world"

    def test_type_preservation_int(self):
        """Test that integer types are preserved."""
        data = {"count": 123}

        result = safe_get_attr(data, 'count')
        assert isinstance(result, int)
        assert result == 123

    def test_type_preservation_bool(self):
        """Test that boolean types are preserved."""
        data = {"active": True, "deleted": False}

        assert safe_get_attr(data, 'active') is True
        assert safe_get_attr(data, 'deleted') is False

    def test_type_preservation_list(self):
        """Test that list types are preserved."""
        data = {"items": [1, 2, 3, 4, 5]}

        result = safe_get_attr(data, 'items')
        assert isinstance(result, list)
        assert result == [1, 2, 3, 4, 5]

    def test_type_preservation_dict(self):
        """Test that nested dict types are preserved."""
        data = {"nested": {"key": "value"}}

        result = safe_get_attr(data, 'nested')
        assert isinstance(result, dict)
        assert result == {"key": "value"}

    def test_none_value_vs_missing_key(self):
        """Test distinction between None value and missing key."""
        data = {"explicit_none": None}

        # Key exists with None value
        assert safe_get_attr(data, 'explicit_none') is None
        assert safe_get_attr(data, 'explicit_none', 'default') is None

        # Key doesn't exist
        assert safe_get_attr(data, 'missing_key', 'default') == 'default'

    def test_works_with_mock_object(self):
        """Test that function works with MagicMock objects."""
        mock = MagicMock()
        mock.attribute = "mocked_value"

        result = safe_get_attr(mock, 'attribute')
        assert result == "mocked_value"

    def test_complex_nested_access(self):
        """Test accessing nested attributes (requires chaining calls)."""
        data = {
            "level1": {
                "level2": {
                    "value": "nested"
                }
            }
        }

        # Get level1, then level2, then value
        level1 = safe_get_attr(data, 'level1')
        level2 = safe_get_attr(level1, 'level2')
        value = safe_get_attr(level2, 'value')

        assert value == "nested"

    def test_with_pydantic_optional_fields(self):
        """Test with Pydantic model having optional fields."""
        from typing import Optional

        class OptionalModel(BaseModel):
            required: str
            optional: Optional[str] = None

        # Model with optional field not provided
        model1 = OptionalModel(required="test")
        assert safe_get_attr(model1, 'required') == "test"
        assert safe_get_attr(model1, 'optional') is None

        # Model with optional field provided
        model2 = OptionalModel(required="test", optional="value")
        assert safe_get_attr(model2, 'optional') == "value"
