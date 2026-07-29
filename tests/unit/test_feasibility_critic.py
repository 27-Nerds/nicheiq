"""Phase 1 — merged feasibility critic + verdict-boundary caps (flagged).

Exercises the critic via a SimpleNamespace 'self' (avoids heavy __init__), and the
verdict caps via the static/instance helpers on ReportGenerator with a stub state.
"""

from types import SimpleNamespace

import pytest

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.models.solution_idea import RawConcept


def _rc(name, obv=0.3):
    return RawConcept(
        concept_name=name,
        one_liner=f"{name} does a thing",
        ideation_technique="niche_drilling",
        project_type="saas",
        target_keywords=["a", "b"],
    )


def _critic_self():
    # The _score_pool_novelty wrapper now dispatches to _score_concepts + _finalize_critic_pool;
    # bind both onto the SimpleNamespace stub so the unbound-call pattern still works.
    fake = SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: an existing tool",
        audience_mapping=None,
        _record_divergent_usage=lambda u: None,
    )
    fake._score_concepts = usc.UnifiedSolutionCrew._score_concepts.__get__(fake)
    fake._finalize_critic_pool = usc.UnifiedSolutionCrew._finalize_critic_pool.__get__(fake)
    return fake


def _verdicts(items, drop_names=None):
    return usc._NoveltyVerdicts(
        verdicts=[usc._NoveltyVerdict(**it) for it in items],
        drop_names=drop_names or [],
    )


class TestMergedCritic:
    def _run(self, monkeypatch, concepts, result):
        monkeypatch.setattr(
            usc.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (result, SimpleNamespace())),
        )
        return usc.UnifiedSolutionCrew._score_pool_novelty(_critic_self(), concepts)

    def test_writes_feasibility_fields_and_keeps_unofficial(self, monkeypatch):
        concepts = [_rc("A"), _rc("B")]
        # bulk_route is now required to keep a source verified (no route => 'restricted').
        result = _verdicts([
            {"name": "A", "independent_obviousness": 0.2, "build_feasibility": 0.7,
             "data_feasibility": 0.65, "data_access_model": "unofficial",
             "bulk_route": "community scraper list endpoint", "data_notes": "via community scraper; ToS-gray"},
            {"name": "B", "independent_obviousness": 0.3, "build_feasibility": 0.8,
             "data_feasibility": 0.9, "data_access_model": "public",
             "bulk_route": "official public API", "data_notes": "public API"},
        ])
        out = self._run(monkeypatch, concepts, result)
        names = {c.concept_name for c in out}
        assert names == {"A", "B"}  # unofficial KEPT, nothing dropped
        a = next(c for c in out if c.concept_name == "A")
        # build 0.7 <= data 0.65 + 0.15 margin, so coupling does not fire; values preserved
        assert a.build_feasibility_score == 0.7
        assert a.data_feasibility_score == 0.65
        assert a.data_access_model == "unofficial"

    def test_no_bulk_route_downgrades_to_restricted_and_caps(self, monkeypatch):
        # The bulk_route gate: a source with no named route is UNVERIFIED -> 'restricted',
        # data capped to restricted cap (0.45), build coupled to data+margin (0.60).
        concepts = [_rc("A")]
        result = _verdicts([
            {"name": "A", "independent_obviousness": 0.2, "build_feasibility": 0.9,
             "data_feasibility": 0.9, "data_access_model": "public", "bulk_route": "NO-BULK",
             "data_notes": "claims a public API"},
        ])
        out = self._run(monkeypatch, concepts, result)
        a = out[0]
        assert a.data_access_model == "restricted"
        assert a.data_feasibility_score == 0.45
        assert a.build_feasibility_score == pytest.approx(0.6)
        # Note is reconciled at the source so label and notes don't drift.
        assert "no bulk route confirmed" in (a.data_acquisition_notes or "")

    def test_off_vocab_access_label_abstains_to_unverified(self, monkeypatch):
        # data_access_model is free text on the wire; an off-vocab token used to land
        # verbatim in the report field AND tags.data_access. Abstain, never persist.
        concepts = [_rc("A")]
        result = _verdicts([
            {"name": "A", "independent_obviousness": 0.2, "build_feasibility": 0.7,
             "data_feasibility": 0.7, "data_access_model": "subscription",
             "bulk_route": "official public API", "data_notes": "vendor API"},
        ])
        out = self._run(monkeypatch, concepts, result)
        assert out[0].data_access_model == "unverified"

    def test_in_vocab_access_label_passes_through(self, monkeypatch):
        # 'freemium' IS a DataAccessTag (free data tier + paid features) — not a
        # monetization leak, so the guard must not touch it.
        concepts = [_rc("A")]
        result = _verdicts([
            {"name": "A", "independent_obviousness": 0.2, "build_feasibility": 0.7,
             "data_feasibility": 0.7, "data_access_model": "freemium",
             "bulk_route": "official public API", "data_notes": "free tier API"},
        ])
        out = self._run(monkeypatch, concepts, result)
        assert out[0].data_access_model == "freemium"

    def test_drop_names_allowlisted_and_applied(self, monkeypatch):
        concepts = [_rc(f"c{i}") for i in range(8)]  # >= MIN_KEEP so a drop survives
        result = _verdicts(
            [{"name": f"c{i}", "independent_obviousness": 0.3, "build_feasibility": 0.7,
              "data_feasibility": 0.5, "data_access_model": "public"} for i in range(8)],
            drop_names=["c0", "NONEXISTENT-INJECTED"],  # second is not an input → ignored
        )
        out = self._run(monkeypatch, concepts, result)
        names = {c.concept_name for c in out}
        assert "c0" not in names          # legit no-route drop applied
        assert len(out) == 7              # only one dropped; injected name ignored
        assert "NONEXISTENT-INJECTED" not in names

    def test_floor_guard_refills_large_pool(self, monkeypatch):
        concepts = [_rc(f"c{i}") for i in range(8)]
        # drop 5 → would leave 3 (<6) → floor refills back to 6
        result = _verdicts(
            [{"name": f"c{i}", "independent_obviousness": 0.3} for i in range(8)],
            drop_names=[f"c{i}" for i in range(5)],
        )
        out = self._run(monkeypatch, concepts, result)
        assert len(out) == 6

    def test_fail_open(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError("x")
        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(boom))
        concepts = [_rc("A"), _rc("B")]
        out = usc.UnifiedSolutionCrew._score_pool_novelty(_critic_self(), concepts)
        assert len(out) == 2  # unchanged

# ---- verdict-boundary caps (enable_verdict_data_caps) removed 2026-07-07 (never validated) ----


# ---- Phase 5: trend longevity downgrade-only reconcile ----

from nicheiq.crews.trend_longevity_crew import reconcile_longevity_verdict as _recon


class TestTrendReconcile:
    def test_llm_may_not_raise_above_grounded(self):
        assert _recon("Risky", "Sustainable") == "Risky"  # clamped down

    def test_llm_may_lower(self):
        assert _recon("Sustainable", "Fad") == "Fad"      # LLM worse → kept
        assert _recon("Sustainable", "Risky") == "Risky"

    def test_equal_kept(self):
        assert _recon("Risky", "Risky") == "Risky"

    def test_undetermined_keeps_llm(self):
        assert _recon("Undetermined", "Sustainable") == "Sustainable"
        assert _recon("Undetermined", "Fad") == "Fad"


# ---- Phase 4: Stage-13 data-feasibility reconcile (downgrade-only) ----

from nicheiq.crews.data_source_crew import reconcile_data_feasibility as _recon_data


class TestDataReconcile:
    def test_harder_lowers_and_caveats(self):
        # critic said public (0.95); Stage-13 verified 'paid' → harder
        score, access, caveat = _recon_data(0.95, "public", "paid")
        assert score == 0.65 and access == "paid" and caveat and "harder" in caveat

    def test_unofficial_estimate_to_paid(self):
        score, access, caveat = _recon_data(0.6, "unofficial", "partner-only")
        assert score <= 0.4 and access == "partner-only" and caveat

    def test_not_harder_no_change(self):
        # Stage-13 'public' is easier than critic 'paywalled' → no downgrade
        score, access, caveat = _recon_data(0.65, "paywalled", "public")
        assert score == 0.65 and access == "paywalled" and caveat is None

    def test_never_raises_score(self):
        # critic already low; verified 'freemium' (0.8) must NOT raise it
        score, _access, caveat = _recon_data(0.3, "restricted", "freemium")
        # restricted(1) vs freemium(4): verified easier → no change
        assert score == 0.3 and caveat is None

    def test_unknown_verified_noop(self):
        assert _recon_data(0.9, "public", None) == (0.9, "public", None)
