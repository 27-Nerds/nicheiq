"""Phase 3 — market sizing scoped to the addressed pain slice.

Covers: token-overlap pain scoping, the qualitative scope note, banded severity/WTP (no raw 0-1
leak), and graceful fallback when nothing matches.
"""

from types import SimpleNamespace

import pytest

from nicheiq.crews.market_sizing_crew import MarketSizingCrew


def _pain(title, categories=None, description="", severity=0.8, wtp=0.6):
    return SimpleNamespace(
        title=title,
        categories=categories or [],
        description=description,
        severity_score=severity,
        commercial_intent=wtp,
    )


def _analysis(pains, total_mentions=500):
    return SimpleNamespace(pain_points=pains, total_mentions=total_mentions)


def _solution(addressed):
    return SimpleNamespace(pain_points_addressed=addressed)


@pytest.fixture
def crew():
    return MarketSizingCrew()


PAINS = [
    _pain("Anti-cheat systems fail to stop cheaters", ["fairness"], "ranked matches ruined by cheating"),
    _pain("Matchmaking queue times are too long", ["matchmaking"], "waiting ten minutes for a match"),
    _pain("Toxic teammate harassment in voice chat", ["community"], "verbal abuse over comms"),
]


class TestScopePainsToSolution:
    def test_matches_addressed_pain_by_token_overlap(self, crew):
        scoped = crew._scope_pains_to_solution(PAINS, ["cheating and anti-cheat enforcement"])
        titles = [p.title for p in scoped]
        assert "Anti-cheat systems fail to stop cheaters" in titles
        assert "Matchmaking queue times are too long" not in titles

    def test_multiple_addressed_strings_union(self, crew):
        scoped = crew._scope_pains_to_solution(
            PAINS, ["anti-cheat cheaters", "matchmaking queue waiting times"]
        )
        assert len(scoped) == 2

    def test_no_overlap_returns_empty(self, crew):
        scoped = crew._scope_pains_to_solution(PAINS, ["billing invoice tax compliance"])
        assert scoped == []

    def test_empty_addressed_returns_empty(self, crew):
        assert crew._scope_pains_to_solution(PAINS, []) == []


class TestFormatPainSignalsScoping:
    def test_scopes_and_adds_note(self, crew):
        out = crew._format_pain_signals(_analysis(PAINS), _solution(["anti-cheat cheaters"]))
        assert "**Scope:**" in out
        assert "1 of 3 validated pains" in out
        assert "Pain Points In Scope:** 1" in out

    def test_no_match_falls_back_to_niche(self, crew):
        out = crew._format_pain_signals(_analysis(PAINS), _solution(["billing invoice tax"]))
        assert "**Scope:**" not in out  # nothing matched → no false scoping
        assert "Pain Points In Scope:** 3" in out

    def test_no_raw_decimals_in_output(self, crew):
        out = crew._format_pain_signals(_analysis(PAINS), _solution(["anti-cheat cheaters"]))
        import re
        assert not re.search(r"\d\.\d", out)  # severity/WTP banded, not 0.80
        assert "severity:" in out and "willingness-to-pay:" in out

    def test_no_solution_is_niche_wide(self, crew):
        out = crew._format_pain_signals(_analysis(PAINS), None)
        assert "**Scope:**" not in out
        assert "Pain Points In Scope:** 3" in out
