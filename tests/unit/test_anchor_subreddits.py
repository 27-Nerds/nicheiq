"""Item 1 (2026-07-02 plan) — anchor-subreddit targeting: parse Stage-1 anchor_communities into
subreddit names, pre-validate, and prepend into the PRAW native-search sub list (dark flag)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from nicheiq.tools.reddit_tool import RedditCollectorTool


class TestExtractSubredditsFromAnchors:
    def test_parses_all_observed_anchor_forms(self):
        anchors = [
            "Forrager — Cottage Food Laws by State (forrager.com)",     # non-Reddit → ignored
            "Reddit: r/CottageFood",                                     # prefixed
            "r/cottagebakery",                                           # bare
            "https://www.reddit.com/r/Baking/",                          # full URL
            "Facebook group: “Cottage Food Laws”",                       # non-Reddit → ignored
            "CakeCentral.com Forums (home bakery business discussions)", # non-Reddit → ignored
        ]
        assert RedditCollectorTool.extract_subreddits_from_anchors(anchors) == [
            "CottageFood", "cottagebakery", "Baking"]

    def test_case_insensitive_dedupe_preserves_order(self):
        anchors = ["r/CottageFood", "Reddit: r/cottagefood", "r/Baking"]
        assert RedditCollectorTool.extract_subreddits_from_anchors(anchors) == ["CottageFood", "Baking"]

    def test_empty_and_none_safe(self):
        assert RedditCollectorTool.extract_subreddits_from_anchors([]) == []
        assert RedditCollectorTool.extract_subreddits_from_anchors([None, "", "just words"]) == []


class TestValidateSubreddits:
    def test_drops_unresolvable_keeps_valid(self, monkeypatch):
        import nicheiq.tools.reddit_tool as rt

        def _sub(name):
            m = MagicMock()
            if name == "NotARealSub12345":
                type(m).id = property(lambda self: (_ for _ in ()).throw(Exception("404")))
            else:
                m.id = "abc"
            return m

        fake_reddit = SimpleNamespace(subreddit=_sub)
        monkeypatch.setattr(rt, "_get_shared_reddit_client", lambda: fake_reddit)
        tool = RedditCollectorTool()
        assert tool.validate_subreddits(["CottageFood", "NotARealSub12345", "Baking"]) == [
            "CottageFood", "Baking"]
