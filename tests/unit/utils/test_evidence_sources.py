"""Evidence-backed community counts.

Regression for run 8ef396eb: r/DublinConcerts was the LARGEST raw bucket (16 of 133
collected posts) and contributed ZERO posts to any pain point, yet the launch plan named
it the High-Priority channel ("Found 16 highly relevant discussions in r/DublinConcerts
during research") and then made it a KPI — in a plan scoped to U.S. metros.
"""

from types import SimpleNamespace

from nicheiq.utils.evidence_sources import evidence_subreddit_breakdown


def _post(post_id, subreddit):
    return SimpleNamespace(post_id=post_id, subreddit=subreddit)


def _pain(source_post_ids):
    return SimpleNamespace(source_post_ids=source_post_ids)


def _state(posts, pains):
    return SimpleNamespace(
        social_content=SimpleNamespace(reddit_posts=posts),
        pain_point_analysis=SimpleNamespace(pain_points=pains),
    )


class TestEvidenceSubredditBreakdown:
    def test_high_volume_zero_evidence_subreddit_is_excluded(self):
        posts = [_post(f"d{i}", "DublinConcerts") for i in range(16)]
        posts += [_post(f"m{i}", "Music") for i in range(5)]
        state = _state(posts, [_pain(["m0", "m1"]), _pain(["m2"])])

        breakdown = evidence_subreddit_breakdown(state)

        assert "DublinConcerts" not in breakdown
        assert breakdown == {"Music": 3}
        assert max(breakdown, key=breakdown.get) == "Music"

    def test_a_post_cited_by_several_pains_counts_once(self):
        state = _state([_post("m0", "Music")], [_pain(["m0"]), _pain(["m0"])])
        assert evidence_subreddit_breakdown(state) == {"Music": 1}

    def test_unknown_post_ids_are_ignored(self):
        state = _state([_post("m0", "Music")], [_pain(["m0", "gone", "hn-42"])])
        assert evidence_subreddit_breakdown(state) == {"Music": 1}

    def test_empty_when_no_pain_point_cites_a_post(self):
        posts = [_post("d0", "DublinConcerts")]
        assert evidence_subreddit_breakdown(_state(posts, [_pain([])])) == {}

    def test_empty_without_a_corpus_or_analysis(self):
        assert evidence_subreddit_breakdown(SimpleNamespace()) == {}
        assert evidence_subreddit_breakdown(_state([], [])) == {}
