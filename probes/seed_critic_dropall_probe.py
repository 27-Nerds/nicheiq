"""D-3: how often does the seed cell's critic drop EVERY concept?

Removing the concept prefilter (S21) means real generated concepts now pass through
`_score_concepts`, and `_tournament_cell` drops any concept marked `critic_no_route` or
`data_access_model == 'blocked'`. If it drops all of them the cell returns None, the pipeline
stamps `generation_produced_no_candidate`, and the user gets a DISCLOSED refusal. That terminal
state was reachable before only when the generator returned nothing; nobody had measured how
often the critic can now produce it.

Replays the captured 03d20ff6 concepts (`probes/seed_prefilter_capture.py`) through the REAL
`_score_concepts` — no re-implementation — and applies `_tournament_cell`'s own usable filter.

Usage:
  PYTHONPATH=probes .venv/bin/python probes/seed_critic_dropall_probe.py <capture.json> <repeats>
Redirect to a file; never pipe.
"""
import json
import sys

from nicheiq.models.solution_idea import RawConcept
from seed_prefilter_capture import build_crew
from seed_prefilter_spec_probe import _CHECKPOINT, _CONCEPT_FIELDS


def usable(concepts):
    """`_tournament_cell`'s own pre-rank filter, quoted not paraphrased."""
    return [c for c in concepts
            if not getattr(c, "critic_no_route", False)
            and (getattr(c, "data_access_model", None) or "").strip().lower() != "blocked"]


def main():
    cap = json.load(open(sys.argv[1]))
    repeats = int(sys.argv[2])
    pitch = cap["pitch"]
    crew = build_crew(_CHECKPOINT, pitch)
    print(f"critic model (unsubstituted production tier for _score_concepts)")
    drop_all = 0
    total = 0
    for rep in range(1, repeats + 1):
        for i, sample in enumerate(cap["samples"], 1):
            concepts = [RawConcept(**{k: r[k] for k in _CONCEPT_FIELDS if r.get(k) is not None},
                                   source_frame="user_seed", source_focus_key="seed")
                        for r in sample["generated"]]
            crew._score_concepts(concepts, idx=97)
            kept = usable(concepts)
            total += 1
            if not kept:
                drop_all += 1
            print(f"rep{rep} sample{i}: {len(kept)}/{len(concepts)} usable "
                  f"-> {'CELL RETURNS None (generation_produced_no_candidate)' if not kept else 'ok'}")
            for c in concepts:
                print(f"    {c.concept_name:<28} no_route={getattr(c, 'critic_no_route', None)} "
                      f"exists={getattr(c, 'critic_already_exists', None)} "
                      f"access={getattr(c, 'data_access_model', None)!r} "
                      f"obv={getattr(c, 'obviousness_score', None)}")
    print(f"\nDROP-ALL: {drop_all}/{total} cell runs would return None")


if __name__ == "__main__":
    main()
