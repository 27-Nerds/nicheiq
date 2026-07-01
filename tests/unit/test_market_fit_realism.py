"""market_fit realism rule — bounded critic prompt addition, always on (A/B-validated 2026-07-01).

Attacks the ~+0.13 market_fit over-optimism vs the neutral-Opus panel (harness: calibration_gate.py):
severity is the ceiling, discounted for mechanism / market / linkage; moderate default; reserve 0.7+.
Flag removed after validation — the rule is now unconditional in the critic prompt.
"""

from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _prompt():
    fake = SimpleNamespace(_format_competitor_mentions=lambda: "",
                           pain_point_analysis=SimpleNamespace(pain_points=[]))
    return UnifiedSolutionCrew._calibration_static_prompt(fake)[0]


def test_rule_always_present_and_bounded():
    p = _prompt()
    # ceiling framing + all three discount axes + a reserved high band (bounded, not "score low")
    assert "MARKET_FIT REALISM" in p
    assert "CEILING" in p
    assert "MECHANISM" in p and "MARKET" in p and "LINKAGE" in p
    assert ">= 0.7" in p and "0.45-0.60" in p
