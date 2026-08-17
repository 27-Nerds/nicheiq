"""What the REFINE call site ships once the retention floor stops vetoing, and what the birth
judge then does with it — honest concepts and adversarial ones, in the same harness.

Round 22 (S22). The floor veto at `_refine_single_concept(frame='user_seed')` was the last
no-LLM veto on the seed path; demoting it means an off-product refinement now reaches
`_semantic_seed_identity_matches` instead of being replaced by a stub. That is only safe if the
judge refuses what the floor would have blocked, so this drives BOTH directions through the real
functions:

  * `--honest`      the concepts the production generator actually produced for live job
                    03d20ff6 (replayed from `probes/seed_prefilter_capture.py`'s dump).
  * `--adversarial` three hand-built concepts, one per identity axis (mechanism / buyer / job),
                    each keeping the pitch's vocabulary while changing the product. These are the
                    under-firing attack: they must reach the judge and the judge must refuse them.

Per input: N real `_refine_single_concept` calls, then the REAL birth judge (with the same
`seed_identity_evidence` advisory block birth builds) REPEATS times per refined output, majority
vote. Results are appended to the JSON after every input so a stalled provider call cannot lose
the completed rows (one was observed at ~5m30s — see the D-2 note in the ledger).

MODEL SUBSTITUTION — read the banner the script prints. Production's refine tier
(`IDEATION_REFINE_LLM=gpt-5.6-luna`) is OpenAI and the account has no credit. Every refinement
number this produces is a property of the substituted model until re-measured on Luna. The
generator (replayed) and the judge are unsubstituted.

Usage:
  PYTHONPATH=probes IDEATION_REFINE_LLM=openrouter/x-ai/grok-4.3 \
    .venv/bin/python probes/seed_refine_floor_probe.py <capture.json> <arm> <runs> <repeats> <out.json>
Redirect to a file; never pipe.
"""
import json
import sys
import time
from types import SimpleNamespace

import nicheiq.utils.seed_fidelity as sf
from nicheiq.config.settings import settings
from nicheiq.models.solution_idea import RawConcept
from nicheiq.utils.frames import FrameFocus
from seed_prefilter_capture import build_crew
from seed_prefilter_spec_probe import _ANCHORS, _CHECKPOINT, _CONCEPT_FIELDS

_STUB_TAIL = "expand before shipping.)"

# Three substitutions of live job 03d20ff6's pitch, one identity axis each, written to KEEP the
# pitch's vocabulary (London, AI, local businesses, web app) so the lexical layer has the best
# possible chance of missing them. Each is a `RawConcept` in exactly the shape the seed cell's
# generator emits, so `_refine_single_concept` cannot tell them from a real one.
_ADVERSARIAL = [
    dict(
        axis="mechanism",
        concept_name="LondonAIAnswerRewriter",
        one_liner=(
            "A simple web app for local businesses in London that WRITES and publishes "
            "optimised copy so AI assistants describe your services the way you want — "
            "content generation, not monitoring."),
        project_type="other",
        delivery_format="web_app",
        why_non_obvious="Publishing the answer beats watching the answer.",
    ),
    dict(
        axis="buyer",
        concept_name="AIAssistantAnswerQualityAudit",
        one_liner=(
            "A simple web app for the AI platform teams themselves — OpenAI, Google, "
            "Perplexity — that audits how their assistants describe local businesses in "
            "London and flags where their answers are wrong."),
        project_type="other",
        delivery_format="web_app",
        why_non_obvious="The platform, not the business, pays to fix its own answers.",
    ),
    dict(
        axis="job",
        concept_name="LondonAIReferralLeadMarket",
        one_liner=(
            "A simple web app that captures customers who asked an AI assistant for a "
            "recommendation in London and SELLS those leads to local businesses as "
            "pay-per-introduction enquiries."),
        project_type="other",
        delivery_format="web_app",
        why_non_obvious="Monetise the referral itself rather than reporting on it.",
    ),
]


def concepts_for(arm: str, cap: dict) -> list:
    if arm == "adversarial":
        return [(a["axis"], RawConcept(
            **{k: v for k, v in a.items() if k != "axis"},
            target_keywords=["ai visibility london", "london business ai"],
            ideation_technique="atomic_feature",
            source_frame="user_seed", source_focus_key="seed")) for a in _ADVERSARIAL]
    out = []
    for i, sample in enumerate(cap["samples"], 1):
        rows = sample["generated"]
        cs = [RawConcept(**{k: r[k] for k in _CONCEPT_FIELDS if r.get(k) is not None},
                         source_frame="user_seed", source_focus_key="seed") for r in rows]
        # The cell's own ranking, not a re-implementation of a policy.
        out.append((f"sample{i}", max(cs, key=lambda c: sf.seed_fidelity_score(cap["pitch"], c))))
    return out


def judge(crew, pitch, idea, identity_terms, repeats):
    verdicts = []
    for _ in range(repeats):
        evidence = sf.seed_identity_evidence(pitch, idea, identity_terms, [])
        verdicts.append(bool(crew._semantic_seed_identity_matches(
            pitch, idea, evidence=evidence)))
    return verdicts


def main():
    cap_path, arm, runs, repeats, out_path = (
        sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    cap = json.load(open(cap_path))
    pitch, identity_terms = cap["pitch"], cap["identity_terms"]
    seed_tokens = sf._content_tokens(pitch)
    floor = max(1, (len(seed_tokens) * 3 + 4) // 5)

    print("!! MODEL SUBSTITUTION: refine tier = "
          f"{settings.ideation_refine_llm} (effort={settings.ideation_refine_reasoning_effort}). "
          "Production is gpt-5.6-luna (OpenAI, out of credit). Judge and generator are "
          "unsubstituted.")
    print(f"judge = {settings.report_structured_llm}")
    print(f"arm={arm} runs={runs} judge_repeats={repeats} "
          f"pitch tokens={len(seed_tokens)} floor={floor}\n")

    crew = build_crew(_CHECKPOINT, pitch)
    focus = FrameFocus(frame="user_seed", key="seed",
                       payload={"seed_text": pitch, "tool_ref": ""},
                       anchor_pain_titles=_ANCHORS)
    results = []
    for label, concept in concepts_for(arm, cap):
        for run in range(1, runs + 1):
            t0 = time.time()
            idea = crew._refine_single_concept(
                concept, None, frame="user_seed", focus=focus,
                anchor_pain_titles=_ANCHORS, cell_segment_name=None)
            elapsed = time.time() - t0
            desc = getattr(idea, "description", "") or ""
            # E-4 (2026-08-15, S23) — THIS DETECTOR OVER-DETECTED AND THE NUMBER IT PRODUCED WAS
            # TAKEN AS A MEASUREMENT. `description == concept.one_liner` fires on a GENUINE LLM spec
            # that opens by echoing the one-liner in `description` while writing fresh
            # `value_proposition` prose — it did so on 2 of 12 real specs. `_synthesize_idea_from_concept`
            # fills description AND value_proposition AND short_description from the one-liner, so the
            # sound test is the CONJUNCTION. The four hard-coded 0.5 scores are an independent
            # cross-check on the same object.
            _ol = (concept.one_liner or "").strip()
            is_stub = bool(_ol) and (
                (getattr(idea, "description", "") or "").strip() == _ol
                and (getattr(idea, "value_proposition", "") or "").strip() == _ol)
            retained = len(seed_tokens & sf._content_tokens(sf._candidate_identity_text(idea)))
            routes = [str(r) for r in sf.unpitched_core_dependencies(pitch, idea)]
            verdicts = judge(crew, pitch, idea, identity_terms, repeats)
            row = {
                "label": label, "concept": concept.concept_name, "run": run,
                "seconds": round(elapsed, 1),
                "outcome": "STUB" if is_stub else "SPEC",
                "retained": retained, "floor": floor,
                "floor_ok": retained >= floor,
                "routes": routes,
                "solution_name": getattr(idea, "solution_name", None),
                "headline": getattr(idea, "headline", None),
                "value_proposition": getattr(idea, "value_proposition", None),
                "description": desc,
                "judge_same_product": verdicts,
                "judge_majority": max(set(verdicts), key=verdicts.count) if verdicts else None,
                "judge_stable": len(set(verdicts)) == 1,
                "drift": sf.seed_clause_drift(identity_terms, idea),
            }
            results.append(row)
            print(f"[{label}/{concept.concept_name}] run {run}: {row['outcome']} "
                  f"retention {retained}/{len(seed_tokens)} (floor {floor}) "
                  f"{'PASS' if row['floor_ok'] else 'FAIL'} | routes={len(routes)} | "
                  f"judge same_product={verdicts} majority={row['judge_majority']} "
                  f"| drift={row['drift']} | {row['seconds']}s")
            print(f"    solution_name={row['solution_name']!r}")
            print(f"    value_proposition={(row['value_proposition'] or '')[:160]!r}")
            json.dump({"pitch": pitch, "arm": arm,
                       "refine_model": settings.ideation_refine_llm,
                       "judge_model": settings.report_structured_llm,
                       "rows": results}, open(out_path, "w"), indent=1)

    print("\n--- SUMMARY ---")
    specs = [r for r in results if r["outcome"] == "SPEC"]
    print(f"real specs: {len(specs)}/{len(results)}")
    under_floor = [r for r in results if not r["floor_ok"]]
    print(f"rows the OLD veto would have stubbed (under floor): {len(under_floor)}/{len(results)}")
    if under_floor:
        refused = [r for r in under_floor if r["judge_majority"] is False]
        print(f"  of those, the birth judge REFUSES: {len(refused)}/{len(under_floor)}")
    print(f"judge accepted: {sum(1 for r in results if r['judge_majority'])}/{len(results)}")
    print(f"judge unstable rows: {[r['concept'] for r in results if not r['judge_stable']]}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
