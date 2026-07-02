"""Subreddit discovery (2026-07-02) — find REAL subs by keyword instead of trusting LLM recall.

queries_from_anchor_names: any-platform anchor names → short search queries (a hallucinated name is
still a good query). discover_subreddits: PRAW subreddits.search → filter (public/restricted, sfw,
low subscriber floor) → stemmed token-overlap ranking (kills same-word noise like No Man's Sky).
"""

from types import SimpleNamespace

from nicheiq.tools.reddit_tool import RedditCollectorTool


class TestQueriesFromAnchorNames:
    def test_all_observed_anchor_shapes(self):
        anchors = [
            "r/CottageFood (Reddit)",                                   # hallucinated — still a good query
            "Cottage Food Business Owners (Facebook Group)",
            "Cottage Food Laws (CottageFoodLaws.com) Facebook Group",
            "Piano World Forums – Piano Teachers Forum",
            "MTNA (Music Teachers National Association) – MTNA Connect community",
        ]
        qs = RedditCollectorTool.queries_from_anchor_names(anchors)
        assert qs[0] == "cottage food"                       # de-camel-cased r/Name
        assert "cottage food business" in qs                 # platform words stripped, <=3 words
        assert all(len(q.split()) <= 3 for q in qs)
        assert not any(w in q for q in qs for w in ("facebook", "reddit", "forum"))

    def test_dedupe_and_cap(self):
        anchors = ["r/CottageFood", "Cottage Food (Facebook Group)"] + [f"Club {i} Community" for i in range(9)]
        qs = RedditCollectorTool.queries_from_anchor_names(anchors, max_queries=4)
        assert qs.count("cottage food") == 1 and len(qs) <= 4

    def test_empty_and_junk_safe(self):
        assert RedditCollectorTool.queries_from_anchor_names([]) == []
        assert RedditCollectorTool.queries_from_anchor_names([None, "", "()"]) == []


def _fake_sub(name, subs, title="", desc="", sub_type="public", over18=False):
    return SimpleNamespace(display_name=name, subscribers=subs, title=title,
                           public_description=desc, subreddit_type=sub_type, over18=over18)


class TestDiscoverSubreddits:
    def _tool_with(self, monkeypatch, results_by_query):
        import nicheiq.tools.reddit_tool as rt
        fake = SimpleNamespace(subreddits=SimpleNamespace(
            search=lambda q, limit=8: iter(results_by_query.get(q, []))))
        monkeypatch.setattr(rt, "_get_shared_reddit_client", lambda: fake)
        return RedditCollectorTool()

    def test_ranks_dedicated_sub_over_generic_and_kills_noise(self, monkeypatch):
        niche = "home bakers selling cakes and cookies from home under cottage food laws"
        tool = self._tool_with(monkeypatch, {"cottage food": [
            _fake_sub("CottageFoodBusiness", 83, "CottageFoodBusiness",
                      "Selling home baked goods under cottage food laws"),
            _fake_sub("FoodPorn", 8_600_000, "FoodPorn", "pictures of delicious food"),
            _fake_sub("NoMansSkyTheGame", 1_100_000, "No Man's Sky", "a game about space"),
        ]})
        out = tool.discover_subreddits(["cottage food"], niche)
        names = [c["name"] for c in out]
        assert names[0] == "CottageFoodBusiness"      # overlap score dominates subscriber count
        assert "NoMansSkyTheGame" not in names        # <2 token overlap → dropped

    def test_filters_private_nsfw_and_tiny(self, monkeypatch):
        niche = "cottage food home bakers selling cakes"
        tool = self._tool_with(monkeypatch, {"cottage food": [
            _fake_sub("bakersPrivate", 5000, "cottage food bakers", sub_type="private"),
            _fake_sub("bakersNsfw", 5000, "cottage food bakers cakes", over18=True),
            _fake_sub("bakersTiny", 3, "cottage food bakers cakes"),
            _fake_sub("cottagefoodoperators", 43, "cottage food operators selling home baked cakes",
                      sub_type="restricted"),
        ]})
        out = tool.discover_subreddits(["cottage food"], niche)
        assert [c["name"] for c in out] == ["cottagefoodoperators"]  # restricted kept, rest dropped

    def test_fail_soft_on_search_error(self, monkeypatch):
        import nicheiq.tools.reddit_tool as rt
        def _boom(q, limit=8):
            raise RuntimeError("api down")
        fake = SimpleNamespace(subreddits=SimpleNamespace(search=_boom))
        monkeypatch.setattr(rt, "_get_shared_reddit_client", lambda: fake)
        assert RedditCollectorTool().discover_subreddits(["x y"], "niche text") == []


class TestStage1Wiring:
    def test_discovered_subs_appended_to_anchor_communities(self, monkeypatch):
        from nicheiq.flows.research_flow import ResearchFlow
        ctx = SimpleNamespace(
            niche_description="home bakers selling under cottage food laws",
            user_target_audience="home bakers",
            community_search_terms=["cottage food"],
            anchor_communities=["r/CottageFood (Reddit)"],
        )
        import nicheiq.flows.research_flow as rf
        monkeypatch.setattr(
            rf.settings, "enable_reddit", True)
        from nicheiq.tools.reddit_tool import RedditCollectorTool as RT
        monkeypatch.setattr(RT, "discover_subreddits",
                            lambda self, queries, niche_text, **kw: [
                                {"name": "CottageFoodBusiness", "subscribers": 83, "score": 4, "title": ""}])
        stub = SimpleNamespace()
        stub._discover_anchor_subreddits = ResearchFlow._discover_anchor_subreddits.__get__(stub)
        stub._discover_anchor_subreddits(ctx)
        assert "r/CottageFoodBusiness (Reddit, discovered)" in ctx.anchor_communities
