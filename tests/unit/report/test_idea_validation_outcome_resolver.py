from __future__ import annotations

import json
from pathlib import Path

from nicheiq.report.idea_validation_block import resolve_idea_validation_outcome

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "oc1_historical_contradictions.json"


def _historical_blocks() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_historical_killed_blocks_resolve_to_premise_unproven() -> None:
    fixtures = _historical_blocks()

    assert len(fixtures) == 2
    for fixture in fixtures:
        assert fixture["source_file"].startswith("output/checkpoints/preview_report_")
        assert fixture["json_path"] == "/idea_validation"
        block = fixture["block"]
        outcome, headline = resolve_idea_validation_outcome(
            idea_name=block["idea_name"],
            demoted=block["seed_candidate_status"] != "active",
            parity_raw=block["incumbent_parity"],
            unanchored=block["unanchored_hypothesis"],
            red_team_verdict=block["red_team_verdict"],
            refinement_present=block["refinement"] is not None,
            brief_parity_hit=bool(block["original_mechanism_parity"]),
        )

        assert outcome == "premise_unproven"
        assert "adversarial review could not confirm the premise" in headline


def test_vendored_fields_match_the_recorded_source_when_local_corpus_is_present() -> None:
    repository_root = Path(__file__).parents[3]

    for fixture in _historical_blocks():
        source = repository_root / fixture["source_file"]
        if not source.exists():
            continue
        actual = json.loads(source.read_text(encoding="utf-8"))["idea_validation"]
        assert {key: actual.get(key) for key in fixture["block"]} == fixture["block"]


def test_outcome_precedence_keeps_red_team_below_demotion_and_parity() -> None:
    common = {
        "idea_name": "Example",
        "unanchored": False,
        "red_team_verdict": "killed",
        "refinement_present": False,
        "brief_parity_hit": False,
    }

    demoted, _ = resolve_idea_validation_outcome(**common, demoted=True, parity_raw="none found")
    occupied, _ = resolve_idea_validation_outcome(
        **common, demoted=False, parity_raw="shipped by Vendor: evidence"
    )

    assert demoted == "ruled_out"
    assert occupied == "occupied"
