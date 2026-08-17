"""D-2 — RE-DERIVE `_SEED_RANK_MAX_REFINEMENTS`'s justification WITH THE CRITIC ON.

The comment above `_SEED_RANK_MAX_REFINEMENTS` says the first judge-accepted concept sits at
fidelity rank "1, 2 and 1 — never past 2", and that a cap of 3 therefore "covers every position
observed with one to spare". That was read off `probes/seed_rank_pool_ab.py`, whose own output
records `critic_driven: false` — an ordering production never takes, because `_score_concepts`
runs at `_run_seed_cell` BEFORE `_tournament_cell` orders the pool.

This harness re-derives the ranks the way production orders them, deterministically, from
artifacts already on disk — no network, no new LLM spend:

  * concepts            <- probes/seed_prefilter_capture.py's dump (3 live pools, 4 each)
  * critic verdicts     <- the funded-production-critic field probe (2 reps x 12 concepts),
                           which recorded each concept's fields BEFORE and AFTER `_score_concepts`
  * judge verdicts      <- seed_rank_pool_ab.py's per-concept `judge_majority`

For each critic repeat it applies the critic's AFTER values to the concept, drops what
`_tournament_cell` drops (`critic_no_route` / `data_access_model == 'blocked'`), orders by the
shipped key `(-seed_fidelity_score, obviousness)` and reports the rank of the first
judge-ACCEPTED concept. The critic-OFF arm is computed the same way from the same rows so the
two are comparable.

Run:  .venv/bin/python probes/seed_rank_critic_on_rederive.py > /tmp/critic_on.txt
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nicheiq.utils.seed_fidelity import seed_fidelity_score  # noqa: E402

CAPTURE = "/tmp/prefilter_capture.json"
FIELD_PROBE = "/tmp/e1_live_prod2.json"     # production critic (gpt-5.6-luna), funded, 2 reps
POOL_AB = "/tmp/pool_ab_luna.json"          # production refiner arm, judge unsubstituted


def _obv(c):
    o = getattr(c, "obviousness_score", -1.0)
    return o if isinstance(o, (int, float)) and o >= 0 else 0.5


def _usable(c):
    return (not getattr(c, "critic_no_route", False)
            and (getattr(c, "data_access_model", None) or "").strip().lower() != "blocked")


def main():
    cap = json.load(open(CAPTURE))
    pitch = cap["pitch"]
    probe = json.load(open(FIELD_PROBE))
    pool_ab = json.load(open(POOL_AB))

    assert pool_ab["pitch"] == pitch and probe["pitch"] == pitch, "different pitch — abort"
    print(f"critic model      : {probe['critic']}")
    print(f"refiner (pool A/B): {pool_ab['refine_model']}   judge: {pool_ab['judge_model']}")
    print(f"pool A/B critic_driven flag as recorded: {pool_ab.get('critic_driven')!r}")

    # judge verdict per (sample, concept): majority over the repeats, as the walk uses
    verdict = {}
    for r in pool_ab["rows"]:
        verdict[(r["sample"], r["concept"])] = bool(r["judge_majority"])

    # critic before/after per (rep, sample, concept)
    after = {}
    before = {}
    for r in probe["rows"]:
        after[(r["rep"], r["sample"], r["concept"])] = r["after"]
        before[(r["rep"], r["sample"], r["concept"])] = r["before"]
    reps = sorted({r["rep"] for r in probe["rows"]})

    for arm, table in (("CRITIC OFF (as the A/B ran it)", before),
                       ("CRITIC ON  (as production runs it)", after)):
        print(f"\n===== {arm} =====")
        for rep in reps:
            ranks = []
            for si, sample in enumerate(cap["samples"], 1):
                pool = []
                for cd in sample["generated"]:
                    name = cd["concept_name"]
                    fields = dict(cd)
                    fields.update(table[(rep, si, name)])
                    pool.append(SimpleNamespace(**fields))
                pool = [c for c in pool if _usable(c)]
                ordered = sorted(pool, key=lambda c: (-seed_fidelity_score(pitch, c), _obv(c)))
                first = None
                for pos, c in enumerate(ordered, 1):
                    if verdict.get((si, c.concept_name)):
                        first = pos
                        break
                ranks.append(first)
                detail = ", ".join(
                    f"{p}:{c.concept_name}[f={seed_fidelity_score(pitch, c):.3f} "
                    f"o={_obv(c):.2f} {'A' if verdict.get((si, c.concept_name)) else 'r'}]"
                    for p, c in enumerate(ordered, 1))
                print(f"  rep{rep} sample{si}: first ACCEPT at rank {first}  | {detail}")
            print(f"  rep{rep} -> first-accept ranks {ranks}  max={max(r or 99 for r in ranks)}")


if __name__ == "__main__":
    main()
