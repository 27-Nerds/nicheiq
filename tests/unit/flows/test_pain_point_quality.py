"""Tests for _validate_pain_point_quality tier classification in ResearchFlow.

Quality tiers measure RESEARCH QUALITY (evidence breadth/diversity), not niche
attractiveness. Severity, WTP, and opportunity scores are excluded — they belong
in the go/no-go verdict pipeline.
"""

import types
from datetime import datetime
from unittest.mock import patch

import pytest

from nicheiq.models.keyword_data import OpportunityLevel
from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult
from nicheiq.models.social_content import RedditPost, SocialContentCollection


def _make_pain_point(
    severity: float = 0.8,
    wtp: float = 0.5,
    opportunity: OpportunityLevel = OpportunityLevel.HIGH,
    num_quotes: int = 10,
    platforms: list[str] | None = None,
    num_source_ids: int | None = None,
    source_id_prefix: str = "post",
) -> PainPoint:
    """Helper to create a PainPoint with configurable fields."""
    if platforms is None:
        platforms = ["Reddit"]
    if num_source_ids is None:
        num_source_ids = num_quotes
    quotes = [f"Quote text number {i} with enough words" for i in range(num_quotes)]
    source_ids = [f"{source_id_prefix}_{i}" for i in range(num_source_ids)]
    return PainPoint(
        title="Test Pain Point",
        description="A test pain point description",
        mention_count=50,
        severity_score=severity,
        willingness_to_pay=wtp,
        opportunity_level=opportunity,
        representative_quotes=quotes,
        source_platforms=platforms,
        categories=["TestCategory"],
        source_post_ids=source_ids,
    )


def _make_analysis(pain_points: list[PainPoint]) -> PainPointAnalysisResult:
    """Helper to create a PainPointAnalysisResult."""
    return PainPointAnalysisResult(
        niche="Test Niche",
        pain_points=pain_points,
        total_mentions=sum(pp.mention_count for pp in pain_points),
        top_categories=["TestCategory"],
        analysis_summary="Test summary",
    )


def _make_reddit_posts(pairs: list[tuple[str, str]]) -> list[RedditPost]:
    """Build minimal RedditPost list from [(post_id, subreddit), ...] pairs."""
    return [
        RedditPost(
            post_id=pid,
            title="Test post",
            selftext="",
            author="testuser",
            subreddit=sub,
            score=10,
            num_comments=5,
            created_utc=datetime(2024, 1, 1),
            url=f"https://reddit.com/r/{sub}/comments/{pid}",
        )
        for pid, sub in pairs
    ]


def _validate(analysis, reddit_posts=None, enable_twitter=False, enable_reddit=True):
    """Run _validate_pain_point_quality with mocked settings and social content."""
    from nicheiq.flows.research_flow import ResearchFlow

    flow = ResearchFlow.__new__(ResearchFlow)
    # Flow.state is a read-only property backed by _state
    flow._state = types.SimpleNamespace(
        social_content=SocialContentCollection(
            reddit_posts=reddit_posts or []
        )
    )
    with patch("nicheiq.flows.research_flow.settings") as mock_settings:
        mock_settings.enable_twitter = enable_twitter
        mock_settings.enable_reddit = enable_reddit
        return flow._validate_pain_point_quality(analysis)


def _build_gold_dataset():
    """Build a dataset that meets GOLD tier requirements.

    GOLD needs: unique_source_count >= 20, subreddit_diversity >= 4,
    pain_point_count >= 5, quote_density >= 8.
    """
    # 5 pain points, each with 8 quotes from 4 unique sources across 4 subreddits
    subreddits = ["freelance", "entrepreneur", "startups", "smallbusiness"]
    pps = []
    all_post_pairs = []
    for i in range(5):
        prefix = f"pp{i}"
        pp = _make_pain_point(
            num_quotes=8,
            num_source_ids=8,
            source_id_prefix=prefix,
        )
        pps.append(pp)
        # Map each pain point's sources to a subreddit (rotate across subreddits)
        for j in range(8):
            sub = subreddits[(i + j) % len(subreddits)]
            all_post_pairs.append((f"{prefix}_{j}", sub))

    # Deduplicate post pairs (same post_id should map to same subreddit)
    seen = set()
    unique_pairs = []
    for pid, sub in all_post_pairs:
        if pid not in seen:
            seen.add(pid)
            unique_pairs.append((pid, sub))

    return pps, unique_pairs


# =============================================================================
# GOLD tier tests
# =============================================================================


class TestGoldTier:
    def test_gold_tier_with_diverse_evidence(self):
        """5+ PPs, 20+ unique sources, 4+ subreddits, quote_density >= 8 → GOLD."""
        pps, post_pairs = _build_gold_dataset()
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, score = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "GOLD"
        assert 0.0 <= score <= 1.0

    def test_gold_tier_boundary_minimum(self):
        """Exactly at GOLD thresholds → GOLD."""
        # 5 PPs × 4 unique sources each = 20 unique sources
        subreddits = ["sub_a", "sub_b", "sub_c", "sub_d"]
        pps = []
        post_pairs = []
        for i in range(5):
            pp = _make_pain_point(num_quotes=8, num_source_ids=4, source_id_prefix=f"g{i}")
            pps.append(pp)
            for j in range(4):
                post_pairs.append((f"g{i}_{j}", subreddits[j]))

        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "GOLD"


# =============================================================================
# SILVER tier tests
# =============================================================================


class TestSilverTier:
    def test_silver_tier_moderate_evidence(self):
        """3 PPs, 12 unique sources, 2 subreddits → SILVER."""
        pps = []
        post_pairs = []
        for i in range(3):
            pp = _make_pain_point(num_quotes=6, num_source_ids=4, source_id_prefix=f"s{i}")
            pps.append(pp)
            for j in range(4):
                sub = "freelance" if (i + j) % 2 == 0 else "startups"
                post_pairs.append((f"s{i}_{j}", sub))

        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "SILVER"

    def test_silver_not_gold_insufficient_subreddits(self):
        """20+ unique sources but only 3 subreddits → SILVER (GOLD needs 4)."""
        pps = []
        post_pairs = []
        for i in range(5):
            pp = _make_pain_point(num_quotes=8, num_source_ids=4, source_id_prefix=f"ns{i}")
            pps.append(pp)
            for j in range(4):
                # Only 3 subreddits — fails GOLD diversity gate
                sub = ["sub_a", "sub_b", "sub_c"][j % 3]
                post_pairs.append((f"ns{i}_{j}", sub))

        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "SILVER"

    def test_silver_many_sources_one_subreddit(self):
        """15 unique sources but all from 1 subreddit → BRONZE (SILVER needs 2)."""
        pps = []
        post_pairs = []
        for i in range(3):
            pp = _make_pain_point(num_quotes=6, num_source_ids=5, source_id_prefix=f"os{i}")
            pps.append(pp)
            for j in range(5):
                post_pairs.append((f"os{i}_{j}", "only_subreddit"))

        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        # 15 unique sources >= 10 (SILVER), but subreddit_diversity = 1 < 2
        assert tier == "BRONZE"


# =============================================================================
# BRONZE tier tests
# =============================================================================


class TestBronzeTier:
    def test_bronze_tier_minimum_viable(self):
        """2 PPs, 6 unique sources, quote_density=4 → BRONZE."""
        pps = [
            _make_pain_point(num_quotes=4, num_source_ids=3, source_id_prefix=f"b{i}")
            for i in range(2)
        ]
        post_pairs = [(f"b{i}_{j}", "freelance") for i in range(2) for j in range(3)]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "BRONZE"

    def test_bronze_no_subreddit_gate(self):
        """BRONZE has no subreddit_diversity gate — single subreddit is OK."""
        pps = [
            _make_pain_point(num_quotes=4, num_source_ids=3, source_id_prefix=f"bs{i}")
            for i in range(2)
        ]
        post_pairs = [(f"bs{i}_{j}", "only_sub") for i in range(2) for j in range(3)]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "BRONZE"


# =============================================================================
# INSUFFICIENT tier tests
# =============================================================================


class TestInsufficientTier:
    def test_insufficient_too_few_sources(self):
        """2 PPs with only 4 unique sources (< 5) → INSUFFICIENT."""
        pps = [
            _make_pain_point(num_quotes=4, num_source_ids=2, source_id_prefix=f"is{i}")
            for i in range(2)
        ]
        post_pairs = [(f"is{i}_{j}", "sub") for i in range(2) for j in range(2)]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "INSUFFICIENT"

    def test_insufficient_too_few_pain_points(self):
        """1 PP with many sources → INSUFFICIENT (need >= 2)."""
        pp = _make_pain_point(num_quotes=12, num_source_ids=12, source_id_prefix="ip")
        post_pairs = [(f"ip_{i}", f"sub_{i % 5}") for i in range(12)]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis([pp])
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "INSUFFICIENT"

    def test_insufficient_low_quote_density(self):
        """3 PPs, quote_density=2 → INSUFFICIENT (need >= 3)."""
        pps = [
            _make_pain_point(num_quotes=2, num_source_ids=2, source_id_prefix=f"iq{i}")
            for i in range(3)
        ]
        post_pairs = [(f"iq{i}_{j}", "sub") for i in range(3) for j in range(2)]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        assert tier == "INSUFFICIENT"

    def test_insufficient_empty_pain_points(self):
        """0 PPs → INSUFFICIENT."""
        analysis = _make_analysis([])
        tier, score = _validate(analysis)
        assert tier == "INSUFFICIENT"
        assert score == 0.0


# =============================================================================
# Evidence-only behavior tests (regression guards)
# =============================================================================


class TestEvidenceOnlyBehavior:
    """Confirm quality tier measures evidence, NOT niche attractiveness."""

    def test_high_severity_few_sources_not_gold(self):
        """High severity/WTP but only 3 unique sources → NOT GOLD."""
        pps = [
            _make_pain_point(
                severity=0.95, wtp=0.9, opportunity=OpportunityLevel.HIGH,
                num_quotes=8, num_source_ids=1, source_id_prefix=f"hs{i}",
            )
            for i in range(5)
        ]
        # Only 5 unique sources, 1 subreddit
        post_pairs = [(f"hs{i}_0", "hot_niche") for i in range(5)]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        # Excellent niche metrics, but minimal evidence diversity → BRONZE
        assert tier == "BRONZE"

    def test_low_severity_many_sources_gold(self):
        """Low severity/WTP but 20+ diverse sources → GOLD."""
        pps = []
        post_pairs = []
        subreddits = ["sub_a", "sub_b", "sub_c", "sub_d"]
        for i in range(5):
            pp = _make_pain_point(
                severity=0.2, wtp=0.1, opportunity=OpportunityLevel.LOW,
                num_quotes=8, num_source_ids=4, source_id_prefix=f"ls{i}",
            )
            pps.append(pp)
            for j in range(4):
                post_pairs.append((f"ls{i}_{j}", subreddits[j]))

        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        # Terrible niche metrics, but excellent evidence → GOLD
        assert tier == "GOLD"

    def test_single_pp_many_sources_insufficient(self):
        """1 PP with 25 sources across 5 subreddits → still INSUFFICIENT."""
        pp = _make_pain_point(num_quotes=12, num_source_ids=12, source_id_prefix="sp")
        post_pairs = [(f"sp_{i}", f"sub_{i % 5}") for i in range(12)]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis([pp])
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        # pain_point_count = 1 < 2 → INSUFFICIENT
        assert tier == "INSUFFICIENT"


# =============================================================================
# Edge case tests
# =============================================================================


class TestEdgeCases:
    def test_all_same_post(self):
        """All source_post_ids point to the same post → unique_source_count=1."""
        pps = [
            PainPoint(
                title=f"PP {i}", description="desc", mention_count=10,
                severity_score=0.5, willingness_to_pay=0.5,
                opportunity_level=OpportunityLevel.MEDIUM,
                representative_quotes=[f"quote {j}" for j in range(5)],
                source_platforms=["Reddit"],
                source_post_ids=["same_post"] * 5,
            )
            for i in range(3)
        ]
        post_pairs = [("same_post", "one_sub")]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        # unique_source_count=1 < 5 → INSUFFICIENT
        assert tier == "INSUFFICIENT"

    def test_orphan_source_ids_no_crash(self):
        """source_post_ids that don't exist in social_content → no crash, lower diversity."""
        pps = [
            _make_pain_point(num_quotes=6, num_source_ids=6, source_id_prefix=f"orph{i}")
            for i in range(3)
        ]
        # Only provide reddit_posts for some IDs — others are "orphans"
        post_pairs = [
            ("orph0_0", "sub_a"), ("orph0_1", "sub_b"),
            ("orph1_0", "sub_a"), ("orph1_1", "sub_c"),
        ]
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        # Should not crash — orphan IDs just don't contribute to subreddit diversity
        tier, score = _validate(analysis, reddit_posts=reddit_posts)
        assert tier in ("GOLD", "SILVER", "BRONZE", "INSUFFICIENT")
        assert 0.0 <= score <= 1.0

    def test_empty_source_post_ids(self):
        """All PPs have quotes but empty source_post_ids → max tier BRONZE."""
        pps = [
            _make_pain_point(num_quotes=10, num_source_ids=0, source_id_prefix=f"e{i}")
            for i in range(5)
        ]
        reddit_posts = _make_reddit_posts([])
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, reddit_posts=reddit_posts)
        # unique_source_count=0 < 5 → INSUFFICIENT
        assert tier == "INSUFFICIENT"

    def test_no_social_content(self):
        """social_content with no reddit_posts → subreddit_diversity=0, no crash."""
        pps = [
            _make_pain_point(num_quotes=6, num_source_ids=6, source_id_prefix=f"nc{i}")
            for i in range(3)
        ]
        analysis = _make_analysis(pps)
        # No reddit_posts at all — subreddit lookup returns nothing
        tier, score = _validate(analysis, reddit_posts=[])
        assert 0.0 <= score <= 1.0


# =============================================================================
# Confidence score tests
# =============================================================================


class TestConfidenceScore:
    def test_perfect_dataset_near_max_score(self):
        """Perfect evidence → confidence score near 1.0."""
        pps, post_pairs = _build_gold_dataset()
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        _, score = _validate(analysis, reddit_posts=reddit_posts)
        # 40 unique sources, 4 subreddits, 8 quotes/pp, 5 PPs
        # All metrics should be at or near max normalization
        assert score > 0.7

    def test_single_platform_weights_sum_to_one(self):
        """Verify single-platform weights produce score in [0, 1]."""
        pps, post_pairs = _build_gold_dataset()
        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        _, score = _validate(analysis, reddit_posts=reddit_posts, enable_twitter=False)
        # Weights: 0.30 + 0.25 + 0.25 + 0.0 + 0.20 = 1.0
        assert 0.0 <= score <= 1.0

    def test_dual_platform_cross_platform_contributes(self):
        """Dual-platform mode: cross-platform pain points increase score."""
        # Single-platform pain points
        pps_single = []
        post_pairs = []
        for i in range(5):
            pp = _make_pain_point(
                num_quotes=8, num_source_ids=4,
                source_id_prefix=f"dp{i}", platforms=["Reddit"],
            )
            pps_single.append(pp)
            for j in range(4):
                sub = ["sub_a", "sub_b", "sub_c", "sub_d"][j]
                post_pairs.append((f"dp{i}_{j}", sub))

        reddit_posts = _make_reddit_posts(post_pairs)

        analysis_single = _make_analysis(pps_single)
        _, score_single = _validate(
            analysis_single, reddit_posts=reddit_posts,
            enable_twitter=True, enable_reddit=True,
        )

        # Same but cross-platform
        pps_cross = []
        for i in range(5):
            pp = _make_pain_point(
                num_quotes=8, num_source_ids=4,
                source_id_prefix=f"dp{i}", platforms=["Reddit", "Twitter"],
            )
            pps_cross.append(pp)

        analysis_cross = _make_analysis(pps_cross)
        _, score_cross = _validate(
            analysis_cross, reddit_posts=reddit_posts,
            enable_twitter=True, enable_reddit=True,
        )

        # Cross-platform version should score higher
        assert score_cross > score_single

    def test_normalization_caps(self):
        """Metrics beyond normalization max don't increase score beyond 1.0 contribution."""
        # 60 unique sources (cap is 30), 10 subreddits (cap is 5)
        pps = []
        post_pairs = []
        for i in range(8):
            pp = _make_pain_point(
                num_quotes=12, num_source_ids=12,
                source_id_prefix=f"cap{i}",
            )
            pps.append(pp)
            for j in range(12):
                sub = f"sub_{j % 10}"
                post_pairs.append((f"cap{i}_{j}", sub))

        reddit_posts = _make_reddit_posts(post_pairs)
        analysis = _make_analysis(pps)
        _, score = _validate(analysis, reddit_posts=reddit_posts)
        # All metrics at or above cap → score should be ~1.0
        assert score <= 1.0
        assert score > 0.95
