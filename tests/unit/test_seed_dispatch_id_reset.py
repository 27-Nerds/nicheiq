"""NIT (outcome-delivery review): `UnifiedSolutionCrew._current_seed_dispatch_id` is set on
the seed-birth path but was never cleared. A reused crew instance would leak a STALE seed
dispatch id onto a later, non-seed run's `ruled_out_pains` entries (each entry stamps
`dispatch_id: getattr(self, "_current_seed_dispatch_id", None)`).

`execute_pipeline`'s per-run reset block (mirroring the existing `ruled_out_pains = []` /
`_tournament_ctx = None` resets there) now also resets it to None.
"""
from types import SimpleNamespace

import pytest

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew_with_stale_dispatch_id():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew._current_seed_dispatch_id = "stale-seed-dispatch-from-prior-run"
    # Triggers execute_pipeline's very first hard-raise (line ~8316-8320), immediately
    # after the reset block runs — no need to mock the rest of the (heavy) pipeline.
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    return crew


class TestExecutePipelineResetsSeedDispatchId:
    def test_reset_clears_stale_dispatch_id_before_the_no_pain_points_raise(self):
        crew = _crew_with_stale_dispatch_id()

        with pytest.raises(ValueError, match="No pain points provided"):
            crew.execute_pipeline()

        assert crew._current_seed_dispatch_id is None
