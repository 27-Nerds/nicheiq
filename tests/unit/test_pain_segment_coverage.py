"""Prompt-assembly / helper tests for the pain + audience crews (no LLM calls): the audience
grounding directive, the context-window-summarization guard, and the low-quality-post filter.
"""
from types import SimpleNamespace

import yaml

import nicheiq.crews.audience_mapping_crew as amc
import nicheiq.crews.pain_point_crew as ppc

SEGMENTS = ["Casual tournament viewers and event-driven fans", "Digital item traders", "Team loyalists"]


# ---- Part D: audience grounding directive ----------------------------------------------------

def _aud_self(segments=SEGMENTS, boundary="esports spectating; excludes casual gaming",
              excl=("CS2 = Cities Skylines II", "skin-gambling as primary focus")):
    s = SimpleNamespace(market_segments=list(segments), industry_boundaries=boundary,
                        disambiguation_exclusions=list(excl))
    s._segment_grounding_directive = amc.AudienceMappingCrew._segment_grounding_directive.__get__(s)
    return s


class TestAudienceGroundingDirective:
    def test_renders_prior_and_boundary_guard(self):
        # always on now (no flag) — renders when Stage-1 segments/boundaries are present
        out = _aud_self()._segment_grounding_directive()
        assert "GROUNDING PRIOR" in out and "Team loyalists" in out
        assert "BOUNDARY GUARD" in out
        assert "Cities Skylines" in out                      # disambiguation exclusion injected
        assert "loneliness" in out                           # generic-persona drop rule

    def test_blank_without_stage1_inputs(self):
        # no segments + no boundary + no exclusions -> nothing to ground -> empty
        assert _aud_self(segments=[], boundary="", excl=())._segment_grounding_directive() == ""

    def test_partial_inputs_degrade_safely(self):
        # no segments, only a boundary -> still renders the boundary guard, no prior
        out = _aud_self(segments=[], excl=())._segment_grounding_directive()
        assert "GROUNDING PRIOR" not in out and "BOUNDARY GUARD" in out

    def test_constructor_accepts_and_stores_new_fields(self):
        crew = amc.AudienceMappingCrew(
            reddit_posts=[], niche_description="x",
            market_segments=SEGMENTS, industry_boundaries="b",
            disambiguation_exclusions=["e"],
        )
        assert crew.market_segments == SEGMENTS
        assert crew.industry_boundaries == "b"
        assert crew.disambiguation_exclusions == ["e"]

    def test_yaml_exposes_token(self):
        cfg = yaml.safe_load(open("src/nicheiq/crews/config/audience_mapping_tasks.yaml"))
        desc = next(iter(cfg.values()))["description"]
        assert "{segment_grounding}" in desc


class TestPainSegmentMatching:
    """Stage-4 affected_segments enrichment: richer vocab + light-stem recover real matches the
    old exact-token matcher dropped, while a no-overlap pain still stays null (no wrong home).
    """

    from nicheiq.utils.segment_matching import match_pain_to_segments
    _match = staticmethod(match_pain_to_segments)

    @staticmethod
    def _seg(name, alignment=(), motivation=()):
        return SimpleNamespace(segment_name=name, pain_point_alignment=list(alignment),
                               motivation_drivers=list(motivation))

    @staticmethod
    def _pain(title, categories=(), description=""):
        return SimpleNamespace(title=title, categories=list(categories), description=description)

    _SEGS = [
        _seg.__func__("Digital Asset Investors",
                      ["Market volatility and sudden asset devaluation"],
                      ["Maximizing ROI on digital inventory"]),
        _seg.__func__("Competitive Esports Enthusiasts",
                      ["Frustration with cheaters impacting game integrity"],
                      ["Deep-diving into match stats and player performance"]),
        _seg.__func__("Casual Community Builders",
                      ["High logistical burden of hosting local events"],
                      ["Fostering local gaming culture"]),
    ]

    def test_stem_bridges_anticheat_to_cheaters(self):
        # "anti-cheat" (hyphen-split) + "cheaters" (stem) both -> "cheat"; old exact match missed this
        p = self._pain("VAC anti-cheat failures ruin competitive matches",
                       ["Anti-Cheat and Matchmaking"])
        assert "Competitive Esports Enthusiasts" in self._match(p, self._SEGS)

    def test_motivation_drivers_count_as_signal(self):
        # "performance" lives only in motivation_drivers, which the old matcher ignored
        p = self._pain("HLTV rating opacity frustrates player performance analysis",
                       ["Performance Metrics"])
        assert "Competitive Esports Enthusiasts" in self._match(p, self._SEGS)

    def test_no_overlap_stays_null(self):
        # harassment/gender vocab matches none of the finance/esports/community segments
        p = self._pain("Female players cannot speak in voice chat without harassment",
                       ["Toxicity and Moderation"])
        assert self._match(p, self._SEGS) == []

    def test_caps_at_two_segments(self):
        p = self._pain("asset market cheaters performance local events ROI inventory devaluation",
                       ["Market", "Anti-Cheat", "Events"])
        assert len(self._match(p, self._SEGS)) <= 2

    def test_no_segments_returns_empty(self):
        assert self._match(self._pain("anything"), []) == []


class TestContextWindowFix:
    """Regression: high-content agents must NOT let CrewAI auto-summarize the corpus.

    CrewAI's OpenAICompletion hardcodes an OpenAI-only context-window table and mis-detects every
    OpenRouter model as ~7K tokens; with respect_context_window=True it would summarize our budgeted
    400K corpus down to a lossy, majority-biased ~7K digest BEFORE the agent ever reads it (dropping
    the quiet fan/spectator minority). We own the corpus budgeting, so these agents must keep
    respect_context_window=False.
    """

    def test_pain_corpus_agents_disable_summarization(self):
        crew = ppc.PainPointCrew(reddit_posts=[], niche_description="x", market_segments=["a"])
        for name in ("content_researcher", "pain_point_analyst", "pain_point_validator"):
            assert getattr(crew, name)().respect_context_window is False, name

    def test_audience_agent_disables_summarization(self):
        crew = amc.AudienceMappingCrew(reddit_posts=[], niche_description="x")
        assert crew.audience_researcher().respect_context_window is False


class TestLowQualityFilterKeepsDiscussionRichPosts:
    """Regression: a short/empty-selftext post with REAL comment discussion must be KEPT.

    Fan/spectator/collector pains are disproportionately link/question posts (empty selftext, all
    the substance in the comments — e.g. "does anyone care about stickers?" + 31 comments). The old
    selftext<50 rule deleted them whole and biased the corpus toward long player-rant posts. We now
    drop a short-selftext post only when its comment discussion is ALSO thin.
    """

    @staticmethod
    def _post(pid, selftext, comment_bodies):
        from datetime import datetime, timezone
        from nicheiq.models.social_content import RedditComment, RedditPost
        now = datetime.now(timezone.utc)
        return RedditPost(
            post_id=pid, title=f"title {pid}", selftext=selftext, author="u", subreddit="r",
            score=10, num_comments=len(comment_bodies), created_utc=now,
            url=f"https://reddit.com/r/r/comments/{pid}/",
            comments=[RedditComment(comment_id=f"{pid}c{i}", author="a", body=b, score=2,
                                    created_utc=now) for i, b in enumerate(comment_bodies)],
        )

    def _run(self, posts):
        crew = ppc.PainPointCrew.__new__(ppc.PainPointCrew)
        kept = ppc.PainPointCrew._filter_low_quality_reddit(crew, posts)
        return {p.post_id for p in kept}

    def test_empty_selftext_rich_comments_is_kept(self):
        # link/question post: empty selftext, but a real discussion (the fan-pain shape)
        p = self._post("rich", "", ["x" * 120, "y" * 130, "z" * 90])  # ~340 chars, avg >30
        assert "rich" in self._run([p])

    def test_empty_selftext_thin_comments_is_dropped(self):
        # genuine meme/link with no substance: empty selftext + trivial comments
        p = self._post("thin", "", ["lol", "nice"])  # ~7 chars total
        assert "thin" not in self._run([p])

    def test_long_selftext_still_kept(self):
        p = self._post("essay", "x" * 400, ["a" * 50])
        assert "essay" in self._run([p])
