"""
Tests for the evidence-grounded pain-point scoring pipeline (Phase 1 fixes).

Covers:
- compute_opportunity_level: the deterministic severity/WTP formula
- PainPointCrew.resolve_pain_point_scores: mention_count from vector-search
  evidence, zero-quote severity clamp, downgrade-only opportunity_level
- PainPointCrew._validate_theme_linkage: fuzzy remap, orphan clearing, coverage
- PainPointCrew._format_pain_points_with_evidence: quote/word caps, zero-quote text
- PainPointCrew.usage_metrics: summing across phase crews
"""

from unittest.mock import MagicMock

from nicheiq.crews.pain_point_crew import PainPointCrew
from nicheiq.models.keyword_data import OpportunityLevel
from nicheiq.models.pain_point import (
    ContentCategorizationReport,
    EnrichedPainPointQuotes,
    ExtractedQuote,
    PainPointExtraction,
    PainPointScoring,
    QuoteEnrichmentResult,
    ThemeCategory,
    UnvalidatedPainPoint,
    compute_opportunity_level,
)


def _make_unvalidated(title="Manual Invoicing", parent_theme_id=None, mention_count=20):
    return UnvalidatedPainPoint(
        title=title,
        parent_theme_id=parent_theme_id,
        description="Manual invoicing is painful and slow",
        mention_count=mention_count,
        anchor_keywords=["manual invoices", "invoice pain"],
    )


def _make_scoring(
    title="Manual Invoicing",
    severity=0.8,
    wtp=0.7,
    level=OpportunityLevel.HIGH,
    downgrade_reason=None,
):
    return PainPointScoring(
        pain_point_title=title,
        severity_score=severity,
        commercial_intent=wtp,
        opportunity_level=level,
        downgrade_reason=downgrade_reason,
    )


def _make_enrichment(title="Manual Invoicing", quotes=None, matched_post_ids=None):
    return EnrichedPainPointQuotes(
        pain_point_title=title,
        quotes=quotes or [],
        matched_post_ids=matched_post_ids or [],
    )


def _make_theme(name="Invoicing Problems", frequency="High", mention_count=25):
    return ThemeCategory(
        category_name=name,
        definition="Problems around invoicing workflows",
        frequency=frequency,
        mention_count=mention_count,
        primary_user_segments=["Freelancers"],
        anchor_keywords=["manual invoices", "invoice pain", "billing errors"],
    )


class TestComputeOpportunityLevel:
    """The deterministic formula: High = both ≥0.6; Medium = exactly one; Low = none."""

    def test_both_high(self):
        assert compute_opportunity_level(0.6, 0.6) == OpportunityLevel.HIGH

    def test_severity_only(self):
        assert compute_opportunity_level(0.9, 0.59) == OpportunityLevel.MEDIUM

    def test_wtp_only(self):
        assert compute_opportunity_level(0.3, 0.7) == OpportunityLevel.MEDIUM

    def test_both_low(self):
        assert compute_opportunity_level(0.59, 0.59) == OpportunityLevel.LOW


class TestResolvePainPointScores:
    """Code-governed merge fields: mention_count, severity clamp, opportunity downgrades."""

    def test_mention_count_from_matched_post_ids(self):
        enrichment = _make_enrichment(matched_post_ids=["p1", "p2", "p3", "p4", "p5"])
        mention_count, _, _, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(mention_count=42),
            matching_score=_make_scoring(),
            quotes=["a real quote"],
            matching_enrichment=enrichment,
            theme_mentions={},
        )
        assert mention_count == 5  # evidence count, not the LLM's 42

    def test_mention_count_llm_fallback_without_enrichment(self):
        mention_count, _, _, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(mention_count=42),
            matching_score=_make_scoring(),
            quotes=[],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert mention_count == 42

    def test_mention_count_clamped_to_parent_theme(self):
        mention_count, _, _, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(parent_theme_id="invoicing-problems", mention_count=99),
            matching_score=_make_scoring(),
            quotes=[],
            matching_enrichment=None,
            theme_mentions={"invoicing-problems": 25},
        )
        assert mention_count == 25

    def test_zero_quote_severity_clamped(self):
        _, severity, level, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(severity=0.9, wtp=0.7, level=OpportunityLevel.HIGH),
            quotes=[],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert severity == 0.45
        # Clamped severity (<0.6) + high WTP → formula says MEDIUM, not HIGH
        assert level == OpportunityLevel.MEDIUM

    def test_severity_not_clamped_with_quotes(self):
        _, severity, _, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(severity=0.9),
            quotes=["q1 invoicing delays", "q2 lost a client", "q3 hours wasted"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert severity == 0.9

    def test_formula_overrides_llm_when_levels_match_formula(self):
        _, _, level, reason, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(severity=0.8, wtp=0.7, level=OpportunityLevel.HIGH),
            quotes=["q1", "q2", "q3"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert level == OpportunityLevel.HIGH
        assert reason is None

    def test_justified_downgrade_honored(self):
        _, _, level, reason, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(
                severity=0.8,
                wtp=0.7,
                level=OpportunityLevel.LOW,
                downgrade_reason="Universal emotional theme — would appear identically in every niche",
            ),
            quotes=["q1", "q2", "q3"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert level == OpportunityLevel.LOW
        assert reason is not None and "Universal" in reason

    def test_unjustified_downgrade_rejected(self):
        _, _, level, reason, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(
                severity=0.8, wtp=0.7, level=OpportunityLevel.LOW, downgrade_reason=None
            ),
            quotes=["q1", "q2", "q3"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert level == OpportunityLevel.HIGH  # formula wins
        assert reason is None

    def test_short_downgrade_reason_rejected(self):
        _, _, level, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(
                severity=0.8, wtp=0.7, level=OpportunityLevel.MEDIUM, downgrade_reason="cap"
            ),
            quotes=["q1", "q2", "q3"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert level == OpportunityLevel.HIGH

    def test_upgrade_rejected(self):
        _, _, level, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(severity=0.4, wtp=0.4, level=OpportunityLevel.HIGH),
            quotes=["q1", "q2", "q3"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert level == OpportunityLevel.LOW  # formula wins; upgrade ignored


class TestLowEvidenceAndStanceCounting:
    """New behavior: low-evidence severity clamp and stance-verified mention_count."""

    def test_low_evidence_clamps_severity(self):
        # Only 1 stance-verified quote (< _MIN_QUOTES=2) → severity clamped.
        _, severity, level, _, low_evidence, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(severity=0.9, wtp=0.7, level=OpportunityLevel.HIGH),
            quotes=["q1"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert low_evidence is True
        assert severity == 0.45
        assert level == OpportunityLevel.MEDIUM  # clamped severity drops it from HIGH

    def test_sufficient_evidence_not_low(self):
        # 2 independent supporting quotes is adequate — not low-evidence, no clamp.
        _, severity, _, _, low_evidence, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=_make_scoring(severity=0.9),
            quotes=["q1", "q2"],
            matching_enrichment=None,
            theme_mentions={},
        )
        assert low_evidence is False
        assert severity == 0.9

    def test_mention_count_counts_all_relevant_posts_not_just_displayed(self):
        # mention_count is a discussion-VOLUME signal: it counts every
        # relevance-passing post (matched_post_ids), independent of how few quotes
        # the stance gate kept for display. Count broad, show narrow.
        enrichment = _make_enrichment(
            quotes=[ExtractedQuote(quote_text="only one shown quote here", post_id="p1")],
            matched_post_ids=["p1", "p2", "p3", "p4", "p5"],
        )
        mention_count, _, _, _, _, _ = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(mention_count=42),
            matching_score=_make_scoring(),
            quotes=["q1", "q2", "q3"],
            matching_enrichment=enrichment,
            theme_mentions={},
        )
        # All 5 discussing posts, not the 1 displayed quote and not the LLM's 42.
        assert mention_count == 5


class TestValidateThemeLinkage:
    """Fuzzy remap, orphan clearing, and High/Medium coverage computation."""

    def _categorization(self, themes):
        return ContentCategorizationReport(
            executive_summary="summary",
            theme_categories=themes,
            user_segments=[
                {"segment_name": "A", "primary_concerns": ["x"], "mention_frequency": "High"},
                {"segment_name": "B", "primary_concerns": ["y"], "mention_frequency": "Low"},
                {"segment_name": "C", "primary_concerns": ["z"], "mention_frequency": "Low"},
            ],
            overall_quality="High",
        )

    def test_exact_linkage_no_findings(self):
        themes = [
            _make_theme("Invoicing Problems", "High"),
            _make_theme("Expense Tracking", "Medium"),
            _make_theme("Tax Prep", "Low"),
            _make_theme("Cash Flow", "Low"),
        ]
        extraction = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                _make_unvalidated("PP one", parent_theme_id="invoicing-problems"),
                _make_unvalidated("PP two", parent_theme_id="expense-tracking"),
                _make_unvalidated("PP three", parent_theme_id="invoicing-problems"),
            ],
            extraction_summary="ok",
        )
        orphans, uncovered = PainPointCrew._validate_theme_linkage(
            extraction, self._categorization(themes)
        )
        assert orphans == []
        assert uncovered == []  # Low themes don't count as uncovered

    def test_fuzzy_remap(self):
        themes = [
            _make_theme("Invoicing Problems", "High"),
            _make_theme("Expense Tracking", "Low"),
            _make_theme("Tax Prep", "Low"),
            _make_theme("Cash Flow", "Low"),
        ]
        extraction = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                # Slug drift: close enough for ≥0.7 fuzzy remap
                _make_unvalidated("PP one", parent_theme_id="invoicing-problem"),
                _make_unvalidated("PP two", parent_theme_id="invoicing-problems"),
                _make_unvalidated("PP three", parent_theme_id="invoicing-problems"),
            ],
            extraction_summary="ok",
        )
        orphans, uncovered = PainPointCrew._validate_theme_linkage(
            extraction, self._categorization(themes)
        )
        assert orphans == []
        assert extraction.extracted_pain_points[0].parent_theme_id == "invoicing-problems"

    def test_orphan_cleared_and_uncovered_reported(self):
        themes = [
            _make_theme("Invoicing Problems", "High"),
            _make_theme("Hardware Compatibility", "Medium"),
            _make_theme("Tax Prep", "Low"),
            _make_theme("Cash Flow", "Low"),
        ]
        extraction = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                _make_unvalidated("PP one", parent_theme_id="invoicing-problems"),
                _make_unvalidated("PP two", parent_theme_id="totally-unrelated-slug"),
                _make_unvalidated("PP three", parent_theme_id="invoicing-problems"),
            ],
            extraction_summary="ok",
        )
        orphans, uncovered = PainPointCrew._validate_theme_linkage(
            extraction, self._categorization(themes)
        )
        assert ("PP two", "totally-unrelated-slug") in orphans
        assert extraction.extracted_pain_points[1].parent_theme_id is None
        assert [t.category_name for t in uncovered] == ["Hardware Compatibility"]


class TestFormatPainPointsWithEvidence:
    """Quote/word caps and zero-quote messaging in the Task 3 evidence block."""

    def test_caps_quotes_and_words(self):
        long_quote = " ".join(["word"] * 150)
        enrichment = QuoteEnrichmentResult(
            niche="test",
            enriched_pain_points=[
                _make_enrichment(
                    quotes=[
                        ExtractedQuote(quote_text=long_quote, post_id=f"p{i}")
                        for i in range(5)
                    ],
                    matched_post_ids=["p0", "p1", "p2", "p3", "p4"],
                )
            ],
            total_quotes_found=5,
            enrichment_summary="ok",
        )
        text = PainPointCrew._format_pain_points_with_evidence(
            [_make_unvalidated()], enrichment
        )
        assert text.count("[source:") == 3  # capped at 3 quotes
        assert "[…]" in text  # word-truncation marker
        # No single quoted line exceeds ~100 words
        for line in text.splitlines():
            if line.strip().startswith('- "'):
                assert len(line.split()) <= 105

    def test_zero_quotes_message(self):
        enrichment = QuoteEnrichmentResult(
            niche="test",
            enriched_pain_points=[_make_enrichment(quotes=[], matched_post_ids=[])],
            total_quotes_found=0,
            enrichment_summary="ok",
        )
        text = PainPointCrew._format_pain_points_with_evidence(
            [_make_unvalidated()], enrichment
        )
        assert "NONE FOUND" in text
        assert "≤ 0.45" in text

    def test_fuzzy_title_match(self):
        enrichment = QuoteEnrichmentResult(
            niche="test",
            enriched_pain_points=[
                _make_enrichment(
                    title="Manual Invoicing!",  # near-exact
                    quotes=[ExtractedQuote(quote_text="a real user quote here", post_id="p1")],
                    matched_post_ids=["p1"],
                )
            ],
            total_quotes_found=1,
            enrichment_summary="ok",
        )
        text = PainPointCrew._format_pain_points_with_evidence(
            [_make_unvalidated(title="Manual Invoicing")], enrichment
        )
        assert "a real user quote here" in text


class TestUsageMetricsSumming:
    """usage_metrics must aggregate across all phase crews (A, B, corrective)."""

    def _crew_with_metrics(self, prompt, completion):
        crew = MagicMock()
        crew.usage_metrics = {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }
        return crew

    def test_sums_across_phase_crews(self):
        instance = PainPointCrew.__new__(PainPointCrew)
        instance._phase_crews = [
            self._crew_with_metrics(100, 50),
            self._crew_with_metrics(200, 30),
        ]
        metrics = instance.usage_metrics
        assert metrics == {
            "prompt_tokens": 300,
            "completion_tokens": 80,
            "total_tokens": 380,
        }

    def test_none_when_no_crews(self):
        instance = PainPointCrew.__new__(PainPointCrew)
        instance._phase_crews = []
        assert instance.usage_metrics is None

    def test_object_style_metrics(self):
        crew = MagicMock()
        crew.usage_metrics = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        instance = PainPointCrew.__new__(PainPointCrew)
        instance._phase_crews = [crew]
        assert instance.usage_metrics == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }


class TestToolAddressabilityCap:
    """Code-enforced, downgrade-only commercial-intent cap off the tool_addressable verdict."""

    def _resolve(self, tool_addressable, wtp=0.8, severity=0.8):
        sc = _make_scoring(severity=severity, wtp=wtp, level=OpportunityLevel.HIGH)
        sc.tool_addressable = tool_addressable
        # 5 supporting quotes so the low-evidence clamp does not interfere
        return PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(),
            matching_score=sc,
            quotes=["q1", "q2", "q3", "q4", "q5"],
            matching_enrichment=_make_enrichment(matched_post_ids=["p1", "p2"]),
            theme_mentions={},
        )

    def test_partial_caps_wtp_to_0_4(self):
        _, _, level, _, _, wtp = self._resolve("partial", wtp=0.8)
        assert wtp == 0.4
        # opportunity recomputed on capped wtp: severity 0.8 high, wtp 0.4 low -> MEDIUM
        assert level == OpportunityLevel.MEDIUM

    def test_none_caps_wtp_to_0_15(self):
        _, _, level, _, _, wtp = self._resolve("none", wtp=0.9)
        assert wtp == 0.15
        assert level == OpportunityLevel.MEDIUM  # severity high, wtp capped low

    def test_full_untouched(self):
        _, _, level, _, _, wtp = self._resolve("full", wtp=0.8)
        assert wtp == 0.8
        assert level == OpportunityLevel.HIGH

    def test_downgrade_only_never_raises(self):
        # already below the cap -> unchanged (cap can only lower)
        _, _, _, _, _, wtp = self._resolve("partial", wtp=0.3)
        assert wtp == 0.3

    def test_missing_field_defaults_full(self):
        sc = _make_scoring(severity=0.8, wtp=0.8)
        # do NOT set tool_addressable -> getattr default 'full' -> untouched
        _, _, _, _, _, wtp = PainPointCrew.resolve_pain_point_scores(
            unvalidated=_make_unvalidated(), matching_score=sc,
            quotes=["q1", "q2", "q3"], matching_enrichment=_make_enrichment(matched_post_ids=["p1"]),
            theme_mentions={},
        )
        assert wtp == 0.8


class TestConfigurableOpportunityCutoffs:
    """The 0.6 cutoffs are heuristic priors exposed as params (config-driven in the pipeline)."""

    def test_default_cutoffs_unchanged(self):
        assert compute_opportunity_level(0.6, 0.6) == OpportunityLevel.HIGH
        assert compute_opportunity_level(0.59, 0.59) == OpportunityLevel.LOW

    def test_raised_severity_cutoff_demotes(self):
        # with a stricter severity cutoff, 0.6 severity no longer counts as high
        assert compute_opportunity_level(0.6, 0.6, high_severity=0.8) == OpportunityLevel.MEDIUM

    def test_lowered_intent_cutoff_promotes(self):
        assert compute_opportunity_level(0.7, 0.4, high_commercial_intent=0.4) == OpportunityLevel.HIGH
