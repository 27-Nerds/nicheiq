"""
Tests for the batched attempt-1 keyword validation pre-pass (Phase 2, DataForSEO
cost optimization): one expand_keywords call covers ALL solutions instead of
one call per solution.
"""

from unittest.mock import MagicMock

import nicheiq.flows.research_flow as rf_module
from nicheiq.flows.research_flow import ResearchFlow


class _FlowStub:
    """Borrows the real method; CrewAI's Flow.state property is read-only,
    so a full ResearchFlow instance can't be stubbed directly."""

    _batched_attempt_one_validation = ResearchFlow._batched_attempt_one_validation
    # 4.2: the thin-slice fallback now prefilters the cross-solution pool
    _prefilter_fallback_keywords = ResearchFlow._prefilter_fallback_keywords


def _make_flow():
    flow = _FlowStub()
    flow.state = MagicMock()
    flow.dataforseo_tool = MagicMock()
    return flow


def _patch_collaborators(monkeypatch, seeds_by_solution, expanded, relevance=0.8):
    """Patch SeedGenerator / find_solution_by_name / check_keyword_relevance."""

    def fake_seed_generator(**kwargs):
        gen = MagicMock()

        def generate(solution, attempt, count=20):
            return seeds_by_solution.get(solution.name, [])

        gen.generate_seeds_with_strategy.side_effect = generate
        gen.calculate_validation_from_expansion.side_effect = (
            lambda kws, name, original_seed_count=0: {
                "solution_name": name,
                "keyword_demand_score": 0.6,
                "validated_count": len(kws),
            }
        )
        return gen

    def fake_find_solution(name, _ideas):
        solution = MagicMock()
        solution.name = name
        # 4.2 prefilter corpus fields must be real strings/lists (MagicMock attrs break
        # the deterministic token-overlap corpus build)
        solution.solution_name = name
        solution.value_proposition = f"{name} invoicing tool for freelancers"
        solution.pain_points_addressed = []
        solution.winning_angle = ""
        return solution

    monkeypatch.setattr(rf_module, "SeedGenerator", fake_seed_generator)
    monkeypatch.setattr(rf_module, "find_solution_by_name", fake_find_solution)
    monkeypatch.setattr(
        rf_module,
        "check_keyword_relevance",
        lambda kws, solution, niche_context=None, audience_vocabulary=None, validation_cache=None: (
            relevance,
            [kw for kw in kws[:3]],
            [],
        ),
    )


class TestBatchedAttemptOneValidation:
    def test_single_expand_call_for_all_solutions(self, monkeypatch):
        flow = _make_flow()
        expanded = [
            {"keyword": "alpha invoicing tool", "search_volume": 500},
            {"keyword": "beta expense tracker", "search_volume": 300},
        ]
        flow.dataforseo_tool.expand_keywords.return_value = expanded
        _patch_collaborators(
            monkeypatch,
            seeds_by_solution={
                "Alpha": ["alpha invoicing", "alpha billing"],
                "Beta": ["beta expenses", "beta receipts"],
            },
            expanded=expanded,
        )

        states = flow._batched_attempt_one_validation(["Alpha", "Beta"], audience_vocab=None)

        # THE optimization: exactly one expansion call for both solutions
        assert flow.dataforseo_tool.expand_keywords.call_count == 1
        assert set(states.keys()) == {"Alpha", "Beta"}
        for state in states.values():
            assert state["validation_result"]["keyword_demand_score"] == 0.6
            assert state["relevance_score"] == 0.8
            assert state["good_keywords"]

    def test_batched_seeds_are_deduplicated(self, monkeypatch):
        flow = _make_flow()
        flow.dataforseo_tool.expand_keywords.return_value = [
            {"keyword": "shared seed tool", "search_volume": 100}
        ]
        _patch_collaborators(
            monkeypatch,
            seeds_by_solution={
                "Alpha": ["shared seed", "alpha only"],
                "Beta": ["shared seed", "beta only"],
            },
            expanded=[],
        )

        flow._batched_attempt_one_validation(["Alpha", "Beta"], audience_vocab=None)

        sent_seeds = flow.dataforseo_tool.expand_keywords.call_args.kwargs["seed_keywords"]
        assert len(sent_seeds) == len({s.lower() for s in sent_seeds})  # no duplicates
        assert "shared seed" in [s.lower() for s in sent_seeds]

    def test_batch_failure_returns_empty_for_fallback(self, monkeypatch):
        """API failure → empty dict, callers fall back to per-solution attempt 1."""
        flow = _make_flow()
        flow.dataforseo_tool.expand_keywords.side_effect = RuntimeError("API down")
        _patch_collaborators(
            monkeypatch,
            seeds_by_solution={"Alpha": ["alpha seed one", "alpha seed two"]},
            expanded=[],
        )

        states = flow._batched_attempt_one_validation(["Alpha"], audience_vocab=None)
        assert states == {}

    def test_no_seeds_skips_api_call(self, monkeypatch):
        flow = _make_flow()
        _patch_collaborators(monkeypatch, seeds_by_solution={}, expanded=[])

        states = flow._batched_attempt_one_validation(["Alpha"], audience_vocab=None)
        assert states == {}
        assert flow.dataforseo_tool.expand_keywords.call_count == 0
