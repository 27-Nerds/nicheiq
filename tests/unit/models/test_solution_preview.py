"""Unit tests for SolutionPreview models."""

import pytest

from nicheiq.models.solution_preview import (
    SolutionValidationData,
    SolutionPreview,
    SolutionPreviewList,
)


def _make_validation_data(**overrides) -> SolutionValidationData:
    """Create SolutionValidationData with defaults."""
    defaults = dict(
        keyword_demand_score=75.0,
        demand_signal="Strong",
        total_volume=5000,
        validated_count=10,
        avg_keyword_difficulty=35.0,
        rankability_factor=0.8,
    )
    defaults.update(overrides)
    return SolutionValidationData(**defaults)


def _make_preview(**overrides) -> SolutionPreview:
    """Create SolutionPreview with defaults."""
    defaults = dict(
        name="TestSolution",
        description="A test solution",
        value_proposition="Solves everything",
    )
    defaults.update(overrides)
    return SolutionPreview(**defaults)


class TestSolutionValidationData:
    def test_constructs_with_all_fields(self):
        data = _make_validation_data()
        assert data.keyword_demand_score == 75.0
        assert data.demand_signal == "Strong"
        assert data.total_volume == 5000

    def test_handles_optional_fields(self):
        data = SolutionValidationData()
        assert data.keyword_demand_score is None
        assert data.top_keywords is None

    def test_extra_fields_allowed(self):
        data = SolutionValidationData(custom_field="extra")
        assert data.custom_field == "extra"  # extra="allow"

    def test_serializes_to_dict_and_back(self):
        data = _make_validation_data()
        d = data.model_dump()
        restored = SolutionValidationData(**d)
        assert restored.keyword_demand_score == data.keyword_demand_score


class TestSolutionPreview:
    def test_constructs_with_minimal_fields(self):
        # Uses "name" alias for solution_name
        preview = _make_preview()
        assert preview.solution_name == "TestSolution"
        assert preview.description == "A test solution"

    def test_constructs_with_full_validation_data(self):
        val = _make_validation_data()
        preview = _make_preview(validated=True, validation=val)
        assert preview.validated is True
        assert preview.validation.keyword_demand_score == 75.0

    def test_validated_defaults_to_false(self):
        preview = _make_preview()
        assert preview.validated is False
        assert preview.validation is None

    def test_name_alias_maps_to_solution_name(self):
        # "name" is an alias for "solution_name"
        preview = SolutionPreview(
            name="MyApp",
            description="desc",
            value_proposition="vp",
        )
        assert preview.solution_name == "MyApp"

    def test_serializes_to_dict(self):
        preview = _make_preview()
        d = preview.model_dump(by_alias=True)
        assert "name" in d or "solution_name" in d

    def test_extra_fields_allowed(self):
        preview = _make_preview(custom_extra="data")
        assert preview.custom_extra == "data"

    def test_delivery_format_is_optional_and_serialized(self):
        legacy = _make_preview()
        current = _make_preview(delivery_format="browser-extension")

        assert legacy.delivery_format is None
        assert current.model_dump()["delivery_format"] == "browser-extension"


class TestSolutionPreviewList:
    def test_constructs_with_list(self):
        previews = [_make_preview(name="Sol1"), _make_preview(name="Sol2")]
        lst = SolutionPreviewList(solutions=previews)
        assert len(lst.solutions) == 2

    def test_generation_round_defaults_to_1(self):
        lst = SolutionPreviewList()
        assert lst.generation_round == 1

    def test_can_regenerate_defaults_to_true(self):
        lst = SolutionPreviewList()
        assert lst.can_regenerate is True
