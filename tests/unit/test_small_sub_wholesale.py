"""Small-sub collection fixes (2026-07-02, live-diagnosed on cottage-food run #3).

Two failure modes starved discovered dedicated subreddits of any contribution:
1. Native search inside tiny subs (multi-word queries, time-windowed) is structurally empty
   → fetch_small_subreddit_posts pulls new/top(all) listings wholesale.
2. Absolute engagement bars killed grade-2 niche posts (score 1-3, 0-3 comments)
   → _passes_quality waives bars for posts from subs <= reddit_small_sub_max_subscribers.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import nicheiq.tools.reddit_tool as rt
from nicheiq.config.settings import settings
from nicheiq.models.social_content import RedditPost
from nicheiq.tools.reddit_tool import RedditCollectorTool


@pytest.fixture(autouse=True)
def _clear_subscriber_cache():
    rt._SUB_SUBSCRIBERS_CACHE.clear()
    yield
    rt._SUB_SUBSCRIBERS_CACHE.clear()


def _post(score=1, comments=0, subscribers=None):
    return RedditPost(
        post_id="x1", title="Oklahoma Small Business Cottage Food", selftext="short",
        author="u", subreddit="CottageFoodBusiness", score=score, num_comments=comments,
        created_utc=datetime.now(tz=timezone.utc), url="https://reddit.com/r/x/1",
        subreddit_subscribers=subscribers,
    )


class TestSmallSubQualityWaiver:
    def test_small_sub_low_engagement_passes(self):
        # live-observed casualty: grade-2 niche post, score 1, 0 comments — must now pass
        tool = RedditCollectorTool()
        assert tool._passes_quality(_post(score=1, comments=0, subscribers=83), grade=2)

    def test_small_sub_still_needs_min_score(self):
        tool = RedditCollectorTool()
        assert not tool._passes_quality(_post(score=0, subscribers=83), grade=3)

    def test_unknown_subscribers_keeps_full_bars(self):
        # legacy cached posts deserialize with subreddit_subscribers=None → old behavior
        tool = RedditCollectorTool()
        assert not tool._passes_quality(_post(score=1, comments=0, subscribers=None), grade=None)

    def test_big_sub_keeps_full_bars(self):
        tool = RedditCollectorTool()
        big = settings.reddit_small_sub_max_subscribers + 1
        assert not tool._passes_quality(_post(score=1, comments=0, subscribers=big), grade=None)


def _submission(pid, title, selftext=""):
    return SimpleNamespace(permalink=f"/r/s/comments/{pid}/", title=title, selftext=selftext)


def _fake_client(subs_by_name):
    return SimpleNamespace(subreddit=lambda name: subs_by_name[name])


def _fake_sub(subscribers, new_posts=(), top_posts=()):
    return SimpleNamespace(
        display_name="s", subscribers=subscribers,
        new=lambda limit: iter(new_posts),
        top=lambda time_filter, limit: iter(top_posts),
    )


class TestFetchSmallSubredditPosts:
    def test_small_sub_fetched_new_and_top_deduped(self, monkeypatch):
        a, b = _submission("a", "post a"), _submission("b", "post b")
        sub = _fake_sub(83, new_posts=[a, b], top_posts=[b])  # b in both listings
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"CottageFoodBusiness": sub}))
        out = RedditCollectorTool().fetch_small_subreddit_posts(["CottageFoodBusiness"])
        assert [r.title for r in out] == ["post a", "post b"]

    def test_big_sub_skipped(self, monkeypatch):
        sub = _fake_sub(150_000, new_posts=[_submission("a", "post a")])
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"Baking": sub}))
        assert RedditCollectorTool().fetch_small_subreddit_posts(["Baking"]) == []

    def test_already_collected_urls_skipped(self, monkeypatch):
        a = _submission("a", "post a")
        sub = _fake_sub(83, new_posts=[a])
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"s": sub}))
        url = f"https://www.reddit.com{a.permalink}"
        assert RedditCollectorTool().fetch_small_subreddit_posts(
            ["s"], already_collected_urls={url}) == []

    def test_fail_soft_per_sub(self, monkeypatch):
        import prawcore
        ok = _fake_sub(83, new_posts=[_submission("a", "post a")])

        class _Boom:
            display_name = "gone"
            @property
            def subscribers(self):
                raise prawcore.exceptions.PrawcoreException()
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"gone": _Boom(), "ok": ok}))
        out = RedditCollectorTool().fetch_small_subreddit_posts(["gone", "ok"])
        assert [r.title for r in out] == ["post a"]  # broken sub skipped, good one fetched


def _sub_authors(subscribers, posts):
    """posts = [(pid, title, author)]"""
    subs = [SimpleNamespace(permalink=f"/r/s/comments/{pid}/", title=t, selftext="",
                            author=a) for pid, t, a in posts]
    return SimpleNamespace(display_name="s", subscribers=subscribers,
                           new=lambda limit: iter(subs),
                           top=lambda time_filter, limit: iter([]))


class TestVendorPromoDefense:
    """Codex-review finding: tiny on-topic vendor subs (r/InferX pattern) pass the waived
    engagement gate AND relevance grading — one-author dominance is the deterministic tell."""

    def test_dominated_sub_dropped(self, monkeypatch):
        posts = [(f"p{i}", f"Product update {i}", "vendor_guy") for i in range(5)]
        posts += [("p9", "a question", "someone_else")]
        sub = _sub_authors(83, posts)   # 5/6 = 0.83 >= 0.5 share
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"InferX": sub}))
        assert RedditCollectorTool().fetch_small_subreddit_posts(["InferX"]) == []

    def test_balanced_sub_kept(self, monkeypatch):
        posts = [(f"p{i}", f"post {i}", f"user_{i % 4}") for i in range(8)]
        sub = _sub_authors(83, posts)   # max share 2/8 = 0.25
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"ok": sub}))
        out = RedditCollectorTool().fetch_small_subreddit_posts(["ok"])
        assert len(out) == 8

    def test_tiny_batch_kept_regardless(self, monkeypatch):
        posts = [(f"p{i}", f"post {i}", "same_author") for i in range(4)]  # n<6
        sub = _sub_authors(83, posts)
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"tiny": sub}))
        assert len(RedditCollectorTool().fetch_small_subreddit_posts(["tiny"])) == 4

    def test_deleted_authors_do_not_crash_or_trip(self, monkeypatch):
        # author=None (deleted) → bucketed as "[deleted]"; a sub full of deleted authors
        # WILL trip the share check — acceptable (indistinguishable from a promo pattern)
        posts = [(f"p{i}", f"post {i}", None) for i in range(7)]
        sub = _sub_authors(83, posts)
        monkeypatch.setattr(rt, "_get_shared_reddit_client",
                            lambda: _fake_client({"ghost": sub}))
        out = RedditCollectorTool().fetch_small_subreddit_posts(["ghost"])
        assert out == []  # no crash; dominance rule applies
