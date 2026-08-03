from datetime import datetime, timedelta

from nicheiq.models.research_state import ResearchState
from nicheiq.report.report_generator import ReportGenerator


def test_stage_timing_summary_omits_interactive_selection_wait() -> None:
    state = ResearchState()
    state.stage_completion_timestamps = {
        "5": datetime(2026, 8, 1, 20, 0, 0),
        "6": datetime(2026, 8, 2, 8, 5, 0),
    }
    state._user_selected_solutions = {"Selected idea"}

    assert ReportGenerator(state)._generate_stage_timing_summary() is None


def test_stage_timing_summary_remains_available_for_continuous_runs() -> None:
    state = ResearchState()
    started = datetime(2026, 8, 2, 8, 0, 0)
    state.stage_completion_timestamps = {
        "5": started,
        "6": started + timedelta(minutes=5),
    }

    summary = ReportGenerator(state)._generate_stage_timing_summary()

    assert summary is not None
    assert summary.total_duration_seconds == 300
    assert summary.stage_durations == {"6": 300}
