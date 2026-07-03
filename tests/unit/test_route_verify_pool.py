"""Verification parity (2026-07-03): only per-cell tournament winners get the search-grounded
verify_data_routes at birth — bundles/salvaged/re-injections shipped model-knowledge route
labels (live: a bundle shipped SAM.gov as 'paywalled'). _verify_pool_routes runs the SAME
verifier post-union on everything not birth-verified."""

import inspect
from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.search_tool = None
    crew._run_parallel = lambda fn, jobs, *a, **k: [fn(**j) for j in jobs]
    return crew


def _idea(name):
    return SimpleNamespace(solution_name=name)


class TestVerifyPoolRoutes:
    def test_skips_birth_verified_winners(self):
        crew = _crew()
        crew._birth_verified_names = {"Winner1", "Winner2"}
        seen = []
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=lambda i, g, **kw: seen.append(i.solution_name)):
            crew._verify_pool_routes([_idea("Winner1"), _idea("Bundle1"),
                                      _idea("Winner2"), _idea("Salvaged1")])
        assert seen == ["Bundle1", "Salvaged1"]

    def test_no_tracking_means_verify_everything(self):
        # convergent path never birth-verifies — the parity pass covers the whole pool
        crew = _crew()
        seen = []
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=lambda i, g, **kw: seen.append(i.solution_name)):
            crew._verify_pool_routes([_idea("A"), _idea("B")])
        assert seen == ["A", "B"]

    def test_failsoft_per_idea(self):
        crew = _crew()
        crew._birth_verified_names = set()
        calls = []
        def _boomy(i, g, **kw):
            calls.append(i.solution_name)
            if i.solution_name == "A":
                raise RuntimeError("verifier down")
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=_boomy):
            crew._verify_pool_routes([_idea("A"), _idea("B")])  # must not raise
        assert calls == ["A", "B"]

    def test_all_verified_is_noop(self):
        crew = _crew()
        crew._birth_verified_names = {"A"}
        with patch("nicheiq.crews.idea_improvement_loop_v4.verify_data_routes",
                   side_effect=AssertionError("must not run")):
            crew._verify_pool_routes([_idea("A")])


class TestPipelineWiring:
    def test_winners_tracked_before_salvage_and_bundles(self):
        src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
        assert src.index("_birth_verified_names") < src.index("_salvage_cell_losers(")

    def test_verify_runs_after_feasibility_before_dev_time(self):
        # 'blocked' caps build_feasibility (must not be overwritten by _finalize_feasibility);
        # dev-time and the calibration critic read the route label (must see the verified one).
        src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
        assert src.index("_finalize_feasibility(") < src.index("_verify_pool_routes(")
        assert src.index("_verify_pool_routes(") < src.index("_finalize_dev_time(")
