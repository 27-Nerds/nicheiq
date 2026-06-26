"""
Tests for crew guardrails - content categorization and solution selection validation.

Tests:
- validate_content_categorization: checks anchor_keywords on themes
- validate_solution_selection: checks JSON parsing and field validation
"""

import json
from unittest.mock import MagicMock

from nicheiq.models.seo_strategy import CategoryLightResult
from nicheiq.utils.validation.crew_guardrails import (
    _normalize_technique,
    validate_category_tier_output,
    validate_content_categorization,
    validate_raw_concepts,
    validate_solution_selection,
)


class TestValidateContentCategorization:
    """Tests for validate_content_categorization guardrail."""

    def test_validate_content_categorization_checks_anchor_keywords(self):
        """Fails if theme has < 3 anchor_keywords."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "executive_summary": "Test summary",
            "theme_categories": [
                {
                    "category_name": "Theme 1",
                    "definition": "Definition",
                    "frequency": "High",
                    "mention_count": 10,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2"],  # Only 2, needs 3
                },
                {
                    "category_name": "Theme 2",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 8,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                {
                    "category_name": "Theme 3",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 6,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                {
                    "category_name": "Theme 4",
                    "definition": "Definition",
                    "frequency": "Low",
                    "mention_count": 5,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
            ],
            "user_segments": [
                {"segment_name": "Users", "primary_concerns": ["concern"], "mention_frequency": "High"},
                {"segment_name": "Admins", "primary_concerns": ["admin"], "mention_frequency": "Medium"},
                {"segment_name": "Devs", "primary_concerns": ["dev"], "mention_frequency": "Low"},
            ],
            "overall_quality": "High",
        })

        success, result = validate_content_categorization(output)

        assert not success
        assert "anchor_keywords" in result.lower()

    def test_validate_content_categorization_passes_valid(
        self, mock_task_output_valid_categorization
    ):
        """Passes with valid themes (3+ anchor_keywords each)."""
        success, result = validate_content_categorization(mock_task_output_valid_categorization)

        assert success
        # On success, returns raw for CrewAI to re-parse
        assert result == mock_task_output_valid_categorization.raw

    def test_validate_content_categorization_fails_few_themes(self):
        """Fails if < 4 theme_categories."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "executive_summary": "Test summary",
            "theme_categories": [
                {
                    "category_name": "Theme 1",
                    "definition": "Definition",
                    "frequency": "High",
                    "mention_count": 10,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                {
                    "category_name": "Theme 2",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 8,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                # Only 2 themes, need 4
            ],
            "user_segments": [
                {"segment_name": "Users", "primary_concerns": ["concern"], "mention_frequency": "High"},
                {"segment_name": "Admins", "primary_concerns": ["admin"], "mention_frequency": "Medium"},
                {"segment_name": "Devs", "primary_concerns": ["dev"], "mention_frequency": "Low"},
            ],
            "overall_quality": "High",
        })

        success, result = validate_content_categorization(output)

        assert not success
        assert "at least 4" in result.lower()

    def test_validate_content_categorization_fails_few_segments(self):
        """Fails if < 3 user_segments."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "executive_summary": "Test summary",
            "theme_categories": [
                {
                    "category_name": f"Theme {i}",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 10,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                }
                for i in range(4)
            ],
            "user_segments": [
                {"segment_name": "Users", "primary_concerns": ["concern"], "mention_frequency": "High"},
                # Only 1 segment, need 3
            ],
            "overall_quality": "High",
        })

        success, result = validate_content_categorization(output)

        assert not success
        assert "at least 3" in result.lower() or "user_segments" in result.lower()


class TestSeoKeywordGuardrails:
    """Tests for SEO keyword analysis guardrail return compatibility."""

    def test_category_tier_guardrail_serializes_model_raw(self):
        """CrewAI TaskOutput.raw requires a string even when raw contains a model."""
        category_result = CategoryLightResult(
            tier_4_category_groups=[
                {
                    "category_name": "Automation",
                    "keywords": [{"keyword_name": "workflow automation tool"}],
                    "strategy_recommendation": "Target workflow automation comparisons.",
                }
            ],
            category_strategy_notes="Build programmatic pages around automation use cases.",
        )
        output = MagicMock()
        output.pydantic = category_result
        output.raw = category_result

        success, result = validate_category_tier_output(output)

        assert success
        assert isinstance(result, str)
        reparsed = CategoryLightResult.model_validate_json(result)
        assert reparsed.tier_4_category_groups is not None
        assert reparsed.tier_4_category_groups[0].category_name == "Automation"








class TestValidateContentCategorizationEdgeCases:
    """Edge case tests for validate_content_categorization."""

    def test_empty_raw_returns_error(self):
        """No pydantic and empty raw -> error."""
        output = MagicMock()
        output.pydantic = None
        output.raw = ""

        success, result = validate_content_categorization(output)

        assert not success

    def test_pydantic_available_uses_it(self):
        """When pydantic is available, uses it directly."""
        from nicheiq.models.pain_point import (
            ContentCategorizationReport,
            ThemeCategory,
            UserSegment,
        )

        report = ContentCategorizationReport(
            executive_summary="Test",
            theme_categories=[
                ThemeCategory(
                    category_name=f"Theme {i}",
                    definition="Def",
                    frequency="High",
                    mention_count=10,
                    primary_user_segments=["Users"],
                    anchor_keywords=["kw1", "kw2", "kw3"],
                )
                for i in range(4)
            ],
            user_segments=[
                UserSegment(segment_name=f"Seg {i}", primary_concerns=["c"], mention_frequency="High")
                for i in range(3)
            ],
            overall_quality="High",
        )

        output = MagicMock()
        output.pydantic = report
        output.raw = "unused"

        success, result = validate_content_categorization(output)

        # Should pass using pydantic directly
        assert success


def _make_valid_selection_raw(**overrides) -> str:
    """Helper to build valid SolutionSelection JSON with optional overrides."""
    data = {
        "selected_solution_name": "NicheTracker Pro",
        "selection_rationale": (
            "NicheTracker Pro was selected because it addresses the strongest validated pain point "
            "in the market with a clear competitive gap. The solution scores highest on market fit "
            "(0.85) and competitive advantage (0.78), while maintaining strong technical feasibility."
        ),
        "recommended_focus": "Enterprise segment first, then SMB expansion",
        "runner_up_solutions": ["CompetitorRadar", "MarketPulse"],
    }
    data.update(overrides)
    return json.dumps(data)


class TestValidateSolutionSelection:
    """Tests for validate_solution_selection guardrail."""

    def test_valid_selection(self):
        """Valid SolutionSelection JSON -> (True, raw)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw()

        success, result = validate_solution_selection(output)

        assert success
        assert result == output.raw

    def test_invalid_json(self):
        """Malformed JSON (the actual production crash scenario) -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        # Unescaped quote inside selection_rationale - the real crash scenario
        output.raw = '{"selected_solution_name": "Test", "selection_rationale": "It\'s the "best" solution because reasons", "recommended_focus": "focus"}'

        success, result = validate_solution_selection(output)

        assert not success
        assert "json" in result.lower() or "parse" in result.lower()

    def test_short_rationale(self):
        """selection_rationale < 100 chars -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw(
            selection_rationale="Too short rationale."
        )

        success, result = validate_solution_selection(output)

        assert not success
        assert "selection_rationale" in result.lower()

    def test_short_name(self):
        """selected_solution_name < 3 chars -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw(
            selected_solution_name="AB"
        )

        success, result = validate_solution_selection(output)

        assert not success
        assert "selected_solution_name" in result.lower()

    def test_empty_focus(self):
        """Empty recommended_focus -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw(
            recommended_focus=""
        )

        success, result = validate_solution_selection(output)

        assert not success
        assert "recommended_focus" in result.lower()


def _make_raw_concept(
    name="TestConcept",
    technique="niche_drilling",
    why_non_obvious=None,
    distribution_channel="seo",
    **overrides,
) -> dict:
    """Helper to build a valid raw concept dict."""
    concept = {
        "concept_name": name,
        "one_liner": f"A detailed description of {name} that explains the unique angle and approach.",
        "ideation_technique": technique,
        "project_type": "aggregator",
        "target_keywords": [f"{name.lower()} keyword 1", f"{name.lower()} keyword 2"],
        "data_source_hint": "Public data sources",
        "why_non_obvious": (
            why_non_obvious if why_non_obvious is not None else
            f"This approach exploits an information asymmetry in {name.lower()} data "
            "that competitors miss because they focus on surface-level metrics."
        ),
        "distribution_channel": distribution_channel,
    }
    concept.update(overrides)
    return concept


def _make_raw_concept_list_json(concepts=None, techniques_used=None):
    """Helper to build a valid RawConceptList JSON string."""
    if concepts is None:
        # Default: 6 concepts using 3+ different techniques
        concepts = [
            _make_raw_concept("ConceptAlpha", "niche_drilling"),
            _make_raw_concept("ConceptBeta", "niche_drilling"),
            _make_raw_concept("ConceptGamma", "data_source_inversion"),
            _make_raw_concept("ConceptDelta", "cross_industry_template"),
            _make_raw_concept("ConceptEpsilon", "atomic_feature"),
            _make_raw_concept("ConceptZeta", "community_flip"),
        ]
    if techniques_used is None:
        techniques_used = list({c["ideation_technique"] for c in concepts})
    return json.dumps({
        "concepts": concepts,
        "techniques_used": techniques_used,
        "pain_points_referenced": ["Pain Point 1", "Pain Point 2"],
    })


class TestValidateRawConcepts:
    """Tests for validate_raw_concepts guardrail."""

    def test_valid_diverse_concepts_pass(self):
        """Valid concepts with 3+ techniques and good why_non_obvious pass."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json()

        success, result = validate_raw_concepts(output)

        assert success
        assert result == output.raw

    def test_fails_with_fewer_than_3_techniques(self):
        """Fails when fewer than 3 different techniques are used."""
        concepts = [
            _make_raw_concept(f"ConceptNum{i}", "niche_drilling")
            for i in range(6)
        ]
        # All use same technique
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert not success
        assert "technique diversity" in result.lower()

    def test_no_platform_leverage_passes_with_warning(self):
        """No platform_leverage → passes (soft check, not hard failure)."""
        concepts = [
            _make_raw_concept("ConceptAlpha", "niche_drilling"),
            _make_raw_concept("ConceptBeta", "niche_drilling"),
            _make_raw_concept("ConceptGamma", "data_source_inversion"),
            _make_raw_concept("ConceptDelta", "cross_industry_template"),
            _make_raw_concept("ConceptEpsilon", "atomic_feature"),
            _make_raw_concept("ConceptZeta", "community_flip"),
        ]
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert success  # Soft check, not a failure

    def test_fails_with_missing_why_non_obvious(self):
        """Fails when why_non_obvious is missing (< 50 chars)."""
        concepts = [
            _make_raw_concept("ConceptAlpha", "niche_drilling", why_non_obvious=""),
            _make_raw_concept("ConceptBeta", "data_source_inversion"),
            _make_raw_concept("ConceptGamma", "cross_industry_template"),
            _make_raw_concept("ConceptDelta", "atomic_feature"),
            _make_raw_concept("ConceptEpsilon", "community_flip"),
            _make_raw_concept("ConceptZeta", "niche_drilling"),
        ]
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert not success
        assert "why_non_obvious" in result.lower()

    def test_fails_with_short_why_non_obvious(self):
        """Fails when why_non_obvious is too short (< 50 chars)."""
        concepts = [
            _make_raw_concept("ConceptAlpha", "niche_drilling", why_non_obvious="Short reason here."),
            _make_raw_concept("ConceptBeta", "data_source_inversion"),
            _make_raw_concept("ConceptGamma", "cross_industry_template"),
            _make_raw_concept("ConceptDelta", "atomic_feature"),
            _make_raw_concept("ConceptEpsilon", "community_flip"),
            _make_raw_concept("ConceptZeta", "niche_drilling"),
        ]
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert not success
        assert "50+ chars" in result

    def test_fails_with_generic_banned_phrase_in_short_text(self):
        """Fails when short why_non_obvious (< 80 chars) contains banned phrase."""
        concepts = [
            _make_raw_concept(
                "ConceptAlpha", "niche_drilling",
                why_non_obvious="This is a unique approach to solving problems in this space."
            ),
            _make_raw_concept("ConceptBeta", "data_source_inversion"),
            _make_raw_concept("ConceptGamma", "cross_industry_template"),
            _make_raw_concept("ConceptDelta", "atomic_feature"),
            _make_raw_concept("ConceptEpsilon", "community_flip"),
            _make_raw_concept("ConceptZeta", "niche_drilling"),
        ]
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert not success
        assert "unique approach" in result.lower()

    def test_long_why_non_obvious_with_banned_phrase_passes(self):
        """Long why_non_obvious (>= 80 chars) with banned phrase in context passes."""
        long_wno = (
            "While competitors take a unique approach of aggregating listings, this tool instead "
            "exploits the information asymmetry in municipal building permit data scattered across "
            "3,100 county sites, creating signals competitors fundamentally cannot replicate."
        )
        assert len(long_wno) >= 80  # Verify our test data
        concepts = [
            _make_raw_concept("ConceptAlpha", "niche_drilling", why_non_obvious=long_wno),
            _make_raw_concept("ConceptBeta", "data_source_inversion"),
            _make_raw_concept("ConceptGamma", "cross_industry_template"),
            _make_raw_concept("ConceptDelta", "atomic_feature"),
            _make_raw_concept("ConceptEpsilon", "community_flip"),
            _make_raw_concept("ConceptZeta", "niche_drilling"),
        ]
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert success

    def test_technique_name_normalization(self):
        """Technique names with spaces/hyphens normalize to underscores."""
        assert _normalize_technique("platform leverage") == "platform_leverage"
        assert _normalize_technique("platform-leverage") == "platform_leverage"
        assert _normalize_technique("Platform_Leverage") == "platform_leverage"
        assert _normalize_technique("  niche_drilling  ") == "niche_drilling"
        assert _normalize_technique("CROSS-INDUSTRY TEMPLATE") == "cross_industry_template"
        assert _normalize_technique("ai native") == "ai_native"
        assert _normalize_technique("AI-Native") == "ai_native"

    def test_platform_leverage_technique_accepted(self):
        """Platform leverage counts as a valid technique for diversity."""
        concepts = [
            _make_raw_concept("ConceptAlpha", "niche_drilling"),
            _make_raw_concept("ConceptBeta", "platform_leverage"),
            _make_raw_concept("ConceptGamma", "data_source_inversion"),
            _make_raw_concept("ConceptDelta", "platform_leverage"),
            _make_raw_concept("ConceptEpsilon", "community_flip"),
            _make_raw_concept("ConceptZeta", "niche_drilling"),
        ]
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert success

    def test_ai_native_technique_accepted(self):
        """ai_native counts as a distinct valid technique (LLM-as-component lane)."""
        concepts = [
            _make_raw_concept("ConceptAlpha", "niche_drilling"),
            _make_raw_concept("ConceptBeta", "data_source_inversion"),
            _make_raw_concept("ConceptGamma", "ai_native",
                              mechanism_tag="llm-extraction-pipeline"),
            _make_raw_concept("ConceptDelta", "ai_native",
                              mechanism_tag="ai-classification"),
            _make_raw_concept("ConceptEpsilon", "community_flip"),
            _make_raw_concept("ConceptZeta", "niche_drilling"),
        ]
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_raw_concept_list_json(concepts=concepts)

        success, result = validate_raw_concepts(output)

        assert success
        assert result == output.raw
