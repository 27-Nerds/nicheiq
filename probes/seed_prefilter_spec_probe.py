"""What the user RECEIVES once a generated concept survives the prefilter.

Takes a capture from `probes/seed_prefilter_capture.py`, picks the concept the seed cell's own
ranking would select (`_tournament_cell` maximises `seed_fidelity_score` for a `user_seed` cell),
and drives the REAL `_refine_single_concept(frame='user_seed')` on it — the same call the live
run made. Prints the five descriptive fields that reach the report plus every gate reading.

MODEL SUBSTITUTION — read the banner the script prints. The production refine tier
(`IDEATION_REFINE_LLM=gpt-5.6-luna`) is OpenAI and the account has no credit, so this must be run
with `IDEATION_REFINE_LLM` pointed at an OpenRouter model. Every number produced under a
substitution is a property of THAT model until it is re-measured on the production one.

Usage:
  PYTHONPATH=probes IDEATION_REFINE_LLM=openrouter/x-ai/grok-4.3 \
    .venv/bin/python probes/seed_prefilter_spec_probe.py <capture.json> <sample_index>
Redirect to a file; never pipe.
"""
import json
import sys
from types import SimpleNamespace

import nicheiq.utils.seed_fidelity as sf
from nicheiq.config.settings import settings
from nicheiq.models.solution_idea import RawConcept
from nicheiq.utils.frames import FrameFocus
from seed_prefilter_capture import build_crew

# A pain-less stub no longer carries the "(Re-injected …)" tail (2026-08-15, S22 —
# it was internal prose in a user-visible field), so the tail alone under-detects the
# stub on the seed path. `description == one_liner` is what a pain-less stub now is.
_STUB_TAIL = "expand before shipping.)"
_CHECKPOINT = ("output/checkpoints/checkpoint_ai_visibility_for_local_businesses_in_london_"
               "find_03d20ff6-3973-48b6-b414-42a71883225d_20260815_153709")
_ANCHORS = [
    "Cannot keep local service and location data consistent across profiles",
    "Cannot establish a stable prompt-level visibility baseline",
    "Cannot keep business facts consistent across AI-retrieved sources",
]
_CONCEPT_FIELDS = ("concept_name", "one_liner", "project_type", "delivery_format",
                   "target_keywords", "why_non_obvious", "ideation_technique")


def main():
    cap = json.load(open(sys.argv[1]))
    idx = int(sys.argv[2]) - 1
    pitch = cap["pitch"]
    rows = cap["samples"][idx]["generated"]
    concepts = [RawConcept(**{k: r[k] for k in _CONCEPT_FIELDS if r.get(k) is not None},
                           source_frame="user_seed", source_focus_key="seed")
                for r in rows]
    # The cell's own ranking, not a re-implementation of a policy: `_tournament_cell` selects
    # `max(pool, key=seed_fidelity_score)` for a user_seed cell.
    top = max(concepts, key=lambda c: sf.seed_fidelity_score(pitch, c))

    print("!! MODEL SUBSTITUTION: refine tier = "
          f"{settings.ideation_refine_llm} (effort={settings.ideation_refine_reasoning_effort}). "
          "Production is gpt-5.6-luna (OpenAI, out of credit). Do not read this as a "
          "production measurement.")
    print(f"generator model (unsubstituted): {cap['model']}")
    print(f"sample {idx + 1}: {len(concepts)} concepts; the cell would refine "
          f"{top.concept_name!r} (fidelity={sf.seed_fidelity_score(pitch, top):.3f})\n")

    crew = build_crew(_CHECKPOINT, pitch)
    focus = FrameFocus(frame="user_seed", key="seed",
                       payload={"seed_text": pitch, "tool_ref": ""},
                       anchor_pain_titles=_ANCHORS)
    idea = crew._refine_single_concept(top, None, frame="user_seed", focus=focus,
                                       anchor_pain_titles=_ANCHORS, cell_segment_name=None)
    desc = getattr(idea, "description", "") or ""
    vp = (getattr(idea, "value_proposition", "") or "").strip()
    clean = " ".join(pitch.split()).strip()
    # E-4 (2026-08-15, S23) — THIS DETECTOR OVER-DETECTED AND THE NUMBER IT PRODUCED WAS
    # TAKEN AS A MEASUREMENT. `description == concept.one_liner` fires on a GENUINE LLM spec
    # that opens by echoing the one-liner in `description` while writing fresh
    # `value_proposition` prose — it did so on 2 of 12 real specs. `_synthesize_idea_from_concept`
    # fills description AND value_proposition AND short_description from the one-liner, so the
    # sound test is the CONJUNCTION. The four hard-coded 0.5 scores are an independent
    # cross-check on the same object.
    _ol = (top.one_liner or "").strip()
    is_stub = bool(_ol) and (
        (getattr(idea, "description", "") or "").strip() == _ol
        and (getattr(idea, "value_proposition", "") or "").strip() == _ol)
    print("STUB (concept pasted into five boxes)" if is_stub else "GENERATED SPEC")
    for field in ("solution_name", "headline", "short_description", "description",
                  "value_proposition"):
        value = getattr(idea, field, "") or ""
        print(f"  {field:<18} ({len(value):>4}): {value[:180]!r}")
    print(f"  value_proposition IS the pitch verbatim: {vp == clean}")
    seed_tokens = sf._content_tokens(pitch)
    retained = len(seed_tokens & sf._content_tokens(sf._candidate_identity_text(idea)))
    floor = max(1, (len(seed_tokens) * 3 + 4) // 5)
    print(f"  retention          : {retained}/{len(seed_tokens)} (floor {floor})")
    print(f"  unpitched routes   : {sf.unpitched_core_dependencies(pitch, idea)}")
    print(f"  seed_clause_drift  : {sf.seed_clause_drift(cap['identity_terms'], idea)}")


if __name__ == "__main__":
    main()
