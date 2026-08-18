"""Provenance for the pivot records the frontend clamp spec renders.

`frontend/src/lib/components/__tests__/ValidationVerdict.pivotClamp.test.ts` needs a pivot
record carrying LONG text — the `rejected_pitch` and `changes` values that used to be cut at
`[:160]` / `[:200]` in `research_flow._attempt_validate_pivot` and are now stored verbatim
and clamped by CSS instead. The graded block already vendored for that spec carries
`outcome: not_attempted`, so it has neither field.

Two frontend guards constrain where the records may come from:

* `noEscapingTestImports.test.ts` — a spec may not import anything resolving outside
  `frontend/src/`, so the records cannot be read from `tests/fixtures/` at test time. They
  are VENDORED into `__tests__/fixtures/pivotClampText.captured.json`, recording the source
  file and JSON path for each value, per that guard's own prescription.
* `ValidationVerdict.refusedCards.test.ts` — a spec may not hand-author a value the pipeline
  owns; it must derive it from a vendored fixture.

A vendored copy with no drift guard is a hand-maintained copy with a longer fuse, which is
the failure both guards exist to prevent. This test is the guard: it rebuilds the vendored
JSON from the producer-generated blocks under `tests/fixtures/idea_check_states/` (emitted by
`tests/unit/report/fixture_idea_check_states.py`) and fails the moment the two disagree.
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STATES_DIR = REPO_ROOT / "tests" / "fixtures" / "idea_check_states"
VENDORED_PATH = (
    REPO_ROOT / "frontend" / "src" / "lib" / "components" / "__tests__" / "fixtures"
    / "pivotClampText.captured.json"
)

# Which captured run supplies which record, and WHY that one. Both are chosen for the length
# of the field under test — a short value would let a truncating renderer pass.
SOURCES = [
    (
        "rejected",
        "shipped_idexx_weakened",
        "A REJECTED pivot as the pipeline persisted it while the [:160] slice was live — "
        "`rejected_pitch` is exactly 160 characters for that reason, so this record is a "
        "specimen of the defect the clamp replaces. Long enough that the renderer must fold "
        "it, and the spec asserts every character still reaches the DOM.",
    ),
    (
        "accepted",
        "pivot_accepted_teamsnap",
        "An ACCEPTED pivot: `changes` is 175 characters of real innovation-angle prose (under "
        "the old [:200] cap, so it was never cut) — the value the 'Changed' cell has to clamp "
        "rather than truncate.",
    ),
]


def build_vendored() -> list[dict]:
    records = []
    for key, slug, why in SOURCES:
        src = STATES_DIR / f"{slug}.block.generated.json"
        pivot = json.loads(src.read_text())["pivot"]
        records.append({
            "why": why,
            "file": str(src.relative_to(REPO_ROOT)),
            "path": ".pivot",
            "key": key,
            "value": pivot,
        })
    return records


def test_vendored_pivot_records_match_the_generated_blocks():
    generated = build_vendored()

    if os.environ.get("IDEA_VALIDATION_FIXTURE_REGEN"):
        VENDORED_PATH.parent.mkdir(parents=True, exist_ok=True)
        VENDORED_PATH.write_text(
            json.dumps(generated, indent=1, ensure_ascii=False) + "\n")

    assert json.loads(VENDORED_PATH.read_text()) == generated, (
        f"The pivot records the frontend clamp spec renders ({VENDORED_PATH.name}) have "
        "drifted from the producer-generated blocks. Regenerate:\n  "
        f"IDEA_VALIDATION_FIXTURE_REGEN=1 pytest tests/unit/flows/{Path(__file__).name}\n"
        "Do NOT hand-edit the JSON."
    )


def test_the_vendored_records_still_carry_text_long_enough_to_clamp():
    """The clamp spec's premise. If a recapture shortened these fields, the frontend
    assertions would keep passing while testing nothing — the vacuous-pass mode the block
    fixtures exist to end."""
    by_key = {r["key"]: r["value"] for r in build_vendored()}
    assert len(by_key["rejected"]["rejected_pitch"] or "") > 120
    assert len(by_key["accepted"]["changes"] or "") > 120
