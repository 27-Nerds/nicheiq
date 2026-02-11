"""
Tests for RawConcept model fields: why_non_obvious, distribution_channel, platform_leverage technique.
"""

import pytest

from nicheiq.models.solution_idea import RawConcept


class TestRawConceptNewFields:
    """Tests for new RawConcept fields."""

    def test_why_non_obvious_is_optional_defaults_none(self):
        """why_non_obvious defaults to None when not provided."""
        concept = RawConcept(
            concept_name="TestConcept",
            one_liner="A test concept description",
            ideation_technique="niche_drilling",
            project_type="aggregator",
            target_keywords=["keyword1", "keyword2"],
        )
        assert concept.why_non_obvious is None

    def test_why_non_obvious_accepts_string(self):
        """why_non_obvious accepts a string value."""
        wno = "This exploits data asymmetry in building permits across 3,100 counties."
        concept = RawConcept(
            concept_name="TestConcept",
            one_liner="A test concept",
            ideation_technique="niche_drilling",
            project_type="aggregator",
            target_keywords=["kw1", "kw2"],
            why_non_obvious=wno,
        )
        assert concept.why_non_obvious == wno

    def test_distribution_channel_defaults_to_seo(self):
        """distribution_channel defaults to 'seo' when not provided."""
        concept = RawConcept(
            concept_name="TestConcept",
            one_liner="A test concept",
            ideation_technique="niche_drilling",
            project_type="aggregator",
            target_keywords=["kw1", "kw2"],
        )
        assert concept.distribution_channel == "seo"

    def test_distribution_channel_accepts_hybrid(self):
        """distribution_channel accepts 'hybrid' value."""
        concept = RawConcept(
            concept_name="TestConcept",
            one_liner="A test concept",
            ideation_technique="platform_leverage",
            project_type="saas",
            target_keywords=["kw1", "kw2"],
            distribution_channel="hybrid",
        )
        assert concept.distribution_channel == "hybrid"

    def test_ideation_technique_accepts_platform_leverage(self):
        """ideation_technique accepts 'platform_leverage'."""
        concept = RawConcept(
            concept_name="ShopifyApp",
            one_liner="A Shopify app that does something useful",
            ideation_technique="platform_leverage",
            project_type="saas",
            target_keywords=["shopify tool", "shopify app"],
        )
        assert concept.ideation_technique == "platform_leverage"

    def test_backward_compat_old_format_without_new_fields(self):
        """Old-format JSON without why_non_obvious/distribution_channel parses OK."""
        old_data = {
            "concept_name": "OldConcept",
            "one_liner": "An old format concept",
            "ideation_technique": "niche_drilling",
            "project_type": "directory",
            "target_keywords": ["kw1", "kw2"],
            "data_source_hint": "Reddit discussions",
        }
        concept = RawConcept(**old_data)
        assert concept.concept_name == "OldConcept"
        assert concept.why_non_obvious is None
        assert concept.distribution_channel == "seo"

    def test_extra_fields_ignored(self):
        """Extra fields are ignored (model_config extra='ignore')."""
        data = {
            "concept_name": "TestConcept",
            "one_liner": "A test concept",
            "ideation_technique": "niche_drilling",
            "project_type": "aggregator",
            "target_keywords": ["kw1", "kw2"],
            "unknown_field": "should be ignored",
        }
        concept = RawConcept(**data)
        assert concept.concept_name == "TestConcept"
        assert not hasattr(concept, "unknown_field")
