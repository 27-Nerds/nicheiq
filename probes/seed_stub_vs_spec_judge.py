"""The user-outcome A/B: what the birth judge says about the STUB the old veto produced,
against what it says about the SPEC that now ships in its place.

The stub arm is not reconstructed — it is driven through the real `_refine_single_concept`
with the LLM call forced to raise, which is exactly the `except` branch the retention-floor
veto used to reach (`raise ValueError("refinement replaced the user-submitted product")`).
No refine tokens are spent on this arm, so nothing here is model-substituted; the judge is
production's own tier.

Pair it with `probes/seed_refine_floor_probe.py --honest` for the spec arm.

Usage:
  PYTHONPATH=probes .venv/bin/python probes/seed_stub_vs_spec_judge.py <capture.json> <repeats>
Redirect to a file; never pipe.
"""
import json
import sys

import nicheiq.crews.unified_solution_crew as usc
import nicheiq.utils.seed_fidelity as sf
from nicheiq.config.settings import settings
from nicheiq.models.solution_idea import RawConcept
from nicheiq.utils.frames import FrameFocus
from seed_prefilter_capture import build_crew
from seed_prefilter_spec_probe import _ANCHORS, _CHECKPOINT, _CONCEPT_FIELDS

_STUB_TAIL = "expand before shipping.)"


def main():
    cap = json.load(open(sys.argv[1]))
    repeats = int(sys.argv[2])
    pitch, identity_terms = cap["pitch"], cap["identity_terms"]
    seed_tokens = sf._content_tokens(pitch)
    floor = max(1, (len(seed_tokens) * 3 + 4) // 5)
    crew = build_crew(_CHECKPOINT, pitch)
    focus = FrameFocus(frame="user_seed", key="seed",
                       payload={"seed_text": pitch, "tool_ref": ""},
                       anchor_pain_titles=_ANCHORS)
    print(f"judge = {settings.report_structured_llm} (unsubstituted); "
          f"stub arm spends no refine tokens\n")

    real = usc.LLMService.invoke_structured

    def boom(**kw):
        raise ValueError("refinement replaced the user-submitted product")

    rows = []
    for i, sample in enumerate(cap["samples"], 1):
        concepts = [RawConcept(**{k: r[k] for k in _CONCEPT_FIELDS if r.get(k) is not None},
                               source_frame="user_seed", source_focus_key="seed")
                    for r in sample["generated"]]
        top = max(concepts, key=lambda c: sf.seed_fidelity_score(pitch, c))
        usc.LLMService.invoke_structured = staticmethod(boom)
        try:
            stub = crew._refine_single_concept(
                top, None, frame="user_seed", focus=focus,
                anchor_pain_titles=_ANCHORS, cell_segment_name=None)
        finally:
            usc.LLMService.invoke_structured = real
        # E-4 (2026-08-15, S23): the sound stub test is the CONJUNCTION —
        # `_synthesize_idea_from_concept` fills description AND value_proposition from the
        # one-liner, and `description == one_liner` alone fired on 2 of 12 genuine specs.
        # This assertion exists to prove the forced-raise really reached the stub branch,
        # so an over-detecting predicate here would let a non-stub through as evidence.
        _ol = (top.one_liner or "").strip()
        _d = (getattr(stub, "description", "") or "").strip()
        _vp = (getattr(stub, "value_proposition", "") or "").strip()
        assert _d.endswith(_STUB_TAIL) or (_d == _ol and _vp == _ol), "not the stub path"
        verdicts = []
        for _ in range(repeats):
            ev = sf.seed_identity_evidence(pitch, stub, identity_terms, [])
            verdicts.append(bool(crew._semantic_seed_identity_matches(pitch, stub, evidence=ev)))
        retained = len(seed_tokens & sf._content_tokens(sf._candidate_identity_text(stub)))
        row = {"sample": i, "concept": top.concept_name,
               "solution_name": getattr(stub, "solution_name", None),
               "retained": retained, "floor": floor,
               "judge_same_product": verdicts,
               "judge_majority": max(set(verdicts), key=verdicts.count),
               "description": getattr(stub, "description", "")}
        rows.append(row)
        print(f"sample{i} STUB of {top.concept_name!r}: retention {retained}/{len(seed_tokens)} "
              f"(floor {floor}) judge={verdicts}")
        print(f"    solution_name={row['solution_name']!r}")
        print(f"    description={row['description'][:180]!r}")

    print("\n--- SUMMARY (stub arm) ---")
    print(f"judge accepted the stub: {sum(1 for r in rows if r['judge_majority'])}/{len(rows)}")


if __name__ == "__main__":
    main()
