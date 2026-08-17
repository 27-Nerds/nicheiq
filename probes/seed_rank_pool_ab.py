"""EVIDENCE 2 — the live A/B for the `user_seed` cell's RANKING, on the whole pool.

Round 23 (S23). `_tournament_cell:6319` selects the `user_seed` cell's winner with
`max(pool, key=(seed_fidelity_score, -obviousness))` — a token-retention ratio that three
rounds have measured as preferring an echo over a product. This probe does not rank; it
REFINES EVERY CONCEPT IN THE POOL and asks the real birth judge about each one, so any
proposed ranking can be scored against the outcome the owner actually asked for: *the concept
that yields a real spec the judge accepts as the same product.*

Population: the 3 captured generator samples for live job 03d20ff6 (4 concepts each, 12 total),
replayed from `probes/seed_prefilter_capture.py`'s dump. Each sample is one live cell pool.

Per concept: `runs` real `_refine_single_concept(frame='user_seed')` calls, then the REAL birth
judge (`_semantic_seed_identity_matches`, with the same `seed_identity_evidence` advisory block
birth builds) `repeats` times per refined output. Rows are flushed to JSON after every judge
verdict so a stalled provider call (D-2: the refine call is unbounded) cannot lose completed work.

STUB DETECTION — corrected (E-4, 2026-08-15). Earlier probes in this program detected the
no-LLM stub with `description == concept.one_liner`, which OVER-detects: a genuine LLM spec that
opens by echoing the one-liner in `description` while writing fresh `value_proposition` prose was
counted as a stub twice in twelve. `_synthesize_idea_from_concept` sets `description`,
`value_proposition` AND `short_description` all from the one-liner, so the sound test is the
CONJUNCTION. The four 0.5 placeholder scores are recorded as an independent cross-check.

MODEL SUBSTITUTION — read the banner. `IDEATION_REFINE_LLM=gpt-5.6-luna` is OpenAI and the
account has no credit, so every refinement number here is a property of the substituted model.
The generator is replayed (unsubstituted at capture time) and the birth judge
(`report_structured_llm`) is unsubstituted. NOTE ALSO: `ideation_judge_llm` — the concept critic
— is ALSO gpt-5.6-luna, so on this machine `_score_concepts` fails open with a 429 and writes
NOTHING (measured: `probes/seed_rank_field_probe.py --live`). Pass `--critic` to drive the
critic under a substitution; by default the pool carries only what the generator wrote, which is
what the seed cell sees in production on this account.

Usage:
  PYTHONPATH=probes IDEATION_REFINE_LLM=openrouter/x-ai/grok-4.3 \
    .venv/bin/python probes/seed_rank_pool_ab.py <capture.json> <runs> <repeats> <out.json>
Redirect to a file; never pipe.
"""
import json
import sys
import time

import nicheiq.utils.seed_fidelity as sf
from nicheiq.config.settings import settings
from nicheiq.models.solution_idea import RawConcept
from nicheiq.utils.frames import FrameFocus
from seed_prefilter_capture import build_crew
from seed_prefilter_spec_probe import _ANCHORS, _CHECKPOINT

_CONCEPT_FIELDS = ("concept_name", "one_liner", "project_type", "delivery_format",
                   "target_keywords", "why_non_obvious", "ideation_technique",
                   "data_access_model", "data_acquisition_notes")


def is_stub(idea, concept) -> bool:
    """The SOUND stub test (E-4). `_synthesize_idea_from_concept` fills description,
    value_proposition and short_description from the one-liner; a genuine spec that merely
    opens with the one-liner in `description` does not."""
    ol = (getattr(concept, "one_liner", "") or "").strip()
    if not ol:
        return False
    return (
        (getattr(idea, "description", "") or "").strip() == ol
        and (getattr(idea, "value_proposition", "") or "").strip() == ol
    )


def placeholder_quad(idea) -> bool:
    """Independent cross-check: the stub's four hard-coded 0.5 scores."""
    return all(getattr(idea, f, None) == 0.5 for f in (
        "market_fit_score", "technical_feasibility_score",
        "seo_scalability_score", "solo_dev_feasibility"))


def judge(crew, pitch, idea, identity_terms, repeats):
    out = []
    for _ in range(repeats):
        evidence = sf.seed_identity_evidence(pitch, idea, identity_terms, [])
        out.append(bool(crew._semantic_seed_identity_matches(pitch, idea, evidence=evidence)))
    return out


def main():
    cap_path, runs, repeats, out_path = (
        sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    use_critic = "--critic" in sys.argv
    cap = json.load(open(cap_path))
    pitch, identity_terms = cap["pitch"], cap["identity_terms"]
    seed_tokens = sf._content_tokens(pitch)
    floor = max(1, (len(seed_tokens) * 3 + 4) // 5)

    print("!! MODEL SUBSTITUTION: refine tier = "
          f"{settings.ideation_refine_llm} (effort={settings.ideation_refine_reasoning_effort}). "
          "Production is gpt-5.6-luna (OpenAI, out of credit).")
    print(f"judge (unsubstituted) = {settings.report_structured_llm}")
    print(f"critic tier = {settings.ideation_judge_llm} (driven={use_critic})")
    print(f"runs={runs} judge_repeats={repeats} pitch tokens={len(seed_tokens)} floor={floor}\n")

    crew = build_crew(_CHECKPOINT, pitch)
    focus = FrameFocus(frame="user_seed", key="seed",
                       payload={"seed_text": pitch, "tool_ref": ""},
                       anchor_pain_titles=_ANCHORS)
    rows = []
    for si, sample in enumerate(cap["samples"], 1):
        pool = [RawConcept(**{k: r[k] for k in _CONCEPT_FIELDS if r.get(k) is not None},
                           source_frame="user_seed", source_focus_key="seed")
                for r in sample["generated"]]
        if use_critic:
            crew._score_concepts(pool, idx=97)
        # `_tournament_cell`'s own key, quoted rather than paraphrased.
        def _obv(c):
            o = getattr(c, "obviousness_score", -1.0)
            return o if isinstance(o, (int, float)) and o >= 0 else 0.5
        keyed = [(sf.seed_fidelity_score(pitch, c), -_obv(c), i, c)
                 for i, c in enumerate(pool)]
        # Descending by the CURRENT key; index preserves generator order inside a tie, which is
        # what `max` resolves to (first maximal element wins).
        order = sorted(keyed, key=lambda t: (-t[0], -t[1], t[2]))
        print(f"=== sample{si} pool, in the CURRENT ranking's order ===")
        for rank, (fid, negobv, i, c) in enumerate(order, 1):
            print(f"  #{rank} {c.concept_name:<30} fidelity={fid:.3f} obv={-negobv} gen_pos={i}")
        print()

        only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
        for rank, (fid, negobv, gen_pos, concept) in enumerate(order, 1):
            if only and concept.concept_name != only:
                continue
            for run in range(1, runs + 1):
                t0 = time.time()
                idea = crew._refine_single_concept(
                    concept, None, frame="user_seed", focus=focus,
                    anchor_pain_titles=_ANCHORS, cell_segment_name=None)
                elapsed = time.time() - t0
                stub = is_stub(idea, concept)
                retained = len(seed_tokens & sf._content_tokens(sf._candidate_identity_text(idea)))
                verdicts = judge(crew, pitch, idea, identity_terms, repeats)
                row = {
                    "sample": si, "fidelity_rank": rank, "gen_pos": gen_pos,
                    "concept": concept.concept_name, "fidelity": round(fid, 4),
                    "obviousness": -negobv, "run": run, "seconds": round(elapsed, 1),
                    "outcome": "STUB" if stub else "SPEC",
                    "placeholder_quad": placeholder_quad(idea),
                    "retained": retained, "floor": floor, "floor_ok": retained >= floor,
                    "routes": [str(r) for r in sf.unpitched_core_dependencies(pitch, idea)],
                    "solution_name": getattr(idea, "solution_name", None),
                    "value_proposition": getattr(idea, "value_proposition", None),
                    "description": getattr(idea, "description", None),
                    "judge": verdicts,
                    "judge_majority": max(set(verdicts), key=verdicts.count) if verdicts else None,
                    "judge_stable": len(set(verdicts)) == 1,
                    "drift": sf.seed_clause_drift(identity_terms, idea),
                }
                rows.append(row)
                print(f"[s{si} #{rank} {concept.concept_name}] run{run}: {row['outcome']} "
                      f"fid={fid:.3f} retention {retained}/{len(seed_tokens)} "
                      f"{'PASS' if row['floor_ok'] else 'FAIL'} | judge={verdicts} "
                      f"majority={row['judge_majority']} | quad={row['placeholder_quad']} "
                      f"| {row['seconds']}s")
                json.dump({"pitch": pitch, "refine_model": settings.ideation_refine_llm,
                           "judge_model": settings.report_structured_llm,
                           "critic_driven": use_critic, "rows": rows},
                          open(out_path, "w"), indent=1)

    print("\n--- A/B ---")
    for si in sorted({r["sample"] for r in rows}):
        srows = [r for r in rows if r["sample"] == si]
        cur = [r for r in srows if r["fidelity_rank"] == 1]
        cur_acc = sum(1 for r in cur if r["judge_majority"])
        print(f"sample{si}: CURRENT pick = {cur[0]['concept']} "
              f"(fidelity {cur[0]['fidelity']:.3f}) accepted {cur_acc}/{len(cur)} runs")
        for rank in sorted({r["fidelity_rank"] for r in srows}):
            rr = [r for r in srows if r["fidelity_rank"] == rank]
            acc = sum(1 for r in rr if r["judge_majority"])
            spec = sum(1 for r in rr if r["outcome"] == "SPEC")
            print(f"    #{rank} {rr[0]['concept']:<30} fid={rr[0]['fidelity']:.3f} "
                  f"spec {spec}/{len(rr)} judge-accepted {acc}/{len(rr)}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
