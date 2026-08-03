"""Tests for nicheiq.utils.score_helpers."""

from types import SimpleNamespace

import pytest

from nicheiq.config.settings import settings
from nicheiq.models.solution_selection import SolutionScores
from nicheiq.utils.score_helpers import (
    AUDIENCE_FIT_COVERAGE_MIN,
    angle_ranked_composite,
    audience_fit_coverage,
    backfill_solution_scores,
    choose_auto_pick,
    compute_solution_scores,
)


class _FakeIdea:
    """Minimal stand-in for BaseSolutionIdea with configurable score fields."""

    def __init__(
        self,
        solution_name: str,
        market_fit_score=None,
        technical_feasibility_score=None,
        novelty_score=None,
        seo_scalability_score=None,
        audience_fit=None,
    ):
        self.solution_name = solution_name
        self.market_fit_score = market_fit_score
        self.technical_feasibility_score = technical_feasibility_score
        self.novelty_score = novelty_score
        self.seo_scalability_score = seo_scalability_score
        self.audience_fit = audience_fit


# ---------- compute_solution_scores ----------


class TestComputeSolutionScores:
    def test_empty_list(self):
        assert compute_solution_scores([]) == []

    def test_all_fields_present(self):
        idea = _FakeIdea("Foo", 0.8, 0.6, 0.7, 0.9)
        scores = compute_solution_scores([idea])
        assert len(scores) == 1
        s = scores[0]
        assert s.solution_name == "Foo"
        assert s.market_fit_score == 0.8
        assert s.technical_feasibility_score == 0.6
        assert s.competitive_advantage_score == 0.7  # from novelty_score
        assert s.seo_growth_potential_score == 0.9  # stored raw (display parity)
        # composite uses the provisional-capped seo (0.9 -> 0.7 rank ceiling)
        assert s.composite_score == round((0.8 + 0.6 + 0.7 + 0.7) / 4, 3)
        assert s.rank == 1

    def test_none_optional_fields_stay_none(self):
        """novelty/seo stay None (never fabricated as 0.5); required mf/tf keep
        the 0.5 safety-net default; composite averages the present scores."""
        idea = _FakeIdea("Bar")  # all scores None
        scores = compute_solution_scores([idea])
        s = scores[0]
        assert s.market_fit_score == 0.5
        assert s.technical_feasibility_score == 0.5
        assert s.competitive_advantage_score is None
        assert s.seo_growth_potential_score is None
        assert s.composite_score == 0.5  # mean of the two present scores
        assert s.score_source == 'interactive'

    def test_zero_score_preserved(self):
        """Verifies 0.0 is NOT replaced by 0.5 (the 'x or 0.5' antipattern)."""
        idea = _FakeIdea("Zero", 0.0, 0.0, 0.0, 0.0)
        scores = compute_solution_scores([idea])
        s = scores[0]
        assert s.market_fit_score == 0.0
        assert s.technical_feasibility_score == 0.0
        assert s.competitive_advantage_score == 0.0
        assert s.seo_growth_potential_score == 0.0
        assert s.composite_score == 0.0

    def test_ranking(self):
        ideas = [
            _FakeIdea("Low", 0.2, 0.2, 0.2, 0.2),
            _FakeIdea("High", 0.9, 0.9, 0.9, 0.9),
            _FakeIdea("Mid", 0.5, 0.5, 0.5, 0.5),
        ]
        scores = compute_solution_scores(ideas)
        names_ranked = [s.solution_name for s in scores]
        assert names_ranked == ["High", "Mid", "Low"]
        assert scores[0].rank == 1
        assert scores[1].rank == 2
        assert scores[2].rank == 3

    def test_equal_composite_tiebreak_by_name_regardless_of_input_order(self):
        # 2026-07-10 audit: completion-order tie-breaking made equal-composite results depend
        # on network latency. Equal composites now order by normalized solution_name.
        a_first = [
            _FakeIdea("Alpha", 0.5, 0.5, 0.5, 0.5),
            _FakeIdea("Zebra", 0.5, 0.5, 0.5, 0.5),
        ]
        z_first = [
            _FakeIdea("Zebra", 0.5, 0.5, 0.5, 0.5),
            _FakeIdea("Alpha", 0.5, 0.5, 0.5, 0.5),
        ]
        for ideas in (a_first, z_first):
            scores = compute_solution_scores(ideas)
            assert [s.solution_name for s in scores] == ["Alpha", "Zebra"]


# ---------- backfill_solution_scores ----------


class TestBackfillSolutionScores:
    def test_empty_existing(self):
        """All solutions backfilled when existing_scores is empty."""
        ideas = [_FakeIdea("A", 0.8, 0.7, 0.6, 0.5)]
        result = backfill_solution_scores(None, ideas)
        assert len(result) == 1
        assert result[0].solution_name == "A"
        assert result[0].rank == 1

    def test_partial_overlap(self):
        """Only missing solutions are backfilled."""
        existing = [
            SolutionScores(
                solution_name="Existing",
                market_fit_score=0.9,
                technical_feasibility_score=0.8,
                competitive_advantage_score=0.7,
                seo_growth_potential_score=0.6,
                composite_score=0.75,
                rank=1,
            )
        ]
        ideas = [
            _FakeIdea("Existing", 0.9, 0.8, 0.7, 0.6),
            _FakeIdea("New", 0.4, 0.3, 0.2, 0.1),
        ]
        result = backfill_solution_scores(existing, ideas)
        assert len(result) == 2
        names = {s.solution_name for s in result}
        assert names == {"Existing", "New"}

    def test_all_present_no_change(self):
        """Existing selector composites stay fixed while final idea sub-scores synchronize."""
        existing = [
            SolutionScores(
                solution_name="A",
                market_fit_score=0.9,
                technical_feasibility_score=0.8,
                competitive_advantage_score=0.7,
                seo_growth_potential_score=0.6,
                composite_score=0.75,
                rank=1,
            )
        ]
        ideas = [_FakeIdea("A", 0.55, 0.65, 0.45, 0.50)]
        result = backfill_solution_scores(existing, ideas)
        assert len(result) == 1
        # Task-4's strategic composite/ranking remains the selection decision record.
        assert result[0].composite_score == 0.75
        # Its component ledger must reflect the finalized idea fields shown elsewhere.
        assert result[0].market_fit_score == 0.55
        assert result[0].technical_feasibility_score == 0.65
        assert result[0].competitive_advantage_score == 0.45
        assert result[0].seo_growth_potential_score == 0.50

    def test_reranks(self):
        """After backfill, entire list is re-ranked by composite_score."""
        existing = [
            SolutionScores(
                solution_name="Low",
                market_fit_score=0.2,
                technical_feasibility_score=0.2,
                competitive_advantage_score=0.2,
                seo_growth_potential_score=0.2,
                composite_score=0.2,
                rank=1,  # was rank 1 before backfill
            )
        ]
        ideas = [
            _FakeIdea("Low", 0.2, 0.2, 0.2, 0.2),
            _FakeIdea("High", 0.9, 0.9, 0.9, 0.9),
        ]
        result = backfill_solution_scores(existing, ideas)
        assert result[0].solution_name == "High"
        assert result[0].rank == 1
        assert result[1].solution_name == "Low"
        assert result[1].rank == 2

    def test_equal_composite_tiebreak_by_name_regardless_of_input_order(self):
        # 2026-07-10 audit: completion-order tie-breaking made equal-composite results depend
        # on network latency. Equal composites now order by normalized solution_name.
        a_first = [
            _FakeIdea("Alpha", 0.5, 0.5, 0.5, 0.5),
            _FakeIdea("Zebra", 0.5, 0.5, 0.5, 0.5),
        ]
        z_first = [
            _FakeIdea("Zebra", 0.5, 0.5, 0.5, 0.5),
            _FakeIdea("Alpha", 0.5, 0.5, 0.5, 0.5),
        ]
        for ideas in (a_first, z_first):
            result = backfill_solution_scores(None, ideas)
            assert [s.solution_name for s in result] == ["Alpha", "Zebra"]


# ---------- adjacent-audience composite penalty (PR 10 / S4.1) ----------


class TestAudienceFitCoverage:
    def test_empty_pool_is_zero(self):
        assert audience_fit_coverage([]) == 0.0
        assert audience_fit_coverage(None) == 0.0

    def test_untagged_pool_is_zero(self):
        assert audience_fit_coverage([_FakeIdea("A"), _FakeIdea("B")]) == 0.0

    def test_counts_both_true_and_false_as_covered(self):
        pool = [_FakeIdea("A", audience_fit=True), _FakeIdea("B", audience_fit=False)]
        assert audience_fit_coverage(pool) == 1.0

    def test_partial_coverage_fraction(self):
        pool = [
            _FakeIdea("A", audience_fit=True),
            _FakeIdea("B", audience_fit=False),
            _FakeIdea("C"),
            _FakeIdea("D", audience_fit=True),
        ]
        assert audience_fit_coverage(pool) == 0.75

    def test_reads_dicts_too(self):
        assert audience_fit_coverage([{"audience_fit": False}, {"audience_fit": None}]) == 0.5

    def test_ten_of_ten_clears_the_gate_nine_of_ten_does_not(self):
        full = [_FakeIdea(str(i), audience_fit=True) for i in range(10)]
        assert audience_fit_coverage(full) >= AUDIENCE_FIT_COVERAGE_MIN
        partial = full[:9] + [_FakeIdea("untagged")]
        assert audience_fit_coverage(partial) >= AUDIENCE_FIT_COVERAGE_MIN
        partial_8 = full[:8] + [_FakeIdea("u1"), _FakeIdea("u2")]
        assert audience_fit_coverage(partial_8) < AUDIENCE_FIT_COVERAGE_MIN


def _pool(fits, n=10):
    """A pool of n identically-scored ideas whose audience_fit values come from `fits`
    (padded with None). Identical sub-scores make any composite delta the penalty."""
    fits = list(fits) + [None] * (n - len(fits))
    return [
        _FakeIdea(f"Idea{i:02d}", 0.6, 0.6, 0.6, 0.6, audience_fit=f)
        for i, f in enumerate(fits)
    ]


class TestAudienceFitPenaltyComputeSolutionScores:
    def test_false_penalized_when_coverage_clears_gate(self):
        pool = _pool([False] + [True] * 9)
        by_name = {s.solution_name: s for s in compute_solution_scores(pool)}
        baseline = by_name["Idea01"].composite_score  # audience_fit True
        assert by_name["Idea00"].composite_score == pytest.approx(
            round(baseline - settings.audience_fit_penalty, 3)
        )

    def test_not_penalized_below_coverage_gate(self):
        # 8/10 tagged = 0.80 coverage: the False idea must NOT be penalized, otherwise the
        # two untagged ideas would be stealth-promoted above it.
        pool = _pool([False] + [True] * 7, n=10)
        assert audience_fit_coverage(pool) < AUDIENCE_FIT_COVERAGE_MIN
        by_name = {s.solution_name: s for s in compute_solution_scores(pool)}
        assert by_name["Idea00"].composite_score == by_name["Idea01"].composite_score

    def test_true_and_none_never_penalized(self):
        pool = _pool([True, None] + [True] * 8)
        scores = compute_solution_scores(pool)
        assert len({s.composite_score for s in scores}) == 1

    def test_penalty_does_not_mutate_stored_market_fit_score(self):
        pool = _pool([False] + [True] * 9)
        by_name = {s.solution_name: s for s in compute_solution_scores(pool)}
        assert by_name["Idea00"].market_fit_score == 0.6
        assert pool[0].market_fit_score == 0.6  # the idea object itself is untouched

    def test_zero_setting_disables(self, monkeypatch):
        monkeypatch.setattr(settings, "audience_fit_penalty", 0.0)
        pool = _pool([False] + [True] * 9)
        scores = compute_solution_scores(pool)
        assert len({s.composite_score for s in scores}) == 1

    def test_penalty_reorders_an_otherwise_tied_pool(self):
        pool = _pool([False] + [True] * 9)
        assert compute_solution_scores(pool)[-1].solution_name == "Idea00"


class TestAudienceFitPenaltyBackfill:
    def test_new_entry_branch_applies_penalty(self):
        # The escape hatch: an idea first scored down backfill's new-entry branch.
        pool = _pool([False] + [True] * 9)
        by_name = {s.solution_name: s for s in backfill_solution_scores(None, pool)}
        assert by_name["Idea00"].composite_score == pytest.approx(
            round(by_name["Idea01"].composite_score - settings.audience_fit_penalty, 3)
        )
        assert by_name["Idea00"].market_fit_score == 0.6

    def test_new_entry_branch_respects_coverage_gate(self):
        pool = _pool([False] + [True] * 7, n=10)
        by_name = {s.solution_name: s for s in backfill_solution_scores(None, pool)}
        assert by_name["Idea00"].composite_score == by_name["Idea01"].composite_score

    def test_existing_entry_composite_is_left_alone(self):
        # Existing (selector-sourced) entries keep their composite; only sub-scores sync.
        pool = _pool([False] + [True] * 9)
        existing = [
            SolutionScores(
                solution_name="Idea00",
                market_fit_score=0.1,
                technical_feasibility_score=0.1,
                competitive_advantage_score=0.1,
                seo_growth_potential_score=0.1,
                composite_score=0.77,
                rank=1,
            )
        ]
        by_name = {s.solution_name: s for s in backfill_solution_scores(existing, pool)}
        assert by_name["Idea00"].composite_score == 0.77
        assert by_name["Idea00"].market_fit_score == 0.6  # sub-scores DID sync


class TestAudienceFitPenaltyAngleRankedComposite:
    def test_default_kwarg_applies_no_penalty(self):
        idea = _FakeIdea("A", 0.6, 0.6, 0.6, 0.6, audience_fit=False)
        assert angle_ranked_composite(idea) == angle_ranked_composite(
            _FakeIdea("A", 0.6, 0.6, 0.6, 0.6, audience_fit=True)
        )

    def test_penalty_applied_at_full_coverage(self):
        adjacent = _FakeIdea("A", 0.6, 0.6, 0.6, 0.6, audience_fit=False)
        primary = _FakeIdea("B", 0.6, 0.6, 0.6, 0.6, audience_fit=True)
        assert angle_ranked_composite(adjacent, 1.0) == pytest.approx(
            round(angle_ranked_composite(primary, 1.0) - settings.audience_fit_penalty, 3)
        )

    def test_no_penalty_below_gate(self):
        adjacent = _FakeIdea("A", 0.6, 0.6, 0.6, 0.6, audience_fit=False)
        assert angle_ranked_composite(adjacent, 0.5) == angle_ranked_composite(adjacent)

    def test_true_and_none_unpenalized_at_full_coverage(self):
        base = angle_ranked_composite(_FakeIdea("A", 0.6, 0.6, 0.6, 0.6))
        for fit in (True, None):
            idea = _FakeIdea("A", 0.6, 0.6, 0.6, 0.6, audience_fit=fit)
            assert angle_ranked_composite(idea, 1.0) == base

    def test_works_on_dicts(self):
        d = {
            "market_fit_score": 0.6,
            "technical_feasibility_score": 0.6,
            "novelty_score": 0.6,
            "seo_scalability_score": 0.6,
            "audience_fit": False,
        }
        assert angle_ranked_composite(d, 1.0) == pytest.approx(
            round(angle_ranked_composite(d) - settings.audience_fit_penalty, 3)
        )

    def test_never_goes_negative(self, monkeypatch):
        monkeypatch.setattr(settings, "audience_fit_penalty", 1.0)
        idea = _FakeIdea("A", 0.0, 0.0, 0.0, 0.0, audience_fit=False)
        assert angle_ranked_composite(idea, 1.0) == 0.0


class TestChooseAutoPick:
    """Red-team-killed ideas are ineligible for the AUTOMATIC #1 recommendation.

    Paired with the 2026-08-02 removal of the red-team -> incumbent_parity coupling:
    without the cap a killed idea's score rebounds, and `apply_red_team_downgrade` only
    runs at final report assembly (after selection), so this is the only thing keeping a
    killed idea out of the automatic pick.
    """

    class _Ranked:
        def __init__(self, name):
            self.solution_name = name

    @staticmethod
    def _idea(name, verdict=None, caveats=None):
        return SimpleNamespace(
            solution_name=name, red_team_verdict=verdict, red_team_caveats=caveats
        )

    def test_no_killed_ideas_returns_the_leader_untouched(self):
        ranked = [self._Ranked("A"), self._Ranked("B")]
        ideas = [self._idea("A"), self._idea("B", "weakened", ["soft"])]
        pick, note = choose_auto_pick(ranked, ideas)
        assert pick.solution_name == "A"
        assert note is None

    def test_killed_leader_is_skipped_with_an_attributable_note(self):
        ranked = [self._Ranked("A"), self._Ranked("B"), self._Ranked("C")]
        ideas = [
            self._idea("A", "killed", ["no buyer evidence anywhere"]),
            self._idea("B"),
            self._idea("C"),
        ]
        pick, note = choose_auto_pick(ranked, ideas)
        assert pick.solution_name == "B"
        assert "A" in note and "no buyer evidence anywhere" in note

    def test_killed_non_leader_does_not_disturb_the_pick(self):
        ranked = [self._Ranked("A"), self._Ranked("B")]
        ideas = [self._idea("A"), self._idea("B", "killed", ["dead"])]
        pick, note = choose_auto_pick(ranked, ideas)
        assert pick.solution_name == "A"
        assert note is None

    def test_all_killed_degrades_loudly_instead_of_picking_silently(self):
        ranked = [self._Ranked("A"), self._Ranked("B")]
        ideas = [self._idea("A", "killed", ["refuted"]), self._idea("B", "killed", ["also"])]
        pick, note = choose_auto_pick(ranked, ideas)
        assert pick.solution_name == "A"
        assert "No automatic recommendation" in note

    def test_empty_ranked_list(self):
        assert choose_auto_pick([], [self._idea("A", "killed", ["x"])]) == (None, None)

    def test_reads_dict_ideas(self):
        ranked = [self._Ranked("A"), self._Ranked("B")]
        ideas = [{"solution_name": "A", "red_team_verdict": "killed"}, {"solution_name": "B"}]
        pick, note = choose_auto_pick(ranked, ideas)
        assert pick.solution_name == "B"
        assert note is not None
