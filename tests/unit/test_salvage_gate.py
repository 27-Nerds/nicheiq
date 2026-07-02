"""Portfolio funnel F1 — salvage gate (A/B-validated, always on).

Tournament losers get one calibration-critic batch; promotion at max(0.55, own-cell winner − 0.05),
cap salvage_max_promoted; promoted losers are fully expanded and tagged idea_tier='salvaged'.
"""

from types import SimpleNamespace

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _concept(name, pain="pain A", **kw):
    base = dict(concept_name=name, one_liner=f"{name} does a thing", mechanism_tag="calc",
                source_segment="Seg", source_pain=pain, why_non_obvious="insight",
                data_route="official state pages", data_acquisition_notes="", data_access_model="official",
                build_feasibility_score=0.7, data_feasibility_score=0.7, target_keywords=["kw"],
                project_type="saas")
    base.update(kw)
    return SimpleNamespace(**base)


def _winner(name, pain="pain A", comp=0.6):
    return SimpleNamespace(solution_name=name, source_pain=pain,
                           market_fit_score=comp, technical_feasibility_score=comp,
                           novelty_score=comp, seo_scalability_score=comp)


def _crew(monkeypatch, scores_by_name):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)

    def _fake_calibrate(*, batch):
        for idea in batch:
            s = scores_by_name.get(idea.solution_name, 0.3)
            idea.market_fit_score = s
            idea.technical_feasibility_score = s
            idea.novelty_score = s
            idea.seo_scalability_score = s
        return (len(batch), None)

    crew._calibrate_batch = _fake_calibrate
    crew._refine_single_concept = lambda c, pain: SimpleNamespace(
        solution_name=c.concept_name, idea_tier="single")  # tier is overwritten by the gate
    return crew


class TestSalvageGate:
    def _groups(self, losers):
        cell = {"pain": SimpleNamespace(title="pain A"), "segment": None}
        # winner's origin concept is claimed by exact name; losers share the cell
        return [(cell, [_concept("WinnerIdea")] + losers)]

    def test_promotes_loser_above_bar_and_tags_tier(self, monkeypatch):
        crew = _crew(monkeypatch, {"GoodLoser": 0.62, "BadLoser": 0.30})
        winners = [_winner("WinnerIdea", comp=0.60)]
        out = crew._salvage_cell_losers(self._groups([_concept("GoodLoser"), _concept("BadLoser")]), winners)
        assert [o.solution_name for o in out] == ["GoodLoser"]
        assert out[0].idea_tier == "salvaged"

    def test_declines_below_absolute_floor_even_if_near_weak_winner(self, monkeypatch):
        # winner 0.40 → bar = max(0.55, 0.35) = 0.55; loser 0.50 near the weak winner still declines
        crew = _crew(monkeypatch, {"MehLoser": 0.50})
        winners = [_winner("WinnerIdea", comp=0.40)]
        out = crew._salvage_cell_losers(self._groups([_concept("MehLoser")]), winners)
        assert out == []

    def test_cap_respected(self, monkeypatch):
        monkeypatch.setattr(settings, "salvage_max_promoted", 1)
        crew = _crew(monkeypatch, {"L1": 0.70, "L2": 0.65})
        winners = [_winner("WinnerIdea", comp=0.60)]
        out = crew._salvage_cell_losers(self._groups([_concept("L1"), _concept("L2")]), winners)
        assert len(out) == 1 and out[0].solution_name == "L1"  # highest composite wins the cap

    def test_winner_origin_concept_not_treated_as_loser(self, monkeypatch):
        crew = _crew(monkeypatch, {"WinnerIdea": 0.9})
        winners = [_winner("WinnerIdea", comp=0.60)]
        out = crew._salvage_cell_losers(self._groups([]), winners)
        assert out == []  # the claimed concept never re-enters

    def test_fail_soft(self, monkeypatch):
        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew._calibrate_batch = lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))
        winners = [_winner("W")]
        cell = {"pain": SimpleNamespace(title="pain A"), "segment": None}
        assert crew._salvage_cell_losers([(cell, [_concept("X")])], winners) == []


class TestSalvageUpgrade2026_07_02:
    """Wider net + structural dedup + per-pain diversity."""

    def _groups(self, concepts, pain="pain A"):
        cell = {"pain": SimpleNamespace(title=pain), "segment": None}
        return [(cell, concepts)]

    def test_renamed_winner_structural_duplicate_skipped(self, monkeypatch):
        # loser has a different NAME but the same one-liner substance as a winner —
        # salvaging it would put the same idea in the report twice
        crew = _crew(monkeypatch, {"RenamedTwin": 0.9})
        winner = _winner("BakePriceHelper", comp=0.60)
        winner.value_proposition = "calculates fair prices for home bakers using labor and ingredient costs"
        winner.description = ""
        winner.mechanism_tag = "pricing-calculator"
        twin = _concept("RenamedTwin",
                        one_liner="calculates fair prices for home bakers using labor and ingredient costs",
                        mechanism_tag="pricing-calculator")
        out = crew._salvage_cell_losers(self._groups([twin]), [winner])
        assert out == []

    def test_same_pain_same_mechanism_cousin_skipped(self, monkeypatch):
        # reworded cousin: same source pain + matching mechanism tag, different text
        crew = _crew(monkeypatch, {"CousinIdea": 0.9})
        winner = _winner("WinnerIdea", pain="pain A", comp=0.60)
        winner.value_proposition = "completely different wording about scheduling vans"
        winner.description = ""
        winner.mechanism_tag = "route-optimizer"
        cousin = _concept("CousinIdea", pain="pain A",
                          one_liner="an entirely fresh take on planning the day",
                          mechanism_tag="route-optimization")
        out = crew._salvage_cell_losers(self._groups([cousin]), [winner])
        assert out == []

    def test_distinct_mechanism_same_pain_still_eligible(self, monkeypatch):
        crew = _crew(monkeypatch, {"FreshAngle": 0.70})
        winner = _winner("WinnerIdea", pain="pain A", comp=0.60)
        winner.value_proposition = "route optimizer for grooming vans"
        winner.description = ""
        winner.mechanism_tag = "route-optimizer"
        fresh = _concept("FreshAngle", pain="pain A",
                         one_liner="benchmark database of realistic per-breed groom times",
                         mechanism_tag="benchmark-database")
        out = crew._salvage_cell_losers(self._groups([fresh]), [winner])
        assert [o.solution_name for o in out] == ["FreshAngle"]

    def test_per_pain_cap_two_promotions_max(self, monkeypatch):
        monkeypatch.setattr(settings, "salvage_max_promoted", 3)
        crew = _crew(monkeypatch, {"A1": 0.80, "A2": 0.75, "A3": 0.70, "B1": 0.65})
        winner = _winner("WinnerIdea", pain="other pain", comp=0.55)
        cell_a = {"pain": SimpleNamespace(title="pain A"), "segment": None}
        cell_b = {"pain": SimpleNamespace(title="pain B"), "segment": None}
        groups = [
            (cell_a, [_concept("A1", pain="pain A", mechanism_tag="m-one"),
                      _concept("A2", pain="pain A", mechanism_tag="m-two"),
                      _concept("A3", pain="pain A", mechanism_tag="m-three")]),
            (cell_b, [_concept("B1", pain="pain B", mechanism_tag="m-four")]),
        ]
        out = crew._salvage_cell_losers(groups, [winner])
        names = [o.solution_name for o in out]
        # A3 (3rd on pain A) yields its slot to B1 despite higher composite
        assert names == ["A1", "A2", "B1"]

    def test_scoring_cost_bound_ten(self, monkeypatch):
        # widen-to-16 A/B (2026-07-02) was a no-op — real pools run ~4 eligible losers;
        # the original 10 cap stands
        scored = {}

        def _cal(*, batch):
            for i in batch:
                scored[i.solution_name] = True
                i.market_fit_score = 0.3
            return (len(batch), None)
        crew = _crew(monkeypatch, {})
        crew._calibrate_batch = _cal
        concepts = [_concept(f"L{i}", mechanism_tag=f"mech-{i}") for i in range(20)]
        crew._salvage_cell_losers(self._groups(concepts), [_winner("W", pain="zzz")])
        assert len(scored) == 10


def test_tunable_default():
    # gate is unconditional (flag removed after the 2026-07-02 production A/B)
    assert settings.salvage_max_promoted == 3


def test_idea_tier_default_single():
    from nicheiq.models.solution_idea import BaseSolutionIdea
    assert BaseSolutionIdea.model_fields["idea_tier"].default == "single"


def test_final_checkpoint_resave_after_post_union_mutations():
    """Checkpoint-ordering regression (live-caught 2026-07-02 astro run): calibrate/angle/
    validate/tags mutate ideas AFTER the mid-pipeline stage_5_3 save; execute_pipeline must
    re-save the FINAL ideas before returning, not rely on a later incidental save."""
    import inspect
    from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
    src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
    calibrate_pos = src.index("_calibrate_idea_scores(")
    resave_pos = src.rindex('save_stage("stage_5_3_refinement"')
    assert resave_pos > calibrate_pos, (
        "final stage_5_3 re-save must come AFTER the post-union calibration mutations")
