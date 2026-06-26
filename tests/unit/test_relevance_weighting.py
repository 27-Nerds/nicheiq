"""Relevance-weighted post filtering: relevance-scaled engagement gate + token-budget priority."""
from datetime import datetime, timezone
from types import SimpleNamespace

from nicheiq.config.settings import settings
from nicheiq.models.social_content import RedditComment, RedditPost
from nicheiq.tools.reddit_tool import RedditCollectorTool
from nicheiq.utils.token_monitor import ContentTokenMonitor


def _post(score, ncom, selftext=""):
    # selftext defaults to "" so the engagement-gate tests below exercise the comment path
    # (an empty selftext is never an "article"). Pass a long selftext to hit the article waiver.
    return SimpleNamespace(score=score, num_comments=ncom, selftext=selftext)


class TestRelevanceScaledGate:
    def setup_method(self):
        self.tool = RedditCollectorTool()

    def test_high_grade_passes_low_engagement(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_engagement_discount", 0.8)
        monkeypatch.setattr(settings, "relevance_engagement_comment_floor", 1)
        monkeypatch.setattr(settings, "min_reddit_upvotes", 10)
        monkeypatch.setattr(settings, "min_reddit_comments", 5)
        assert self.tool._passes_quality(_post(2, 1), 3) is True    # grade-3 ~= 2 upvotes / 1 comment
        assert self.tool._passes_quality(_post(2, 1), 1) is False   # grade-1 = full 10 / 5

    def test_comment_floor_enforced(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_engagement_discount", 0.8)
        monkeypatch.setattr(settings, "relevance_engagement_comment_floor", 1)
        monkeypatch.setattr(settings, "min_reddit_upvotes", 10)
        monkeypatch.setattr(settings, "min_reddit_comments", 5)
        assert self.tool._passes_quality(_post(50, 0), 3) is False  # 0 comments < floor, no matter how relevant

    def test_none_grade_uses_base_thresholds(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_engagement_discount", 0.8)
        monkeypatch.setattr(settings, "min_reddit_upvotes", 10)
        monkeypatch.setattr(settings, "min_reddit_comments", 5)
        assert self.tool._passes_quality(_post(9, 4), None) is False
        assert self.tool._passes_quality(_post(10, 5), None) is True

    def test_discount_zero_disables_scaling(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_engagement_discount", 0.0)
        monkeypatch.setattr(settings, "min_reddit_upvotes", 10)
        monkeypatch.setattr(settings, "min_reddit_comments", 5)
        assert self.tool._passes_quality(_post(2, 1), 3) is False   # disabled -> base 10/5 even at grade 3


class TestArticleWaiver:
    """A self-contained article/guide (long selftext) is kept WITHOUT comments, provided it still
    clears the upvote bar. A 0-comment link post (no selftext) is still dropped."""

    def setup_method(self):
        self.tool = RedditCollectorTool()

    def _cfg(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_engagement_discount", 0.8)
        monkeypatch.setattr(settings, "relevance_engagement_comment_floor", 1)
        monkeypatch.setattr(settings, "min_reddit_upvotes", 10)
        monkeypatch.setattr(settings, "min_reddit_comments", 5)
        monkeypatch.setattr(settings, "reddit_article_min_chars", 500)

    def test_article_zero_comments_kept(self, monkeypatch):
        self._cfg(monkeypatch)
        # the reported case: score 21, 0 comments, grade 3, long how-to selftext
        assert self.tool._passes_quality(_post(21, 0, "x" * 800), 3) is True

    def test_link_post_zero_comments_still_dropped(self, monkeypatch):
        self._cfg(monkeypatch)
        assert self.tool._passes_quality(_post(21, 0, ""), 3) is False        # no text + no comments
        assert self.tool._passes_quality(_post(21, 0, "short note"), 3) is False  # too-short selftext

    def test_article_still_needs_upvotes(self, monkeypatch):
        self._cfg(monkeypatch)
        # grade-1 (no discount) -> full 10-upvote bar; a long article below it is still dropped
        assert self.tool._passes_quality(_post(3, 0, "x" * 800), 1) is False
        assert self.tool._passes_quality(_post(10, 0, "x" * 800), 1) is True

    def test_short_selftext_with_discussion_still_passes(self, monkeypatch):
        self._cfg(monkeypatch)
        # non-article path unchanged: short selftext but enough comments at high grade
        assert self.tool._passes_quality(_post(5, 2, "short"), 3) is True


class TestRelevancePriority:
    def _p(self, grade):
        return SimpleNamespace(comments=[SimpleNamespace(body="x" * 200)] * 5, score=20,
                               selftext="y" * 500, created_utc=datetime.now(timezone.utc),
                               relevance_grade=grade)

    def test_priority_increases_with_grade(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_priority_weight", 0.5)
        s = {g: ContentTokenMonitor.pain_point_priority_score(self._p(g)) for g in (1, 2, 3)}
        assert s[1] < s[2] < s[3]

    def test_none_grade_keeps_full_weight(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_priority_weight", 0.5)
        assert ContentTokenMonitor.pain_point_priority_score(self._p(None)) == \
               ContentTokenMonitor.pain_point_priority_score(self._p(3))

    def test_weight_zero_disables(self, monkeypatch):
        monkeypatch.setattr(settings, "relevance_priority_weight", 0.0)
        assert ContentTokenMonitor.pain_point_priority_score(self._p(1)) == \
               ContentTokenMonitor.pain_point_priority_score(self._p(3))


def _reddit_post(pid, grade, n_comments=5, score=20):
    """Real RedditPost for the token-budget cap (which counts tokens via tiktoken)."""
    now = datetime.now(timezone.utc)
    return RedditPost(
        post_id=pid, title="t", selftext="x" * 300, author=f"u{pid}", subreddit="r",
        score=score, num_comments=n_comments, created_utc=now,
        url=f"https://reddit.com/r/r/comments/{pid}/",
        comments=[RedditComment(comment_id=f"{pid}c{i}", author="a", body="y" * 150, score=3,
                                created_utc=now) for i in range(n_comments)],
        relevance_grade=grade,
    )


class TestRelevanceBudgetAllocation:
    """When the pain-finder token budget forces drops, relevance-weighting should keep a
    higher mean grade — without letting relevance override a genuinely rich discussion."""

    def _cap(self, posts, max_tokens):
        tm = ContentTokenMonitor()
        return tm.filter_posts_to_token_budget(
            posts, max_tokens, score_fn=ContentTokenMonitor.pain_point_priority_score)

    def test_over_budget_keeps_more_relevant(self, monkeypatch):
        # 6 posts identical in engagement/richness; grades interleaved so input order != grade order.
        posts = [_reddit_post(f"p{i}", g) for i, g in enumerate([1, 1, 2, 2, 3, 3])]
        per = ContentTokenMonitor().count_post_tokens(posts[0])
        max_tokens = per * 3 + 1  # budget fits exactly 3

        monkeypatch.setattr(settings, "relevance_priority_weight", 0.0)  # OLD behavior
        old = self._cap(posts, max_tokens)
        monkeypatch.setattr(settings, "relevance_priority_weight", 0.5)  # NEW behavior
        new = self._cap(posts, max_tokens)

        assert len(old) == len(new) == 3
        old_mean = sum(p.relevance_grade for p in old) / 3
        new_mean = sum(p.relevance_grade for p in new) / 3
        assert new_mean > old_mean  # the budget is now spent on the most-relevant posts

    def test_rich_low_grade_post_is_protected(self, monkeypatch):
        # A grade-1 post with a rich discussion must beat grade-3 thin posts (richness still 40%).
        rich_low = _reddit_post("rich", grade=1, n_comments=40, score=200)
        thin_high = [_reddit_post(f"thin{i}", grade=3, n_comments=2, score=5) for i in range(5)]
        posts = thin_high + [rich_low]
        max_tokens = ContentTokenMonitor().count_post_tokens(rich_low) + 5  # ~1 post fits

        monkeypatch.setattr(settings, "relevance_priority_weight", 0.5)
        kept = self._cap(posts, max_tokens)
        assert any(p.post_id == "rich" for p in kept)  # relevance is a tilt, not a takeover
