"""Tests for nicheiq.utils.score_helpers."""

import pytest

from nicheiq.models.solution_selection import SolutionScores
from nicheiq.utils.score_helpers import backfill_solution_scores, compute_solution_scores


class _FakeIdea:
    """Minimal stand-in for BaseSolutionIdea with configurable score fields."""

    def __init__(
        self,
        solution_name: str,
        market_fit_score=None,
        technical_feasibility_score=None,
        novelty_score=None,
        seo_scalability_score=None,
    ):
        self.solution_name = solution_name
        self.market_fit_score = market_fit_score
        self.technical_feasibility_score = technical_feasibility_score
        self.novelty_score = novelty_score
        self.seo_scalability_score = seo_scalability_score


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
        assert s.seo_growth_potential_score == 0.9
        assert s.composite_score == round((0.8 + 0.6 + 0.7 + 0.9) / 4, 3)
        assert s.rank == 1

    def test_none_fields_default_to_05(self):
        idea = _FakeIdea("Bar")  # all scores None
        scores = compute_solution_scores([idea])
        s = scores[0]
        assert s.market_fit_score == 0.5
        assert s.technical_feasibility_score == 0.5
        assert s.competitive_advantage_score == 0.5
        assert s.seo_growth_potential_score == 0.5
        assert s.composite_score == 0.5

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
        """No backfill when all solutions already scored."""
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
        ideas = [_FakeIdea("A", 0.9, 0.8, 0.7, 0.6)]
        result = backfill_solution_scores(existing, ideas)
        assert len(result) == 1
        # Original scores preserved (not recomputed)
        assert result[0].composite_score == 0.75

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
