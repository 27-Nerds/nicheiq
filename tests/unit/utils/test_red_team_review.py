"""Tests for the adversarial red-team pass (utils/red_team_review.py): killed- AND weakened-
verdict no-op on scores and on the parity channel, per-idea fail-soft on an LLM exception,
the red_team_top_k=0 no-op short-circuit (no LLM call, no searches), and the accept-guarded
revision tail (`_attempt_red_team_revision`) with its funnel counters.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.solution_idea import RedTeamFinding
from nicheiq.utils import llm_service
from nicheiq.utils.idea_portfolio_summary import _idea_digest_line
from nicheiq.utils.red_team_review import _RedTeamVerdict, run_red_team_review


def _verdict(verdict, claim=None, kind="evidence_gap"):
    findings = [RedTeamFinding(kind=kind, claim=claim)] if claim else []
    return _RedTeamVerdict(verdict=verdict, findings=findings, uplift=None)


def _crew(search_map=None):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.niche_context = SimpleNamespace(niche_description="cottage food")
    crew._ma_search_batch = MagicMock(return_value=search_map or {})
    crew.funnel_counts = {}
    crew._score_wave = MagicMock()
    # Reuse the REAL keyword-derivation + caps logic (no parallel mechanism under test).
    crew._mechanism_keywords = UnifiedSolutionCrew._mechanism_keywords
    crew._validate_idea_caps = UnifiedSolutionCrew._validate_idea_caps.__get__(crew)
    return crew


def _score_wave_stub(**scores):
    """Stamps the four gauntlet score fields + incumbent_parity on every idea in the wave,
    simulating `_score_wave`'s effect on a revision candidate."""
    defaults = dict(market_fit_score=0.9, technical_feasibility_score=0.9,
                     novelty_score=0.8, seo_scalability_score=0.8,
                     incumbent_parity="none found")
    defaults.update(scores)

    def stub(wave, **kw):
        for i in wave:
            for k, v in defaults.items():
                setattr(i, k, v)
    return stub


def _dispatch(verdict, revision_dump=None):
    """LLM mock that branches on which call it is: the revision ideator prompt always
    contains 'ESCAPE'; anything else is the red-team verdict call."""
    dump = revision_dump or {"solution_name": "Revised Idea",
                              "value_proposition": "A revised value prop"}

    def _invoke(**kw):
        prompt = kw.get("prompt", "")
        if "ESCAPE" in prompt:
            return SimpleNamespace(model_dump=lambda: dict(dump)), SimpleNamespace(to_dict=lambda: {})
        return verdict, SimpleNamespace(to_dict=lambda: {})
    return _invoke


def _dispatch_multi(verdicts_by_name, revision_dump=None):
    """Like `_dispatch`, but resolves the verdict call by idea name for multi-idea batches."""
    dump = revision_dump or {"solution_name": "Revised Idea",
                              "value_proposition": "A revised value prop"}

    def _invoke(**kw):
        prompt = kw.get("prompt", "")
        if "ESCAPE" in prompt:
            return SimpleNamespace(model_dump=lambda: dict(dump)), SimpleNamespace(to_dict=lambda: {})
        for name, verdict in verdicts_by_name.items():
            if f"- name: {name}\n" in prompt:
                return verdict, SimpleNamespace(to_dict=lambda: {})
        raise AssertionError(f"no matching verdict for prompt: {prompt[:200]}")
    return _invoke


def _idea(name="Idea", mf=0.8, incumbent_parity=None, **kw):
    base = dict(
        solution_name=name, market_fit_score=mf, incumbent_parity=incumbent_parity,
        value_proposition="Automates pricing for cottage-food bakers",
        technical_approach="scrapes recipe cost data",
        mechanism_tag="pricing-calc", candidate_status="active",
        red_team_verdict=None, red_team_caveats=None,
        source_segment_payability=None, source_segment_payability_class=None,
        data_access_model=None, build_feasibility_score=0.8,
        novelty_score=None, obviousness_score=None, solo_dev_feasibility=None,
        technical_feasibility_score=0.6, seo_scalability_score=None, winning_angle=None,
        source_pain=None, source_segment=None, pain_points_addressed=None, target_personas=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _refined(ideas):
    return SimpleNamespace(solution_ideas=ideas)


class TestRedTeamReview:
    def test_killed_verdict_never_writes_the_parity_channel(self, monkeypatch):
        """A 'killed' verdict stamps verdict + caveats and NOTHING else.

        This test previously asserted the opposite (the killing caveat became
        `incumbent_parity = "bundled_free (red-team): ..."` and `_validate_idea_caps`
        capped market_fit to 0.40). That coupling was deleted 2026-08-02: `_RedTeamVerdict`
        carries no vendor field, so every such stamp was a vendor-less parity claim by
        construction, and the sibling probe `_probe_mechanism_parity` already requires a
        named vendor before any parity class is assigned. The kill's consequence now lives
        only where it can be attributed — the verdict floor (`apply_red_team_downgrade`)
        and the auto-pick guard (`score_helpers.choose_auto_pick`).
        """
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        monkeypatch.setattr(settings, "parity_bundled_free_cap", 0.40)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        idea = _idea(mf=0.8)
        verdict = _verdict(
            "killed", "free in Truckstop broker portal",
            "verified_free_or_bundled_alternative")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (verdict, SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        assert idea.red_team_verdict == "killed"
        assert idea.red_team_caveats == ["free in Truckstop broker portal"]
        assert idea.incumbent_parity is None
        assert idea.market_fit_score == 0.8

    def test_weakened_verdict_leaves_scores_untouched(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        idea = _idea(mf=0.8)
        verdict = _verdict("weakened", "minor category overlap noted")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (verdict, SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        assert idea.red_team_verdict == "weakened"
        assert idea.red_team_caveats == ["minor category overlap noted"]
        assert idea.incumbent_parity is None
        assert idea.market_fit_score == 0.8

    def test_gap_only_requested_kill_is_stamped_weakened_with_legacy_claims(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        idea = _idea(mf=0.8)
        verdict = _verdict(
            "killed", "No free tool appeared in the results", "evidence_gap")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (verdict, SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        assert idea.red_team_verdict == "weakened"
        assert idea.red_team_caveats == ["No free tool appeared in the results"]
        assert idea.red_team_findings == verdict.findings
        crew._score_wave.assert_not_called()

    def test_llm_exception_is_fail_soft(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        idea = _idea(mf=0.8)

        def _boom(**kw):
            raise RuntimeError("no live llm in tests")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))

        run_red_team_review(crew, _refined([idea]))  # must not raise

        assert idea.red_team_verdict is None
        assert idea.red_team_caveats is None
        assert idea.market_fit_score == 0.8

    def test_empty_evidence_abstains_no_llm_no_verdict(self, monkeypatch):
        # Live-caught 2026-07-10: drained search budget -> zero evidence -> the pass still
        # issued "weakened" and the analyst summary spun the empty search into "a gap".
        # No evidence => ABSTAIN: no LLM call, no verdict stamped, no revision attempt.
        monkeypatch.setattr(settings, "red_team_top_k", 2)
        crew = _crew(search_map={"q": ""})  # every query resolved empty
        llm_mock = MagicMock()
        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", llm_mock)
        idea = _idea()
        run_red_team_review(crew, SimpleNamespace(solution_ideas=[idea]))
        llm_mock.assert_not_called()
        assert getattr(idea, "red_team_verdict", None) is None
        assert crew.funnel_counts.get("red_team_reviewed", 0) == 0

    def test_search_called_budget_exempt(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        crew = _crew(search_map={"q": "some evidence"})
        _dispatch_ok = _dispatch("survives")
        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", _dispatch_ok)
        run_red_team_review(crew, SimpleNamespace(solution_ideas=[_idea()]))
        assert crew._ma_search_batch.call_args.kwargs.get("budget_exempt") is True

    def test_top_k_zero_skips_everything(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 0)
        crew = _crew()
        idea = _idea(mf=0.8)
        llm_mock = MagicMock()
        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", llm_mock)

        run_red_team_review(crew, _refined([idea]))

        llm_mock.assert_not_called()
        crew._ma_search_batch.assert_not_called()
        assert idea.red_team_verdict is None


class TestRedTeamRevision:
    def test_revision_accepted_when_composite_beats_original(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        monkeypatch.setattr(settings, "parity_bundled_free_cap", 0.40)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        crew._score_wave.side_effect = _score_wave_stub()
        idea = _idea(mf=0.8)
        verdict = _verdict(
            "killed", "free in Truckstop portal",
            "verified_free_or_bundled_alternative")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(_dispatch(verdict, {"solution_name": "Revised Idea",
                                              "value_proposition": "A revised value prop"})))

        refined = _refined([idea])
        run_red_team_review(crew, refined)

        winner = refined.solution_ideas[0]
        assert winner.red_team_revised is True
        assert winner.solution_name == "Revised Idea"
        assert winner.value_proposition == "A revised value prop"
        assert crew.funnel_counts["red_team_revision_accepted"] == 1
        assert crew.funnel_counts["red_team_revised"] == 1
        assert crew.funnel_counts["red_team_reviewed"] == 1
        assert "revised after red-team review" in _idea_digest_line(winner)

    @pytest.mark.parametrize("score_overrides", [
        # (a) revision's composite is lower than the (capped) original's.
        dict(market_fit_score=0.2, technical_feasibility_score=0.2,
             novelty_score=0.1, seo_scalability_score=0.1, incumbent_parity="none found"),
        # (b) revision's own parity re-probe re-fires (not cleared to "none").
        dict(market_fit_score=0.9, technical_feasibility_score=0.9,
             novelty_score=0.8, seo_scalability_score=0.8,
             incumbent_parity="bundled_free (Etsy): ships templates for pricing"),
    ])
    def test_revision_rejected_composite_or_cap_refire(self, monkeypatch, score_overrides):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        monkeypatch.setattr(settings, "parity_bundled_free_cap", 0.40)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        crew._score_wave.side_effect = _score_wave_stub(**score_overrides)
        idea = _idea(mf=0.8)
        verdict = _verdict(
            "killed", "free in Truckstop portal",
            "verified_free_or_bundled_alternative")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(_dispatch(verdict, {"solution_name": "Revised Idea",
                                              "value_proposition": "A revised value prop"})))

        refined = _refined([idea])
        run_red_team_review(crew, refined)

        assert refined.solution_ideas[0] is idea
        assert idea.red_team_verdict == "killed"
        assert idea.red_team_caveats == ["free in Truckstop portal"]
        assert crew.funnel_counts["red_team_revised"] == 1
        assert crew.funnel_counts["red_team_revision_accepted"] == 0

    def test_survives_verdict_attempts_no_revision(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        idea = _idea(mf=0.8)
        verdict = _verdict("survives")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (verdict, SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        crew._score_wave.assert_not_called()
        assert crew.funnel_counts["red_team_revised"] == 0
        assert crew.funnel_counts["red_team_reviewed"] == 1

    def test_weakened_non_actionable_caveat_no_revision(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        idea = _idea(mf=0.8)
        verdict = _verdict("weakened", "minor category overlap noted")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (verdict, SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        crew._score_wave.assert_not_called()
        assert crew.funnel_counts["red_team_revised"] == 0
        assert crew.funnel_counts["red_team_reviewed"] == 1

    def test_funnel_counters_across_mixed_batch(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 2)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        monkeypatch.setattr(settings, "parity_bundled_free_cap", 0.40)
        crew = _crew(search_map={"pricing calc alternative": "some result"})
        crew._score_wave.side_effect = _score_wave_stub()
        idea_a = _idea(name="IdeaA", mf=0.9)
        idea_b = _idea(name="IdeaB", mf=0.8)
        verdicts = {
            "IdeaA": _verdict(
                "killed", "free in Truckstop portal",
                "verified_free_or_bundled_alternative"),
            "IdeaB": _verdict("survives"),
        }
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(_dispatch_multi(verdicts, {"solution_name": "Revised IdeaA",
                                                      "value_proposition": "revised value"})))

        refined = _refined([idea_a, idea_b])
        run_red_team_review(crew, refined)

        assert crew.funnel_counts["red_team_reviewed"] == 2
        assert crew.funnel_counts["red_team_revised"] == 1
        assert crew.funnel_counts["red_team_revision_accepted"] == 1


# ── Run-quality fixes §2 (2026-07-30): anchored queries + off-category abstain ──

_BOUNDARIES = (
    "This market includes shop management systems (SMS) and digital vehicle "
    "inspection (DVI) software for independent repair shops."
)


def _anchored_ctx(**overrides):
    """niche_context with the anchor vocabulary opt-IN (legacy tests stay fail-open)."""
    base = dict(
        niche_description="automotive aftermarket repair software",
        anchor_entities=["Tekmetric", "Shop-Ware", "Mitchell1 Manager SE"],
        community_search_terms=["auto repair"],
        audience_jargon=["RO (repair order)"],
        industry_boundaries=_BOUNDARIES,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _survives():
    return _verdict("survives")


class TestAnchoredQueries:
    def test_all_but_last_query_anchored(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 6)
        crew = _crew(search_map={"q": "Tekmetric review"})
        crew.niche_context = _anchored_ctx()
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (_survives(), SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([_idea()]))

        queries = crew._ma_search_batch.call_args[0][0]
        assert len(queries) == 6
        assert all("auto repair" in q for q in queries[:-1])
        assert "auto repair" not in queries[-1]  # broad arm stays unanchored
        assert queries[0].endswith("auto repair")  # anchored core query first

    def test_low_budget_queries_still_anchored(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 3)
        crew = _crew(search_map={"q": "Tekmetric review"})
        crew.niche_context = _anchored_ctx()
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (_survives(), SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([_idea()]))

        queries = crew._ma_search_batch.call_args[0][0]
        assert len(queries) == 3
        assert all("auto repair" in q for q in queries)

    def test_glossary_expands_acronym_in_queries(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 4)
        crew = _crew(search_map={"q": "Tekmetric shop management system migration"})
        crew.niche_context = _anchored_ctx()
        idea = _idea(mechanism_tag="sms-migration",
                     value_proposition="Rehearse your SMS switch before signing")
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (_survives(), SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        queries = crew._ma_search_batch.call_args[0][0]
        assert any("shop management system" in q for q in queries)
        assert not any(" sms " in f" {q} " for q in queries)


class TestOffCategoryAbstain:
    def test_foreign_evidence_abstains(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 2)
        # Result BODIES are devops content; query keys contain the anchor term —
        # the guard must look at bodies only, never the query labels.
        crew = _crew(search_map={
            "pricing calc auto repair": "Flyway vs Liquibase database migration devops",
            "pricing calc auto repair alternative": "Kubernetes migration checklist",
        })
        crew.niche_context = _anchored_ctx()
        llm = MagicMock()
        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", llm)
        idea = _idea()

        run_red_team_review(crew, _refined([idea]))

        llm.assert_not_called()
        assert idea.red_team_verdict is None
        assert idea.red_team_caveats is None
        assert "off-category" in idea.red_team_vocab_mismatch
        assert crew.funnel_counts["red_team_offcategory_abstained"] == 1
        assert crew.funnel_counts["red_team_reviewed"] == 0

    def test_on_category_via_glossary_longform(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 2)
        # No brand name in the body — matches only through the glossary expansion
        # "shop management system" parsed from industry_boundaries.
        crew = _crew(search_map={
            "q": "best shop management system for independent shops"})
        crew.niche_context = _anchored_ctx()
        idea = _idea()
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (_survives(), SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        assert idea.red_team_verdict == "survives"
        assert getattr(idea, "red_team_vocab_mismatch", None) is None
        assert crew.funnel_counts["red_team_offcategory_abstained"] == 0

    def test_fail_open_below_min_anchors(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 2)
        crew = _crew(search_map={"q": "Kubernetes migration checklist"})
        crew.niche_context = _anchored_ctx(anchor_entities=["Tekmetric", "Shop-Ware"])
        idea = _idea()
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (_survives(), SimpleNamespace(to_dict=lambda: {}))))

        run_red_team_review(crew, _refined([idea]))

        assert idea.red_team_verdict == "survives"  # guard inactive, review proceeded

    def test_empty_evidence_counter(self, monkeypatch):
        monkeypatch.setattr(settings, "red_team_top_k", 1)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 2)
        crew = _crew(search_map={})
        llm = MagicMock()
        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", llm)

        run_red_team_review(crew, _refined([_idea()]))

        llm.assert_not_called()
        assert crew.funnel_counts["red_team_empty_evidence_abstained"] == 1

    def test_digest_line_renders_abstain(self):
        idea = _idea(red_team_vocab_mismatch="probe evidence off-category: ...")
        line = _idea_digest_line(idea)
        assert "vocabulary mismatch" in line
        assert "not negative market evidence" in line


class TestTopKSlotAllocation:
    """Run-quality fixes §5: reserve-then-fill across composite / shippability / market_fit
    (a pure market_fit sort excluded whatever the payability caps had compressed)."""

    def _run(self, ideas, monkeypatch, top_k=2):
        monkeypatch.setattr(settings, "red_team_top_k", top_k)
        monkeypatch.setattr(settings, "red_team_searches_per_idea", 2)
        crew = _crew(search_map={"q": "some result"})
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (_survives(), SimpleNamespace(to_dict=lambda: {}))))
        run_red_team_review(crew, _refined(ideas))
        return [i.solution_name for i in ideas if i.red_team_verdict is not None]

    def test_shippable_idea_reviewed_despite_capped_mf(self, monkeypatch):
        # A tops composite AND shippability (the collapse case); C — not B — is the best
        # remaining ship candidate and must take the shippability slot.
        a = _idea(name="A", mf=0.9, technical_feasibility_score=0.9,
                  build_feasibility_score=0.95, solo_dev_feasibility=0.9)
        b = _idea(name="B", mf=0.6, technical_feasibility_score=0.6,
                  build_feasibility_score=0.5, solo_dev_feasibility=0.4)
        c = _idea(name="C", mf=0.4, technical_feasibility_score=0.7,
                  build_feasibility_score=0.9, solo_dev_feasibility=0.9)
        reviewed = self._run([a, b, c], monkeypatch)
        assert reviewed == ["A", "C"]  # NOT the pure-mf {A, B}

    def test_no_shippability_scores_degrades_to_mf_order(self, monkeypatch):
        a = _idea(name="A", mf=0.9, solo_dev_feasibility=None, build_feasibility_score=None,
                  technical_feasibility_score=0.6)
        b = _idea(name="B", mf=0.8, solo_dev_feasibility=None, build_feasibility_score=None,
                  technical_feasibility_score=0.6)
        c = _idea(name="C", mf=0.5, solo_dev_feasibility=None, build_feasibility_score=None,
                  technical_feasibility_score=0.6)
        reviewed = self._run([a, b, c], monkeypatch)
        assert reviewed == ["A", "B"]

    def test_ship_floor_excludes_weak_shippability(self, monkeypatch):
        # Best remaining ship = 0.5 < 0.70 bar -> slot 2 falls back to market_fit.
        a = _idea(name="A", mf=0.9, technical_feasibility_score=0.9,
                  build_feasibility_score=0.6, solo_dev_feasibility=0.5)
        b = _idea(name="B", mf=0.7, technical_feasibility_score=0.6,
                  build_feasibility_score=0.5, solo_dev_feasibility=0.5)
        c = _idea(name="C", mf=0.3, technical_feasibility_score=0.4,
                  build_feasibility_score=0.5, solo_dev_feasibility=0.5)
        reviewed = self._run([a, b, c], monkeypatch)
        assert reviewed == ["A", "B"]


class TestSeedRunDataContext:
    """"Check my idea" seed reviews carry the run's own validated pains, so a kill
    caveat can never claim demand evidence is absent against the run's own counts."""

    def _seed_idea(self):
        return _idea(
            solution_name="FairPlay Ledger",
            pain_points_addressed=["Cannot prove equal playing time during active games"],
        )

    def _crew_with_pains(self, dispatch_id):
        crew = _crew(search_map={"q": "TeamSnap ships lineup tools for coaches"})
        crew._current_seed_dispatch_id = dispatch_id
        crew.pain_point_analysis = SimpleNamespace(pain_points=[SimpleNamespace(
            title="Cannot prove equal playing time during active games",
            mention_count=16)])
        return crew

    def _captured_prompt(self, crew, monkeypatch):
        captured = {}

        def fake_invoke(**kw):
            captured["prompt"] = kw.get("prompt", "")
            return _RedTeamVerdict(verdict="survives", findings=[], uplift=None), None

        from nicheiq.utils import llm_service
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured", staticmethod(fake_invoke))
        pool = SimpleNamespace(solution_ideas=[self._seed_idea()])
        run_red_team_review(crew, pool)
        return captured.get("prompt", "")

    def test_validate_seed_prompt_carries_run_counts(self, monkeypatch):
        prompt = self._captured_prompt(self._crew_with_pains("validate"), monkeypatch)
        assert "This run's own discovery already validated these pains" in prompt
        assert "(16 mentions)" in prompt
        assert "never claim demand evidence is absent" in prompt

    def test_pool_reviews_get_no_run_data_block(self, monkeypatch):
        prompt = self._captured_prompt(self._crew_with_pains(None), monkeypatch)
        assert "This run's own discovery" not in prompt

    def test_prompt_hard_types_absence_of_evidence_as_gap(self, monkeypatch):
        prompt = self._captured_prompt(self._crew_with_pains("validate"), monkeypatch)

        assert "AFFIRMATIVE kinds are" in prompt
        assert "MUST always be evidence_gap" in prompt
        for phrase in ("not found", "no proof", "does not appear"):
            assert phrase in prompt


class TestUserSeedIsNeverReplaced:
    """"Check my idea" grades the product the USER submitted. The seed is the only visible
    idea so it is ALWAYS red-teamed, and an ACCEPTED revision replaced it via
    `ideas[idx] = rev` — which guaranteed a non-empty identity diff at the post-tail lock in
    `execute_seed_pipeline` and refused the fully-paid run. On the seed path the revision
    could therefore only reject, or destroy a run; it could never improve the idea."""

    def test_a_user_seed_revision_is_never_attempted(self, monkeypatch):
        from nicheiq.utils import red_team_review as rtr

        seed = _idea(name="MySubmittedProduct", source_frame="user_seed")
        refined = _refined([seed])
        crew = _crew()

        # RECORD the calls; do NOT raise. `_attempt_red_team_revision` is fail-soft
        # (`except Exception` -> return False), so an exception-based probe is swallowed and
        # the test passes with or without the guard.
        llm_calls: list = []
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            lambda **_kw: (llm_calls.append(True), (SimpleNamespace(), None))[1])
        crew._score_wave = MagicMock()

        assert rtr._attempt_red_team_revision(
            crew, refined, seed,
            _RedTeamVerdict(verdict="weakened", findings=[RedTeamFinding(
                claim="an incumbent ships this", kind="verified_incumbent_overlap")]),
            "evidence") is False
        assert llm_calls == [], "revision LLM call must not run for a user seed"
        crew._score_wave.assert_not_called()
        # The submitted product is still the one in the pool, unmodified.
        assert refined.solution_ideas == [seed]
        assert seed.solution_name == "MySubmittedProduct"

    def test_a_non_seed_idea_is_still_revised(self, monkeypatch):
        """The guard is scoped to seeds: ordinary discovery ideas keep the revision path,
        which is where it earns its keep."""
        from nicheiq.utils import red_team_review as rtr

        idea = _idea(name="DiscoveryIdea", source_frame="pain")
        refined = _refined([idea])
        crew = _crew()
        reached = []
        monkeypatch.setattr(
            llm_service.LLMService, "invoke_structured",
            lambda **_kw: (reached.append(True), (_ for _ in ()).throw(RuntimeError("stop")))[0])

        rtr._attempt_red_team_revision(
            crew, refined, idea,
            _RedTeamVerdict(verdict="weakened", findings=[RedTeamFinding(
                claim="an incumbent ships this", kind="verified_incumbent_overlap")]),
            "evidence")
        assert reached, "non-seed ideas must still reach the revision attempt"
