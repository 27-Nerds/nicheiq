"""Regression coverage for strict Hacker News relevance handling."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.social_content import SocialContentCollection, SocialPost


def _generic_post(
    post_id: str,
    *,
    platform: str = "hackernews",
    relevance_grade: int | None = None,
) -> SocialPost:
    return SocialPost(
        post_id=post_id,
        platform=platform,
        title=f"Post {post_id}",
        body="Evidence body",
        author="author",
        url=f"https://example.com/{post_id}",
        score=10,
        num_responses=5,
        created_utc=datetime.now(timezone.utc),
        relevance_grade=relevance_grade,
    )


def test_stage2_propagates_hn_candidate_and_relevant_counts():
    flow = ResearchFlow(
        niche_description="Freelance bookkeepers managing month-end close",
        job_id="hn-counts",
    )
    posts = [_generic_post("relevant", relevance_grade=3)]
    flow.hackernews_tool = MagicMock()
    flow.hackernews_tool.search_relevant_and_collect.return_value = SimpleNamespace(
        posts=posts,
        candidate_count=7,
        relevant_count=1,
    )

    result = flow._search_hackernews_pipeline(
        [SimpleNamespace(query="month end close", platform="hackernews")],
        flow.niche_description,
    )

    assert result.posts == posts
    assert result.unique_results_count == 7
    assert result.relevant_urls_count == 1


def test_discovery_materializer_omits_unvalidated_hn_but_keeps_other_platforms(
    tmp_path,
):
    flow = ResearchFlow(
        niche_description="Freelance bookkeepers managing month-end close",
        job_id="hn-materializer",
    )
    flow.state.social_content = SocialContentCollection(
        generic_posts=[
            _generic_post("legacy-ungraded"),
            _generic_post("adjacent", relevance_grade=1),
            _generic_post("relevant", relevance_grade=2),
            _generic_post("youtube", platform="youtube"),
        ],
        total_generic_responses=20,
    )
    flow.state.filtering_stats = {
        "total_urls_searched": 10,
        "total_urls_relevant": 4,
        "hackernews_posts_collected": 3,
    }
    flow.state.social_content_metrics = {
        "total_sources": 4,
        "total_engagement": 40,
        "avg_engagement_per_source": 10,
    }
    flow.state.sources_searched = {
        "hackernews": {"enabled": True, "posts_found": 3},
        "youtube": {"enabled": True, "posts_found": 1},
    }

    path = flow._materialize_discovery_data(str(tmp_path))

    assert path is not None
    data = json.loads(Path(path).read_text())
    sample_urls = {row["url"] for row in data["social_posts_sample"]}
    assert sample_urls == {
        "https://example.com/relevant",
        "https://example.com/youtube",
    }
    assert data["subreddit_post_counts"] == {"Hacker News": 1, "YouTube": 1}
    assert data["sources_searched"]["hackernews"]["posts_found"] == 1
    assert data["methodology"]["urls_relevant"] == 2
    assert data["methodology"]["total_engagement"] == 20
