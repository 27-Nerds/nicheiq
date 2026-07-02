"""Regen critic scoreboard (2026-07-02): quality feedback for 'generate more ideas' runs.

The regen directive previously gave only diversity feedback (blacklist + angle map) — a
regen ideator couldn't tell a 0.70 verified-route winner from a 0.35 feasibility
hallucination. The scoreboard adds per-idea critic scores + market_fit reasons (soft
feedback, not the rubric). Legacy checkpoints without scores render byte-identically.
"""

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew(existing):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.existing_ideas = existing
    return crew


NOTES = ("market_fit: Addresses high-severity financial pain with a verified mechanism "
         "(BLS wages + USDA directory). | technical_feasibility: All data confirmed | "
         "novelty: Closest existing: generic calculators")


class TestCriticReason:
    def test_extracts_market_fit_segment(self):
        r = UnifiedSolutionCrew._critic_reason(NOTES)
        assert r.startswith("Addresses high-severity financial pain")
        assert "technical_feasibility" not in r

    def test_other_criterion(self):
        assert UnifiedSolutionCrew._critic_reason(NOTES, "novelty").startswith("Closest existing")

    def test_absent_and_malformed(self):
        assert UnifiedSolutionCrew._critic_reason(None) == ""
        assert UnifiedSolutionCrew._critic_reason("free text without segments") == ""

    def test_truncation(self):
        long = "market_fit: " + "x" * 400
        r = UnifiedSolutionCrew._critic_reason(long)
        assert len(r) <= 171 and r.endswith("…")


class TestScoreboard:
    def test_legacy_ideas_without_scores_render_nothing(self):
        crew = _crew([{"name": "OldIdea", "description": "d"}])
        assert crew._format_scoreboard() == ""
        # regen directive still renders (angle map), just without the scoreboard
        d = crew._format_regeneration_directive()
        assert "CRITIC SCOREBOARD" not in d and "REGENERATION" in d

    def test_scored_ideas_sorted_desc_with_reasons(self):
        crew = _crew([
            {"name": "WeakIdea", "market_fit_score": 0.35,
             "calibration_notes": "market_fit: unverifiable telemetry route"},
            {"name": "StrongIdea", "market_fit_score": 0.70, "calibration_notes": NOTES},
        ])
        s = crew._format_scoreboard()
        assert s.index("StrongIdea") < s.index("WeakIdea")  # sorted by score desc
        assert "[0.70]" in s and "[0.35]" in s
        assert "unverifiable telemetry route" in s
        assert "Do NOT parrot" in s  # anti-gaming instruction present

    def test_mixed_pool_only_scored_listed(self):
        crew = _crew([
            {"name": "Scored", "market_fit_score": 0.6, "calibration_notes": NOTES},
            {"name": "Unscored"},
        ])
        s = crew._format_scoreboard()
        assert "Scored" in s and "Unscored" not in s

    def test_directive_prepends_scoreboard(self):
        crew = _crew([{"name": "A", "market_fit_score": 0.5, "calibration_notes": NOTES,
                       "description": ""}])
        d = crew._format_regeneration_directive()
        assert d.index("CRITIC SCOREBOARD") < d.index("REGENERATION — Explore NEW ANGLES")

    def test_first_generation_empty(self):
        assert _crew([])._format_regeneration_directive() == ""
