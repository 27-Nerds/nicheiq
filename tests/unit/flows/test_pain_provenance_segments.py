"""Tests for workstream C (provenance-aware per-pain audience signal): PainPoint.evidence_segments.

Covers the three new pieces in ResearchFlow: _build_post_to_subreddit (corpus -> post_id map),
_build_validated_hubs_by_segment (corpus-present-subreddit hub validation, fail-soft), and the
_map_pain_points_to_segments wiring gated by settings.pain_provenance_segments. The pure matching
logic (match_pain_by_provenance) is covered separately in tests/unit/test_pain_segment_coverage.py.
"""

import types
from datetime import datetime
from unittest.mock import patch

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.keyword_data import OpportunityLevel
from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult
from nicheiq.models.research_state import AudienceMappingResult, AudienceSegment
from nicheiq.models.social_content import RedditPost, SocialContentCollection, SocialPost


def _pain(title: str = "Pain", source_post_ids: list[str] | None = None) -> PainPoint:
    return PainPoint(
        title=title,
        description="desc",
        mention_count=5,
        severity_score=0.5,
        commercial_intent=0.5,
        opportunity_level=OpportunityLevel.HIGH,
        representative_quotes=["q1"],
        source_post_ids=source_post_ids or [],
    )


def _analysis(pain_points: list[PainPoint]) -> PainPointAnalysisResult:
    return PainPointAnalysisResult(
        niche="n", pain_points=pain_points, total_mentions=len(pain_points),
        top_categories=["c"], analysis_summary="s",
    )


def _reddit_post(post_id: str, subreddit: str) -> RedditPost:
    return RedditPost(
        post_id=post_id, title="t", selftext="", author="u", subreddit=subreddit,
        score=1, num_comments=0, created_utc=datetime(2024, 1, 1),
        url=f"https://reddit.com/r/{subreddit}/comments/{post_id}",
    )


def _generic_post(post_id: str, platform: str) -> SocialPost:
    return SocialPost(
        post_id=post_id, platform=platform, title="t", body="b", author="u",
        url="https://example.com", score=1, num_responses=0,
        created_utc=datetime(2024, 1, 1),
    )


def _flow(social_content=None, pain_point_analysis=None) -> ResearchFlow:
    flow = ResearchFlow.__new__(ResearchFlow)
    # Flow.state is a read-only property backed by _state (see test_pain_point_quality.py)
    flow._state = types.SimpleNamespace(
        social_content=social_content, pain_point_analysis=pain_point_analysis,
    )
    return flow


def _segment(name: str, discovery_channels: list[str] = ()) -> AudienceSegment:
    return AudienceSegment(
        segment_name=name, size_estimate="Medium", pain_point_alignment=["a"],
        motivation_drivers=["m"], expertise_level="Intermediate", budget_sensitivity="Medium",
        discovery_channels=list(discovery_channels),
    )


def _audience_result(segments: list[AudienceSegment], community_hubs: list[str] = ()) -> AudienceMappingResult:
    return AudienceMappingResult(
        audience_segments=segments,
        primary_target_segment=segments[0].segment_name if segments else "",
        segment_prioritization_rationale="r",
        community_hubs=list(community_hubs),
        content_preferences="p",
        messaging_frameworks=["m"],
        tools_currently_used=["t"],
        frustrations_with_existing=["f"],
        recommended_channels=["c"],
    )


class TestBuildPostToSubreddit:
    def test_mixed_reddit_and_generic_content(self):
        sc = SocialContentCollection(
            reddit_posts=[_reddit_post("p1", "OwnerOperators"), _reddit_post("p2", "Truckers")],
            generic_posts=[_generic_post("g1", "hackernews")],
        )
        flow = _flow(social_content=sc)
        assert flow._build_post_to_subreddit() == {
            "p1": "OwnerOperators", "p2": "Truckers", "g1": "hackernews",
        }

    def test_no_social_content_returns_empty_dict(self):
        assert _flow(social_content=None)._build_post_to_subreddit() == {}


class TestBuildValidatedHubsBySegment:
    def test_corpus_present_validation_drops_fabricated_hub_names(self):
        sc = SocialContentCollection(reddit_posts=[_reddit_post("p1", "OwnerOperators")])
        flow = _flow(social_content=sc)
        post_to_subreddit = flow._build_post_to_subreddit()
        segs = [_segment(
            "Owner-Operators",
            discovery_channels=["Reddit (r/OwnerOperators, r/FakeSubThatDoesntExist)"],
        )]
        audience_result = _audience_result(segs, community_hubs=["r/OwnerOperators"])

        out = flow._build_validated_hubs_by_segment(audience_result, post_to_subreddit)

        # Real (corpus-present) sub kept; hallucinated one dropped without ever calling an API.
        assert out == {"Owner-Operators": {"owneroperators"}}

    def test_segment_with_no_own_hubs_stays_unmatched_not_niche_wide(self):
        # A segment without its own corpus-validated hubs must NOT inherit the shared niche-wide
        # community_hubs prior -- that would let one niche-hub post attribute its pain to multiple
        # unrelated segments, contradicting evidence_segments' provenance contract.
        sc = SocialContentCollection(reddit_posts=[_reddit_post("p1", "Logistics")])
        flow = _flow(social_content=sc)
        post_to_subreddit = flow._build_post_to_subreddit()
        segs = [_segment("Vague Segment", discovery_channels=["LinkedIn", "Industry forums"])]
        audience_result = _audience_result(segs, community_hubs=["r/Logistics"])

        out = flow._build_validated_hubs_by_segment(audience_result, post_to_subreddit)

        assert out == {"Vague Segment": set()}

    def test_no_corpus_subreddits_returns_empty_dict(self):
        flow = _flow(social_content=SocialContentCollection(reddit_posts=[]))
        out = flow._build_validated_hubs_by_segment(_audience_result([_segment("S")]), {})
        assert out == {}


class TestMapPainPointsToSegmentsProvenanceWiring:
    def test_setting_off_leaves_evidence_segments_none(self):
        sc = SocialContentCollection(reddit_posts=[_reddit_post("p1", "OwnerOperators")])
        pain = _pain(source_post_ids=["p1"])
        flow = _flow(social_content=sc, pain_point_analysis=_analysis([pain]))
        segs = [_segment("Owner-Operators", discovery_channels=["r/OwnerOperators"])]
        audience_result = _audience_result(segs, community_hubs=["r/OwnerOperators"])

        with patch("nicheiq.flows.research_flow.settings") as mock_settings:
            mock_settings.pain_provenance_segments = False
            flow._map_pain_points_to_segments(audience_result)

        assert pain.evidence_segments is None

    def test_setting_on_populates_evidence_segments_via_provenance(self):
        sc = SocialContentCollection(reddit_posts=[_reddit_post("p1", "OwnerOperators")])
        pain = _pain(title="Fuel cost tracking is a nightmare", source_post_ids=["p1"])
        flow = _flow(social_content=sc, pain_point_analysis=_analysis([pain]))
        segs = [_segment("Owner-Operators", discovery_channels=["r/OwnerOperators"])]
        audience_result = _audience_result(segs, community_hubs=["r/OwnerOperators"])

        with patch("nicheiq.flows.research_flow.settings") as mock_settings:
            mock_settings.pain_provenance_segments = True
            flow._map_pain_points_to_segments(audience_result)

        assert pain.evidence_segments == ["Owner-Operators"]

    def test_no_source_post_overlap_leaves_evidence_segments_none(self):
        sc = SocialContentCollection(reddit_posts=[_reddit_post("p1", "UnrelatedSub")])
        pain = _pain(source_post_ids=["p1"])
        flow = _flow(social_content=sc, pain_point_analysis=_analysis([pain]))
        segs = [_segment("Owner-Operators", discovery_channels=["r/OwnerOperators"])]
        audience_result = _audience_result(segs, community_hubs=["r/OwnerOperators"])

        with patch("nicheiq.flows.research_flow.settings") as mock_settings:
            mock_settings.pain_provenance_segments = True
            flow._map_pain_points_to_segments(audience_result)

        assert pain.evidence_segments is None


class TestLegacyCheckpointCompatibility:
    def test_pain_point_without_evidence_segments_key_loads_with_default_none(self):
        # Legacy checkpoint shape: dict predates the evidence_segments field entirely.
        legacy_data = {
            "title": "Legacy pain",
            "description": "desc",
            "mention_count": 3,
            "severity_score": 0.5,
            "commercial_intent": 0.4,
            "opportunity_level": "high",
            "representative_quotes": ["q"],
        }
        pain = PainPoint(**legacy_data)
        assert pain.evidence_segments is None


class TestStage4ResumeBackfillsProvenanceMapping:
    def test_resumed_state_with_populated_affected_segments_but_all_none_evidence_segments_reruns_mapping(self):
        # Legacy checkpoint: lexical mapping already ran (affected_segments populated), so the old
        # "any affected_segments is None" resume condition would skip _map_pain_points_to_segments
        # entirely and evidence_segments would stay None forever. With pain_provenance_segments on
        # and social_content available, resume must rerun the mapping to backfill it.
        sc = SocialContentCollection(reddit_posts=[_reddit_post("p1", "OwnerOperators")])
        pain = _pain(title="Fuel cost tracking is a nightmare", source_post_ids=["p1"])
        pain.affected_segments = ["Owner-Operators"]
        pain.evidence_segments = None
        segs = [_segment("Owner-Operators", discovery_channels=["r/OwnerOperators"])]
        audience_result = _audience_result(segs, community_hubs=["r/OwnerOperators"])

        flow = _flow(social_content=sc, pain_point_analysis=_analysis([pain]))
        flow._state.audience_mapping = audience_result
        flow.checkpoint_mgr = types.SimpleNamespace(save_stage=lambda *a, **k: None)

        with patch("nicheiq.flows.research_flow.settings") as mock_settings:
            mock_settings.pain_provenance_segments = True
            flow.stage_4_audience_mapping()

        assert pain.evidence_segments == ["Owner-Operators"]
        assert flow.state.current_stage == 5

    def test_resumed_state_with_provenance_setting_off_does_not_rerun(self):
        sc = SocialContentCollection(reddit_posts=[_reddit_post("p1", "OwnerOperators")])
        pain = _pain(title="Fuel cost tracking is a nightmare", source_post_ids=["p1"])
        pain.affected_segments = ["Owner-Operators"]
        pain.evidence_segments = None
        segs = [_segment("Owner-Operators", discovery_channels=["r/OwnerOperators"])]
        audience_result = _audience_result(segs, community_hubs=["r/OwnerOperators"])

        flow = _flow(social_content=sc, pain_point_analysis=_analysis([pain]))
        flow._state.audience_mapping = audience_result
        flow.checkpoint_mgr = types.SimpleNamespace(save_stage=lambda *a, **k: None)

        with patch("nicheiq.flows.research_flow.settings") as mock_settings:
            mock_settings.pain_provenance_segments = False
            flow.stage_4_audience_mapping()

        assert pain.evidence_segments is None
