"""Review-3 fixes (2026-07-03): the CLI --stop-after-phase 1 path must produce the preview
report (it was dead code — worker-only), and the preview must carry build_feasibility_score."""

import inspect

from nicheiq.flows.research_flow import ResearchFlow


def test_stop_branch_materializes_and_returns_path():
    src = inspect.getsource(ResearchFlow._execute_remaining_stages)
    # Slice to the END of the stop branch (its `return`), not a fixed character count —
    # a char window silently breaks when anything is inserted inside the branch.
    stop = src.index("Stopping after Phase")
    branch = src[stop:src.index("\n\n", stop)]
    assert "_materialize_preview_report" in branch
    assert 'return preview_path or ""' in branch


def test_preview_emits_build_feasibility():
    src = inspect.getsource(ResearchFlow._materialize_preview_report)
    assert '"build_feasibility_score"' in src
    assert '"data_feasibility_score"' in src
