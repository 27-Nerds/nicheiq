"""EVIDENCE 1 — what is actually POPULATED on a `RawConcept` at `_tournament_cell` ranking time.

Round 23 (S23). The brief proposed ranking the `user_seed` pool by "the critic scores the pool
already carries (`market_fit_score`, `novelty_score`, `build_feasibility_score`, …)". Two of
those three names do not exist on `RawConcept` at all, and whether the third is populated depends
on a live critic call that can fail open. This probe answers the question by MEASURING rather
than reading the model: it replays the captured 03d20ff6 concepts, drives the REAL
`_score_concepts` (the only writer between generation and ranking), and dumps every field's value
before and after.

Two arms:
  * `--static`  no network. Declared model fields, which the generator populated in the capture,
                and which are still at their sentinel/None default. This is the floor: what a
                ranking function can rely on when the critic fails open (`_score_concepts` is
                fail-open per batch by design — see its docstring).
  * `--live`    additionally drives `_score_concepts` REPEATS times per sample and records what
                changed. Critic tier is unsubstituted (`ideation_judge_llm`).

Usage:
  PYTHONPATH=probes .venv/bin/python probes/seed_rank_field_probe.py <capture.json> --static
  PYTHONPATH=probes .venv/bin/python probes/seed_rank_field_probe.py <capture.json> --live <repeats> <out.json>
Redirect to a file; never pipe.
"""
import json
import sys

import nicheiq.utils.seed_fidelity as sf
from nicheiq.models.solution_idea import RawConcept

_CONCEPT_FIELDS = ("concept_name", "one_liner", "project_type", "delivery_format",
                   "target_keywords", "why_non_obvious", "ideation_technique",
                   "data_access_model", "data_acquisition_notes")

# The fields a ranking function could plausibly read. Sentinel -1.0 means "not scored".
_SCORE_FIELDS = ("obviousness_score", "data_feasibility_score", "build_feasibility_score",
                 "data_access_model", "data_acquisition_notes",
                 "critic_already_exists", "critic_no_route")


def build(rows):
    return [RawConcept(**{k: r[k] for k in _CONCEPT_FIELDS if r.get(k) is not None},
                       source_frame="user_seed", source_focus_key="seed") for r in rows]


def _val(c, f):
    v = getattr(c, f, "<ABSENT>")
    return v


def static_arm(cap):
    pitch = cap["pitch"]
    declared = set(RawConcept.model_fields)
    print("=== DECLARED FIELDS ON RawConcept ===")
    print(f"count={len(declared)}")
    for name in ("market_fit_score", "novelty_score", "payability_score",
                 "build_feasibility_score", "data_feasibility_score", "obviousness_score"):
        print(f"  {name:<26} declared={name in declared}")
    print()
    print("=== PER-CONCEPT, AS BUILT FROM THE GENERATOR CAPTURE (no critic yet) ===")
    for i, sample in enumerate(cap["samples"], 1):
        cs = build(sample["generated"])
        ranked = sorted(cs, key=lambda c: -sf.seed_fidelity_score(pitch, c))
        print(f"-- sample{i} ({len(cs)} concepts), fidelity-descending")
        for rank, c in enumerate(ranked, 1):
            fid = sf.seed_fidelity_score(pitch, c)
            vals = " ".join(f"{f.split('_')[0]}={_val(c, f)!r}" for f in _SCORE_FIELDS)
            print(f"  #{rank} {c.concept_name:<30} fidelity={fid:.3f}  {vals}")
        print()
    print("=== SUMMARY: fields at their DEFAULT before the critic runs ===")
    all_cs = [c for s in cap["samples"] for c in build(s["generated"])]
    for f in _SCORE_FIELDS:
        default = RawConcept.model_fields[f].default
        at_default = sum(1 for c in all_cs if getattr(c, f) == default)
        print(f"  {f:<26} default={default!r:<12} at-default {at_default}/{len(all_cs)}")


def live_arm(cap, repeats, out_path):
    from nicheiq.config.settings import settings
    from seed_prefilter_capture import build_crew
    from seed_prefilter_spec_probe import _CHECKPOINT

    pitch = cap["pitch"]
    print(f"critic tier (UNSUBSTITUTED): {settings.ideation_judge_llm}")
    crew = build_crew(_CHECKPOINT, pitch)
    rows = []
    for rep in range(1, repeats + 1):
        for i, sample in enumerate(cap["samples"], 1):
            cs = build(sample["generated"])
            before = [{f: _val(c, f) for f in _SCORE_FIELDS} for c in cs]
            crew._score_concepts(cs, idx=97)
            for c, b in zip(cs, before):
                after = {f: _val(c, f) for f in _SCORE_FIELDS}
                changed = sorted(f for f in _SCORE_FIELDS if b[f] != after[f])
                row = {"rep": rep, "sample": i, "concept": c.concept_name,
                       "fidelity": round(sf.seed_fidelity_score(pitch, c), 4),
                       "before": b, "after": after, "changed": changed}
                rows.append(row)
                print(f"rep{rep} s{i} {c.concept_name:<30} fid={row['fidelity']:.3f} "
                      f"obv={after['obviousness_score']} "
                      f"build={after['build_feasibility_score']} "
                      f"data={after['data_feasibility_score']} "
                      f"access={after['data_access_model']!r} "
                      f"no_route={after['critic_no_route']} "
                      f"exists={after['critic_already_exists']}")
            json.dump({"pitch": pitch, "critic": settings.ideation_judge_llm, "rows": rows},
                      open(out_path, "w"), indent=1)
    print("\n--- SUMMARY: did the critic populate the field? ---")
    for f in _SCORE_FIELDS:
        default = RawConcept.model_fields[f].default
        pop = sum(1 for r in rows if r["after"][f] != default)
        print(f"  {f:<26} populated after the critic: {pop}/{len(rows)}")
    print(f"wrote {out_path}")


def main():
    cap = json.load(open(sys.argv[1]))
    if sys.argv[2] == "--static":
        static_arm(cap)
    else:
        live_arm(cap, int(sys.argv[3]), sys.argv[4])


if __name__ == "__main__":
    main()
