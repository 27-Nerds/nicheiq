"""EVIDENCE 3 — the CORPUS A/B for the `user_seed` cell's RANKING site, honest and adversarial.

Round 23 (S23). The changed site is `_tournament_cell`'s pre-rank for a `user_seed` cell. It
takes a POOL and returns one member; the vendored corpus is a list of (pitch, candidate) PAIRS,
so a case-by-case walk cannot exercise a ranking at all. What the corpus CAN supply is real
pools: several of its pitches carry more than one case, and two of those mix an honest candidate
with adversarial ones. Those are the pools this drives.

Two arms over the same pools:
  * OLD  `max(pool, key=(seed_fidelity_score, -obviousness))` — the shipped selector, quoted.
  * NEW  the REAL `_expand_seed_until_judged`, driven — not a re-implementation of it (trap 18:
         a control must run the function the subject runs). `_refine_single_concept` is replaced
         by the corpus candidate the concept stands for, so the refine step is held constant and
         this measures the RANKING in isolation. The judge is the real one, memoised per case so
         a repeat is not re-billed.

STOP-RULE READING. "An adversarial case flipping refused -> accepted" cannot happen at a
selection site: the walk advances past a member only when the birth judge REFUSED it, and
selects a member only when the judge ACCEPTED it. The judge is downstream and unchanged, so the
set of candidates that can ship is unchanged; only which one is offered changes. What IS
reported here, pool by pool, is every case where the two arms select different members and
whether the newly-selected member is honest or adversarial.

Judge is `report_structured_llm` (unsubstituted). No refine tier is used, so no model
substitution applies to this measurement.

Usage:
  PYTHONPATH=probes .venv/bin/python probes/seed_rank_corpus_ab.py <repeats> <cap> <out.json>
Redirect to a file; never pipe.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from loguru import logger
import nicheiq.utils.seed_fidelity as sf
from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew

CORPUS = json.loads(Path("tests/fixtures/seed_identity_corpus.json").read_text())


def crew():
    c = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    c.cost_tracker = None
    c.niche_context = SimpleNamespace(niche_description="")
    c.allowed_project_types = None
    c._monetization_directive = ""
    c._divergent_usages = []
    c._seed_judge_unavailable = False
    return c


def candidate_of(case):
    cand = SimpleNamespace(**case["candidate"])
    for attr in ("solution_name", "delivery_format", "novelty_score", "market_fit_score",
                 "technical_feasibility_score", "value_proposition", "short_description",
                 "obviousness_score"):
        if not hasattr(cand, attr):
            setattr(cand, attr, None)
    cand._corpus_id = case["id"]
    return cand


def _obv(c):
    """`_tournament_cell`'s own reader, quoted rather than paraphrased."""
    o = getattr(c, "obviousness_score", -1.0)
    return o if isinstance(o, (int, float)) and o >= 0 else 0.5


def concept_for(case):
    """A `RawConcept`-shaped stand-in whose name identifies the corpus case it expands to."""
    return SimpleNamespace(
        concept_name=f"concept-{case['id']}", one_liner=case["pitch"], project_type="other",
        delivery_format="other", target_keywords=["k"], why_non_obvious="",
        mechanism_tag=None, data_source_tag=None, journey_tag=None,
        obviousness_score=-1.0, data_feasibility_score=-1.0, build_feasibility_score=-1.0,
        data_access_model=None, data_acquisition_notes=None, source_pain=None)


def main():
    repeats, cap, out_path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    print(f"judge (unsubstituted) = {settings.report_structured_llm}  repeats={repeats} cap={cap}")
    print("no refine tier is used — this isolates the RANKING\n")
    c = crew()

    # TRAP 4, and this harness hit it on its first run. Two corpus cases are token-bag
    # reconstructions from a log, and the fixture marks them `judge_eval: false` with the reason
    # ("a word salad is not the same product … judging it would measure the fixture, not the
    # judge"). The first version of this script fed `7703f811` to the judge, collected a 3/3
    # refusal, and reported the run's ONLY selection change on the strength of it. Honour the
    # fixture's own exclusion: a case the corpus says the judge cannot rule on is not a pool
    # member for a judge-gated selector.
    excluded, pools = [], {}
    for arm in ("honest", "adversarial"):
        for case in CORPUS[arm]:
            if case.get("judge_eval") is False:
                excluded.append(case["id"])
                continue
            pools.setdefault(case["pitch"], []).append((arm, case))
    print(f"excluded by the fixture's own `judge_eval: false`: {excluded}\n")

    verdict_cache = {}
    real_refine = UnifiedSolutionCrew._refine_single_concept
    real_judge = UnifiedSolutionCrew._semantic_seed_identity_matches
    real_cap = usc._SEED_RANK_MAX_REFINEMENTS

    def judged(pitch, case):
        # THE REAL judge, captured BEFORE the class attribute is swapped. The first version of
        # this line read `UnifiedSolutionCrew._semantic_seed_identity_matches` at call time,
        # which by then WAS the driver — infinite recursion, absorbed by
        # `_expand_seed_until_judged`'s own fail-soft `except`, and the whole run reported
        # "0 pools changed" from a walk that never reached a verdict. Trap 3, fifth instance,
        # inside the harness built to measure the thing trap 3 is about. The `failed_soft`
        # guard below is the other half of trap 3's remedy: a harness that drives a fail-soft
        # function must ASSERT it did not fail soft.
        key = (pitch, case["id"])
        if key not in verdict_cache:
            vs = [bool(real_judge(c, pitch, candidate_of(case))) for _ in range(repeats)]
            verdict_cache[key] = vs
        vs = verdict_cache[key]
        return max(set(vs), key=vs.count), vs

    failed_soft = []
    logger.add(lambda m: failed_soft.append(m.record["message"])
               if "in-cell identity pre-check" in m.record["message"] else None,
               level="WARNING")

    rows = []
    for pitch, members in pools.items():
        if len(members) < 2:
            continue
        by_id = {case["id"]: (arm, case) for arm, case in members}
        keyed = sorted(
            ((sf.seed_fidelity_score(pitch, candidate_of(case)), -_obv(candidate_of(case)), i,
              arm, case) for i, (arm, case) in enumerate(members)),
            key=lambda t: (-t[0], -t[1], t[2]))
        old_case = keyed[0][4]
        old_arm = keyed[0][3]

        walked = []

        def fake_refine(self, concept, pain, **kw):
            return candidate_of(by_id[concept.concept_name.split("concept-", 1)[1]][1])

        def driven_judge(self, seed, candidate, evidence=None):
            arm, case = by_id[candidate._corpus_id]
            maj, vs = judged(seed, case)
            walked.append({"id": case["id"], "arm": arm, "judge": vs, "majority": maj})
            return maj

        UnifiedSolutionCrew._refine_single_concept = fake_refine
        UnifiedSolutionCrew._semantic_seed_identity_matches = driven_judge
        usc._SEED_RANK_MAX_REFINEMENTS = cap
        try:
            _idea, picked = c._expand_seed_until_judged(
                [concept_for(case) for *_x, case in keyed],
                seed_text=pitch, focus=None, anchor_pain_titles=[], cell_segment_name=None)
        finally:
            UnifiedSolutionCrew._refine_single_concept = real_refine
            UnifiedSolutionCrew._semantic_seed_identity_matches = real_judge
            usc._SEED_RANK_MAX_REFINEMENTS = real_cap

        if failed_soft:
            raise RuntimeError(
                "`_expand_seed_until_judged` failed soft — this run measured nothing: "
                + failed_soft[0])
        if not walked:
            raise RuntimeError("the walk recorded no judge verdict — nothing was measured")
        new_arm, new_case = by_id[picked.concept_name.split("concept-", 1)[1]]
        row = {
            "pitch": pitch[:70],
            "members": [{"id": cs["id"], "arm": a,
                         "fidelity": round(sf.seed_fidelity_score(pitch, candidate_of(cs)), 4)}
                        for _, _, _, a, cs in keyed],
            "old_pick": {"id": old_case["id"], "arm": old_arm},
            "new_pick": {"id": new_case["id"], "arm": new_arm},
            "changed": old_case["id"] != new_case["id"],
            "walked": walked,
        }
        rows.append(row)
        print(f"PITCH {pitch[:58]!r}")
        for m in row["members"]:
            print(f"    {m['arm']:<12} {m['id']:<20} fidelity={m['fidelity']:.3f}")
        print(f"  OLD picks {old_arm}/{old_case['id']}   NEW picks {new_arm}/{new_case['id']}   "
              f"{'CHANGED' if row['changed'] else 'same'}")
        for w in walked:
            print(f"    walked {w['arm']:<12} {w['id']:<20} judge={w['judge']} -> {w['majority']}")
        print()
        json.dump({"judge": settings.report_structured_llm, "repeats": repeats, "cap": cap,
                   "excluded": excluded, "rows": rows}, open(out_path, "w"), indent=1)

    print("--- SUMMARY, ARMS REPORTED SEPARATELY ---")
    changed = [r for r in rows if r["changed"]]
    print(f"pools measured: {len(rows)}  selection changed: {len(changed)}")
    for r in changed:
        print(f"  {r['old_pick']['arm']}/{r['old_pick']['id']} -> "
              f"{r['new_pick']['arm']}/{r['new_pick']['id']}")
    to_adv = [r for r in changed if r["new_pick"]["arm"] == "adversarial"]
    to_hon = [r for r in changed if r["new_pick"]["arm"] == "honest"]
    print(f"  selection moved TO an honest member:      {len(to_hon)}")
    print(f"  selection moved TO an adversarial member: {len(to_adv)}  "
          f"{[r['new_pick']['id'] for r in to_adv]}")
    print("\n--- every corpus case's own birth-judge verdict (the unchanged authority) ---")
    for (_pitch, cid), vs in sorted(verdict_cache.items(), key=lambda kv: kv[0][1]):
        print(f"  {cid:<20} judge={vs}")
    unstable = [cid for (_p, cid), vs in verdict_cache.items() if len(set(vs)) > 1]
    print(f"unstable verdicts: {unstable}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
