"""Tests for the run-level idea-portfolio summary: the deterministic digest builder
(no LLM/IO) and the name-coverage guardrail around the single grounded LLM call.
"""

from types import SimpleNamespace

from nicheiq.utils.idea_portfolio_summary import (
    build_idea_portfolio_digest,
    generate_idea_portfolio_summary,
)


def _idea(name, *, status="active", source_frame=None, market_fit=0.6, market_fit_raw=None,
          risk_flags=None, pricing_shape_note=None):
    return SimpleNamespace(
        solution_name=name,
        candidate_status=status,
        source_frame=source_frame,
        market_fit_score=market_fit,
        market_fit_score_raw=market_fit_raw,
        seo_scalability_score=0.5,
        source_segment_payability=0.4,
        source_segment_payability_class="mixed",
        incumbent_parity=None,
        adjacent_market_parity=None,
        estimated_development_time="6-10 weeks",
        tags=SimpleNamespace(
            risk_flags=risk_flags or [], pricing_shape_note=pricing_shape_note
        ),
    )


class TestDigestBuilder:
    def test_includes_only_visible_ideas(self):
        ideas = [
            _idea("VisibleOne"),
            _idea("DemotedOne", status="demoted"),
            _idea("AbsorbedOne", status="absorbed"),
        ]
        digest = build_idea_portfolio_digest(ideas)
        assert "VisibleOne" in digest
        assert "DemotedOne" not in digest
        assert "AbsorbedOne" not in digest

    def test_excludes_source_frame(self):
        idea = _idea("Solo", source_frame="UNIQUE_FRAME_MARKER_XYZ")
        digest = build_idea_portfolio_digest([idea])
        assert "UNIQUE_FRAME_MARKER_XYZ" not in digest

    def test_includes_ruled_out_names_and_reasons(self):
        digest = build_idea_portfolio_digest(
            [_idea("Survivor")],
            ruled_out=[{"idea_name": "RuledOutIdea", "reason": "thin wallet"}],
        )
        assert "RuledOutIdea" in digest
        assert "thin wallet" in digest

    def test_self_score_correction_noted(self):
        idea = _idea("CorrectedIdea", market_fit=0.4, market_fit_raw=0.6)
        digest = build_idea_portfolio_digest([idea])
        assert "self-score corrected down" in digest

    def test_no_correction_note_under_threshold(self):
        idea = _idea("StableIdea", market_fit=0.5, market_fit_raw=0.55)
        digest = build_idea_portfolio_digest([idea])
        assert "self-score corrected down" not in digest

    def test_no_decimal_scores_leak(self):
        idea = _idea("BandedIdea", market_fit=0.6)
        digest = build_idea_portfolio_digest([idea])
        assert "0.6" not in digest

    def test_empty_visible_pool_returns_empty_string(self):
        assert build_idea_portfolio_digest([_idea("Gone", status="demoted")]) == ""

    def test_funnel_counts_and_wallet_included(self):
        digest = build_idea_portfolio_digest(
            [_idea("Solo")],
            funnel_counts={"winners": 3, "demoted": 1},
            niche_wallet_brief={"wallet_class": "mixed", "evidence": "priced tools exist"},
        )
        assert "winners=3" in digest
        assert "mixed" in digest
        assert "priced tools exist" in digest


class TestGenerateSummary:
    def test_empty_pool_skips_llm(self, monkeypatch):
        from nicheiq.utils import llm_service

        called = False

        def _boom(**kw):
            nonlocal called
            called = True
            raise AssertionError("should not be called")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))
        summary, usage = generate_idea_portfolio_summary([_idea("X", status="demoted")])
        assert summary is None and usage is None and called is False

    def test_success_on_first_attempt(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        text = "AlphaTool and BetaTracker both show moderate market fit. Validate AlphaTool first."
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (SimpleNamespace(summary=text), SimpleNamespace(to_dict=lambda: {}))),
        )
        summary, usage = generate_idea_portfolio_summary(ideas)
        assert summary == text
        assert usage is not None

    def test_missing_name_retries_then_succeeds(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        calls = []

        def _fake(**kw):
            calls.append(kw["prompt"])
            if len(calls) == 1:
                return SimpleNamespace(summary="Only AlphaTool is discussed here."), None
            return SimpleNamespace(
                summary="AlphaTool and BetaTracker are both covered in this rewrite."
            ), None

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_fake))
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert len(calls) == 2
        assert "DID NOT MENTION" not in calls[0]  # first prompt is the base prompt
        assert "DID NOT MENTION" in calls[1]
        assert "BetaTracker" in calls[1]  # the reminder names the missing idea
        assert summary is not None
        assert "AlphaTool" in summary and "BetaTracker" in summary

    def test_missing_name_after_retry_gives_up(self, monkeypatch):
        from nicheiq.utils import llm_service

        ideas = [_idea("AlphaTool"), _idea("BetaTracker")]
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (SimpleNamespace(summary="Only AlphaTool is discussed here."), None)),
        )
        summary, _ = generate_idea_portfolio_summary(ideas)
        assert summary is None

    def test_fail_soft_on_exception(self, monkeypatch):
        from nicheiq.utils import llm_service

        def _boom(**kw):
            raise RuntimeError("no live llm in tests")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))
        ideas = [_idea("AlphaTool")]
        summary, usage = generate_idea_portfolio_summary(ideas)
        assert summary is None and usage is None
