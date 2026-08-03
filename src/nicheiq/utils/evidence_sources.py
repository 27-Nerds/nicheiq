"""Which communities actually produced EVIDENCE, not just scraped volume.

A subreddit can dominate the raw collection and contribute nothing: run 8ef396eb pulled 16
posts from r/DublinConcerts (the single largest bucket, 133 posts total) and not one of them
survived into a pain point, yet the launch plan named it the High-Priority channel — "Found
16 highly relevant discussions in r/DublinConcerts during research" — and then turned it into
a KPI, in a plan scoped to U.S. metros.

The counts here are keyed on ``PainPoint.source_post_ids``: a community is only credited for
the posts a pain point actually cites. Recommendation copy should use these, not the raw
collection breakdown (which stays correct for "how much did we read").
"""

from __future__ import annotations


def evidence_subreddit_breakdown(state) -> dict[str, int]:
    """{subreddit: number of its posts cited by >=1 pain point}.

    Empty when there is no Reddit corpus or no pain point cites a post — callers should
    treat empty as "no evidence-backed community", never as a reason to fall back to raw
    collection volume.
    """
    social = getattr(state, "social_content", None)
    posts = getattr(social, "reddit_posts", None) or []
    analysis = getattr(state, "pain_point_analysis", None)
    pains = getattr(analysis, "pain_points", None) or []
    if not posts or not pains:
        return {}

    subreddit_by_id = {
        p.post_id: p.subreddit for p in posts if getattr(p, "post_id", None)
    }
    cited: set[str] = set()
    for pain in pains:
        cited.update(getattr(pain, "source_post_ids", None) or [])

    breakdown: dict[str, int] = {}
    for post_id in cited:
        subreddit = subreddit_by_id.get(post_id)
        if subreddit:
            breakdown[subreddit] = breakdown.get(subreddit, 0) + 1
    return breakdown
