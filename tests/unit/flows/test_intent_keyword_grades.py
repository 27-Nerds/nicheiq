"""Q-049 batch-1 — idea-intent grade stamping, volume bands, honesty caveat, SEO-kill
on-idea slice, and the 4.2 fallback prefilter (research_flow Stage 6 units)."""

from types import SimpleNamespace

import pytest
from loguru import logger as loguru_logger

import nicheiq.flows.research_flow as rf
import nicheiq.utils.validation.keyword_intent_validator as kiv
from nicheiq.config.settings import settings
from nicheiq.utils.intent_volume_bands import (
    MIN_GRADED_COVERAGE,
    compute_intent_volume_bands,
    graded_coverage,
)


def _flow(**attrs):
    f = rf.ResearchFlow.__new__(rf.ResearchFlow)  # no heavy __init__
    f.niche_description = attrs.pop("niche_description", "test niche")
    for k, v in attrs.items():
        setattr(f, k, v)
    return f


def _solution(**kw):
    base = dict(
        solution_name="RigCalc",
        value_proposition="KV-cache concurrency rig calculator for self-hosted LLM inference",
        pain_points_addressed=["cannot size GPU rigs for concurrent sessions"],
        winning_angle="distribution_seo",
    )
    base.update(kw)
    return SimpleNamespace(**base)


class _FakeValidator:
    """Stands in for KeywordIntentRelevanceValidator; grades from a preset map."""
    grades_map: dict = {}
    calls: list = []
    raise_on_grade = False

    def __init__(self, *a, **kw):
        pass

    def grade_keywords(self, ctx, keywords, max_workers=4):
        type(self).calls.append(list(keywords))
        if type(self).raise_on_grade:
            raise RuntimeError("grader down")
        return {k: type(self).grades_map.get(k) for k in keywords}


@pytest.fixture
def fake_validator(monkeypatch):
    _FakeValidator.grades_map = {}
    _FakeValidator.calls = []
    _FakeValidator.raise_on_grade = False
    monkeypatch.setattr(kiv, "KeywordIntentRelevanceValidator", _FakeValidator)
    # keep the LLM-seed arm dark so no LLMService call fires
    monkeypatch.setattr(settings, "contains_seed_thin_seed_threshold", 0)
    monkeypatch.setattr(settings, "contains_seed_llm_seeds", False)
    return _FakeValidator


@pytest.fixture
def log_capture():
    msgs: list[str] = []
    sink_id = loguru_logger.add(lambda m: msgs.append(str(m)), level="DEBUG")
    yield msgs
    loguru_logger.remove(sink_id)


class TestGradeStamping:
    def test_stamped_before_no_seed_early_return(self, fake_validator):
        """Grades land on the keyword dicts even when augmentation bails at 'no seeds'."""
        # 4+-word keywords can never become broad seeds (1-3 word rule) => early return
        kws = [{"keyword": "a b c d", "search_volume": 100},
               {"keyword": "e f g h i", "search_volume": 50}]
        fake_validator.grades_map = {"a b c d": 1, "e f g h i": 0}
        out = _flow()._augment_idea_intent_keywords(kws, _solution())
        assert out is kws  # early return path (input list)
        assert out[0]["idea_intent_grade"] == 1
        assert out[1]["idea_intent_grade"] == 0

    def test_merged_rows_carry_grade(self, fake_validator, monkeypatch):
        """M4: contains-seed merged rows are stamped from new_grades (highest-intent set)."""
        monkeypatch.setattr(settings, "contains_seed_merge_min_grade", 3)
        kws = [{"keyword": "rig calculator", "search_volume": 200}]
        fake_validator.grades_map = {"rig calculator": 3, "llm rig calculator": 3,
                                     "gpu rig pricing": 1}
        tool = SimpleNamespace(
            get_keyword_suggestions=lambda s, limit=0: [
                {"keyword": "llm rig calculator", "search_volume": 90, "competition": 0.2},
                {"keyword": "gpu rig pricing", "search_volume": 500, "competition": 0.1},
            ],
            get_related_keywords=lambda s, depth=0, limit=0: [],
        )
        out = _flow(dataforseo_tool=tool)._augment_idea_intent_keywords(kws, _solution())
        assert out[0]["idea_intent_grade"] == 3  # existing row stamped
        merged = [k for k in out if k["keyword"] == "llm rig calculator"]
        assert merged and merged[0]["idea_intent_grade"] == 3
        # grade-1 suggestion below the merge gate never merged
        assert not any(k["keyword"] == "gpu rig pricing" for k in out)

    def test_inactive_path_logs_guard(self, fake_validator, log_capture):
        out = _flow()._augment_idea_intent_keywords(
            [{"keyword": "x y", "search_volume": 1}], None)
        assert "idea_intent_grade" not in out[0]
        assert any("[SEO-RELEVANCE] guard inactive" in m for m in log_capture)

    def test_grader_failure_logs_degraded_and_returns_input(self, fake_validator, log_capture):
        fake_validator.raise_on_grade = True
        kws = [{"keyword": "a b", "search_volume": 10}]
        out = _flow()._augment_idea_intent_keywords(kws, _solution())
        assert out is kws and "idea_intent_grade" not in kws[0]
        assert any("[SEO-RELEVANCE] guard degraded" in m for m in log_capture)

    def test_ungraded_over_20pct_warns(self, fake_validator, log_capture):
        kws = [{"keyword": f"kw number {i} extra", "search_volume": 10} for i in range(10)]
        fake_validator.grades_map = {k["keyword"]: 1 for k in kws[:7]}  # 3/10 ungraded
        _flow()._augment_idea_intent_keywords(kws, _solution())
        assert any("guard degraded" in m and "ungraded" in m for m in log_capture)


class TestResumeRegrade:
    def test_skipped_when_grades_present(self, fake_validator, log_capture):
        kws = [{"keyword": "a b", "search_volume": 10, "idea_intent_grade": 2}]
        _flow()._regrade_resumed_keywords(kws, _solution())
        assert fake_validator.calls == []
        assert any("re-grade skipped" in m for m in log_capture)

    def test_regrades_when_absent(self, fake_validator):
        kws = [{"keyword": "a b", "search_volume": 10},
               {"keyword": "c d", "search_volume": 20}]
        fake_validator.grades_map = {"a b": 2, "c d": 0}
        _flow()._regrade_resumed_keywords(kws, _solution())
        assert kws[0]["idea_intent_grade"] == 2 and kws[1]["idea_intent_grade"] == 0

    def test_no_solution_logs_inactive(self, fake_validator, log_capture):
        kws = [{"keyword": "a b", "search_volume": 10}]
        _flow()._regrade_resumed_keywords(kws, None)
        assert "idea_intent_grade" not in kws[0]
        assert any("[SEO-RELEVANCE] guard inactive" in m for m in log_capture)

    def test_failure_is_fail_soft(self, fake_validator, log_capture):
        fake_validator.raise_on_grade = True
        kws = [{"keyword": "a b", "search_volume": 10}]
        _flow()._regrade_resumed_keywords(kws, _solution())  # must not raise
        assert "idea_intent_grade" not in kws[0]
        assert any("resume re-grade failed" in m for m in log_capture)


def _kwrow(kw, vol, grade="absent"):
    row = {"keyword": kw, "search_volume": vol}
    if grade != "absent":
        row["idea_intent_grade"] = grade
    return row


class TestVolumeBands:
    def test_band_math_partitions_volume(self):
        kws = [_kwrow("j", 100, 3), _kwrow("b", 100, 2), _kwrow("c", 100, 1),
               _kwrow("o", 100, 0), _kwrow("u", 100, None)]
        bands = compute_intent_volume_bands(kws, min_grade=2)
        assert bands["idea_intent_monthly_volume"] == 200  # grades 2+3
        assert bands["category_volume_share"] == 0.4       # grade 1 + ungraded (None)
        assert bands["offtopic_volume_share"] == 0.2

    def test_coverage_guard_at_80pct_boundary(self):
        graded = [_kwrow(f"g{i}", 10, 1) for i in range(8)]
        ungraded = [_kwrow(f"u{i}", 10) for i in range(2)]  # no stamp at all
        assert graded_coverage(graded + ungraded) == pytest.approx(0.8)
        # None-stamped rows count as GRADED coverage? No — stamp value None = ungraded.
        bands = compute_intent_volume_bands(graded + ungraded)
        assert bands["idea_intent_monthly_volume"] is not None  # 0.8 >= guard

    def test_coverage_below_80pct_withholds_all_fields(self, log_capture):
        kws = [_kwrow("a", 10, 3)] + [_kwrow(f"u{i}", 10) for i in range(4)]  # 20% graded
        bands = compute_intent_volume_bands(kws)
        assert bands == {"offtopic_volume_share": None, "category_volume_share": None,
                         "idea_intent_monthly_volume": None}
        assert any("[SEO-RELEVANCE] guard degraded" in m for m in log_capture)

    def test_none_stamp_counts_as_ungraded_for_coverage(self):
        kws = [_kwrow("a", 10, None), _kwrow("b", 10, None), _kwrow("c", 10, 2)]
        assert graded_coverage(kws) == pytest.approx(1 / 3)

    def test_min_grade_floor_uses_setting_not_hardcoded_2(self, monkeypatch):
        monkeypatch.setattr(settings, "keyword_relevance_min_grade", 3)
        kws = [_kwrow("j", 100, 3), _kwrow("b", 100, 2), _kwrow("c", 100, 1)]
        bands = compute_intent_volume_bands(kws)
        assert bands["idea_intent_monthly_volume"] == 100  # grade-2 excluded at floor 3


class _CaveatHost:
    """ResearchFlow.state is a read-only Flow property — bind the method onto a stand-in."""
    _append_seo_intent_caveat = rf.ResearchFlow._append_seo_intent_caveat

    def __init__(self):
        self.state = SimpleNamespace(pipeline_degradations=[])


def _caveat_flow():
    return _CaveatHost()


def _seo_rep(iiv, off, cat, total):
    return SimpleNamespace(idea_intent_monthly_volume=iiv, offtopic_volume_share=off,
                           category_volume_share=cat, total_monthly_volume=total)


class TestSeoIntentCaveat:
    def test_low_intent_share_fires(self):
        f = _caveat_flow()
        f._append_seo_intent_caveat(_seo_rep(50, 0.1, 0.85, 1000), [])
        assert len(f.state.pipeline_degradations) == 1
        assert "idea-intent" in f.state.pipeline_degradations[0]

    def test_high_offtopic_share_fires(self):
        f = _caveat_flow()
        f._append_seo_intent_caveat(_seo_rep(400, 0.4, 0.2, 1000), [])
        assert any("off-topic" in m for m in f.state.pipeline_degradations)

    def test_concentration_fires_on_non_intent_head_term(self):
        """m3-refined: a single >50% head term whose grade is None or < min_grade."""
        f = _caveat_flow()
        kws = [_kwrow("big head", 600, 1), _kwrow("small", 100, 3)]
        f._append_seo_intent_caveat(_seo_rep(300, 0.1, 0.6, 1000), kws)
        assert any("big head" in m for m in f.state.pipeline_degradations)

    def test_concentration_silent_on_idea_intent_head_term(self):
        """A legitimately dominant JOB/BUYER head term never trips the concentration check."""
        f = _caveat_flow()
        kws = [_kwrow("big head", 600, 3), _kwrow("small", 100, 1)]
        f._append_seo_intent_caveat(_seo_rep(650, 0.05, 0.3, 1000), kws)
        assert f.state.pipeline_degradations == []

    def test_suppressed_when_bands_none(self):
        f = _caveat_flow()
        f._append_seo_intent_caveat(_seo_rep(None, None, None, 1000), [])
        assert f.state.pipeline_degradations == []

    def test_suppressed_when_guard_off(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_offtopic_volume_guard", False)
        f = _caveat_flow()
        f._append_seo_intent_caveat(_seo_rep(50, 0.4, 0.5, 1000), [])
        assert f.state.pipeline_degradations == []

    def test_healthy_set_no_caveat(self):
        f = _caveat_flow()
        f._append_seo_intent_caveat(_seo_rep(400, 0.1, 0.5, 1000), [_kwrow("a", 100, 3)])
        assert f.state.pipeline_degradations == []

    def test_deduplicated_on_repeat_call(self):
        f = _caveat_flow()
        rep = _seo_rep(50, 0.1, 0.85, 1000)
        f._append_seo_intent_caveat(rep, [])
        f._append_seo_intent_caveat(rep, [])
        assert len(f.state.pipeline_degradations) == 1


def _kill_flow():
    f = _flow()
    f.serper_tool = None
    f.search_tool = None
    return f


class TestSeoKillOnIdeaFields:
    def test_on_idea_fields_computed_when_fully_graded(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        kws = ([{"keyword": f"j{i}", "search_volume": 500, "keyword_difficulty": 20,
                 "idea_intent_grade": 3} for i in range(30)]
               + [{"keyword": f"c{i}", "search_volume": 500, "keyword_difficulty": 80,
                   "idea_intent_grade": 1} for i in range(10)])
        r = _kill_flow()._compute_seo_kill_question(kws, SimpleNamespace(winning_angle="distribution_seo"))
        assert r.on_idea_page_ceiling == 30
        assert r.on_idea_winnable == 30  # all grade-3 rows carry KD 20 < 40
        assert r.indexable_page_ceiling == 40  # category rows still in the page universe

    def test_on_idea_fields_none_under_coverage_guard(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        kws = [{"keyword": f"k{i}", "search_volume": 500, "keyword_difficulty": 20}
               for i in range(40)]  # no grades at all
        r = _kill_flow()._compute_seo_kill_question(kws, SimpleNamespace(winning_angle="distribution_seo"))
        assert r.on_idea_page_ceiling is None and r.on_idea_winnable is None

    def test_grade0_filter_kill_switch(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        monkeypatch.setattr(settings, "seo_offtopic_volume_guard", False)
        kws = ([{"keyword": f"k{i}", "search_volume": 500, "keyword_difficulty": 20,
                 "idea_intent_grade": 2} for i in range(35)]
               + [{"keyword": f"z{i}", "search_volume": 500, "keyword_difficulty": 20,
                   "idea_intent_grade": 0} for i in range(10)])
        r = _kill_flow()._compute_seo_kill_question(kws, SimpleNamespace(winning_angle="distribution_seo"))
        assert r.indexable_page_ceiling == 45  # guard off => grade-0 rows retained


class TestFallbackPrefilter:
    def test_offtopic_pool_rows_dropped(self):
        sol = _solution()
        nc = SimpleNamespace(audience_jargon=["KV (key-value cache)"], industry_boundaries="")
        pool = [
            {"keyword": "llm concurrency calculator", "search_volume": 100},
            {"keyword": "kv cache sizing", "search_volume": 400},
            {"keyword": "best credit card rewards", "search_volume": 9000},
        ]
        out = _flow()._prefilter_fallback_keywords(pool, sol, nc)
        kept = [k["keyword"] for k in out]
        assert "best credit card rewards" not in kept
        assert set(kept) == {"llm concurrency calculator", "kv cache sizing"}
        assert kept[0] == "kv cache sizing"  # volume-sorted survivors

    def test_fail_closed_even_below_20_survivors(self):
        """Regression: a 0-seed solution must never inherit the raw cross-solution pool."""
        sol = _solution()
        nc = SimpleNamespace(audience_jargon=[], industry_boundaries="")
        pool = [{"keyword": f"unrelated cooking recipe {i}", "search_volume": 100 + i}
                for i in range(30)]
        out = _flow()._prefilter_fallback_keywords(pool, sol, nc)
        assert out == []  # fail-closed: survivors used even when empty

    def test_empty_corpus_fails_open(self):
        sol = SimpleNamespace(solution_name="X", value_proposition="",
                              pain_points_addressed=[], winning_angle="")
        nc = SimpleNamespace(audience_jargon=[], industry_boundaries="")
        pool = [{"keyword": "anything at all", "search_volume": 10}]
        out = _flow()._prefilter_fallback_keywords(pool, sol, nc)
        assert len(out) == 1
