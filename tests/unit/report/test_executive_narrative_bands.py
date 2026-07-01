"""Executive-narrative band policy: the verdict prose must name criteria qualitatively and never
leak a raw 0-1 score / percentage (Phase 0 of the post-selection deep-research band work)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicheiq.report.report_generator import ReportGenerator


@pytest.fixture
def generator():
    return ReportGenerator(MagicMock())


def _nar(tagline, core, verdict):
    return SimpleNamespace(tagline=tagline, core_value_prop=core, verdict_rationale=verdict)


_SOL = SimpleNamespace(solution_name="X")
_PP = SimpleNamespace(title="P")


class TestExecutiveNarrativeBandPolicy:
    def test_band_with_keyword_accepted(self, generator):
        n = _nar("X automates payroll for SMBs",
                 "It solves the payroll pain. It automates the busywork.",
                 "Strong market fit and good feasibility make this promising.")
        assert generator._validate_executive_narrative(n, _SOL, _PP) is True

    def test_decimal_in_verdict_rejected(self, generator):
        n = _nar("X automates payroll", "It solves payroll.",
                 "With market fit of 0.82 this is strong.")
        assert generator._validate_executive_narrative(n, _SOL, _PP) is False

    def test_percentage_in_tagline_rejected(self, generator):
        n = _nar("X cuts costs 40% with good market fit", "It solves payroll.",
                 "Good market fit and strong feasibility.")
        assert generator._validate_executive_narrative(n, _SOL, _PP) is False

    def test_no_criterion_keyword_rejected(self, generator):
        # anti-hallucination guard preserved: prose with no criterion reference is rejected
        n = _nar("X automates payroll", "It solves payroll.",
                 "This looks like a promising opportunity overall.")
        assert generator._validate_executive_narrative(n, _SOL, _PP) is False
