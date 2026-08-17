"""A/B the seed CONCEPT PREFILTER call site (`_run_seed_cell`) deterministically.

The prefilter used to be `faithful = [c for c in concepts if is_seed_faithful(seed_text, c)]`
with an `else` branch that DISCARDS every generated concept and mints a RawConcept out of the
pitch. So a wrong refusal here does not "keep the previous candidate" — it CREATES the
pitch-shaped one that shipped to two paying users.

This drives the REAL `_run_seed_cell` with three recorders and no re-implementation:

  * `_one_sample`     -> returns the case's candidate(s) as the generator's output.
  * `_score_concepts` -> no-op (runs strictly after the prefilter; cannot change its verdict).
  * `_tournament_cell`-> records the candidate list it was handed, returns None.

What is measured for every case: did the user's generated candidate REACH the tournament, or was
it replaced by the pitch stub? Run it once before the edit and once after; diff the two files.

Two populations, deliberately kept apart:
  * `corpus`  — the 22 vendored (pitch, candidate) pairs. Idea-shaped, so this measures the
                GATE's verdict, not the shape production hands this site.
  * `live`    — concepts captured from the real generator on the real 03d20ff6 run state
                (`probes/seed_prefilter_capture.py`). Concept-shaped: what the site really sees.

No network. Usage (the crew builder lives in the sibling script, hence PYTHONPATH):
  PYTHONPATH=probes .venv/bin/python probes/seed_prefilter_gate_ab.py [live_capture.json] > file
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from loguru import logger

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils.seed_fidelity import (
    is_seed_faithful,
    seed_fidelity_score,
    seed_retention_floor_ok,
    unpitched_core_dependencies,
)

CORPUS = json.loads(Path("tests/fixtures/seed_identity_corpus.json").read_text())


# The crew is hydrated from the REAL 03d20ff6 checkpoint rather than hand-stubbed. A
# hand-stubbed crew raised inside `_run_seed_cell`'s fail-soft `except` (missing
# `primary_target_segment`) and every case reported "0 flips" from a function that never
# reached the prefilter — trap 3, in the harness built to measure the prefilter. `drive()`
# now also HARD-FAILS on that log line instead of reading it as a verdict.
_CHECKPOINT = ("output/checkpoints/checkpoint_ai_visibility_for_local_businesses_in_london_"
               "find_03d20ff6-3973-48b6-b414-42a71883225d_20260815_153709")
_CREW = None


def crew():
    global _CREW
    if _CREW is None:
        from seed_prefilter_capture import build_crew
        trace = json.loads(Path(
            "output/checkpoints/seed_identity_trace_"
            "03d20ff6-3973-48b6-b414-42a71883225d.json").read_text())
        _CREW = build_crew(_CHECKPOINT, trace["pitch"])
    return _CREW


def drive(pitch: str, generated: list) -> list:
    """Run the real `_run_seed_cell` prefilter over `generated`; return what reached the
    tournament (a list of objects — either the user's candidates or the minted pitch stub)."""
    reached: list = []
    messages: list = []
    real_one_sample = UnifiedSolutionCrew._one_sample
    real_score = UnifiedSolutionCrew._score_concepts
    real_tournament = UnifiedSolutionCrew._tournament_cell
    UnifiedSolutionCrew._one_sample = lambda self, *a, **kw: (list(generated), [])
    UnifiedSolutionCrew._score_concepts = lambda self, concepts, idx=None: []
    UnifiedSolutionCrew._tournament_cell = (
        lambda self, *, cell, candidates, search, usages, skip_selection=False:
        (reached.extend(candidates or []), None)[1])
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="WARNING")
    try:
        crew()._run_seed_cell(seed_text=pitch, dispatch_id="seed", search=None, usages=[])
    finally:
        logger.remove(sink)
        UnifiedSolutionCrew._one_sample = real_one_sample
        UnifiedSolutionCrew._score_concepts = real_score
        UnifiedSolutionCrew._tournament_cell = real_tournament
    failed = [m for m in messages if "[Seed] cell failed" in m]
    if failed:
        raise RuntimeError(f"the harness never reached the prefilter: {failed[0]}")
    return reached


def _is_pitch_stub(obj, pitch: str) -> bool:
    """The minted fallback concept: its one_liner IS the whitespace-collapsed pitch."""
    return (getattr(obj, "one_liner", None) or "") == " ".join((pitch or "").split()).strip()


def run_corpus():
    print(f"{'arm':<12} {'id':<20} {'reaches_tournament':<19} {'pitch_stub':<11} "
          f"{'floor':<6} {'routes':<7} {'old_is_faithful':<16}")
    flips = {"honest": [], "adversarial": []}
    for arm in ("honest", "adversarial"):
        for case in CORPUS[arm]:
            pitch = case["pitch"]
            cand = SimpleNamespace(**case["candidate"])
            floor_ok = seed_retention_floor_ok(pitch, cand)
            routes = bool(unpitched_core_dependencies(pitch, cand))
            old = is_seed_faithful(pitch, cand)
            reached = drive(pitch, [cand])
            got_candidate = any(r is cand for r in reached)
            stub = any(_is_pitch_stub(r, pitch) for r in reached)
            print(f"{arm:<12} {case['id']:<20} {str(got_candidate):<19} {str(stub):<11} "
                  f"{str(floor_ok):<6} {str(routes):<7} {str(old):<16}")
            if got_candidate and not old:
                flips[arm].append(case["id"])
    print()
    for arm in ("honest", "adversarial"):
        print(f"{arm.upper()} cases that flip refused -> reaches-the-tournament: "
              f"{len(flips[arm])} {flips[arm]}")


def run_live(path: str):
    cap = json.load(open(path))
    pitch = cap["pitch"]
    print(f"\n=== LIVE-SHAPED POPULATION ({cap['model']}, real 03d20ff6 run state) ===")
    for i, sample in enumerate(cap["samples"], 1):
        objs = [SimpleNamespace(**{k: v for k, v in row.items()
                                   if k not in ("retained", "total_tokens", "floor",
                                                "retention_ok", "routes", "is_seed_faithful")})
                for row in sample["generated"]]
        reached = drive(pitch, objs)
        stub = any(_is_pitch_stub(r, pitch) for r in reached)
        names = [getattr(r, "concept_name", None) for r in reached]
        ranked = (max(reached, key=lambda c: seed_fidelity_score(pitch, c)) if reached else None)
        print(f"sample {i}: generated={len(objs)}  reached_tournament={len(reached)}  "
              f"pitch_stub={stub}")
        print(f"   candidates: {names}")
        print(f"   the tournament's own fidelity ranking would select: "
              f"{getattr(ranked, 'concept_name', None)!r} "
              f"(seed_fidelity_score={seed_fidelity_score(pitch, ranked):.3f})"
              if ranked is not None else "   (no candidate)")


def main():
    run_corpus()
    if len(sys.argv) > 1:
        run_live(sys.argv[1])


if __name__ == "__main__":
    main()
