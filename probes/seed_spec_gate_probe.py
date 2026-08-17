"""What the "Check my idea" seed cell actually SHIPS for a real pitch.

Drives the real `_refine_single_concept(frame='user_seed')` — the same call the live run
made — on the seed fallback concept, unpatched, and prints the five descriptive fields that
reach the report plus every deterministic gate reading. Nothing is stubbed: this is the
production path, one LLM call per sample.

`stub` in the output means the refinement was rejected and
`_synthesize_idea_from_concept` filled the five fields from the pitch instead.

Usage:  .venv/bin/python probes/seed_spec_gate_probe.py <trace.json> <repeats>
Redirect to a file; never pipe.
"""
import json
import sys
from types import SimpleNamespace

import nicheiq.utils.seed_fidelity as sf
from nicheiq.crews.unified_solution_crew import (
    UnifiedSolutionCrew,
    _seed_name_from_pitch,
)
from nicheiq.models.delivery_format import infer_delivery_format
from nicheiq.models.solution_idea import RawConcept
from nicheiq.utils.frames import FrameFocus

# A pain-less stub no longer carries the "(Re-injected …)" tail (2026-08-15, S22 —
# it was internal prose in a user-visible field), so the tail alone under-detects the
# stub on the seed path. `description == one_liner` is what a pain-less stub now is.
_STUB_TAIL = "expand before shipping.)"

_ANCHORS = [
    "Cannot keep local service and location data consistent across profiles",
    "Cannot establish a stable prompt-level visibility baseline",
    "Cannot keep business facts consistent across AI-retrieved sources",
]


def build_crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[], tools_currently_used=[],
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="AI visibility for local businesses")
    crew.competitor_mentions_text = ""
    crew.allowed_project_types = None
    crew.search_tool = None
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    crew._monetization_directive = ""
    crew._divergent_usages = []
    return crew


def fallback_concept(seed_text, clean_seed):
    """Byte-identical to the concept `_run_seed_cell` mints when generation is rejected."""
    keyword_base = " ".join(clean_seed.split()[:8]) or "user product idea"
    return RawConcept(
        concept_name=_seed_name_from_pitch(seed_text or clean_seed),
        one_liner=clean_seed or "User-submitted product idea",
        ideation_technique="atomic_feature",
        project_type="other",
        delivery_format=infer_delivery_format(clean_seed) or "other",
        target_keywords=[keyword_base, f"{keyword_base} app"],
        why_non_obvious=(
            "User-provided product brief; preserve its core mechanism during refinement."),
        source_frame="user_seed",
        source_focus_key="seed",
    )


def main():
    trace = json.load(open(sys.argv[1]))
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    pitch = trace["pitch"]
    identity_terms = trace["identity_terms"]
    clean = " ".join(pitch.split()).strip()
    focus = FrameFocus(frame="user_seed", key="seed",
                       payload={"seed_text": pitch, "tool_ref": ""},
                       anchor_pain_titles=_ANCHORS)

    crew = build_crew()
    concept = fallback_concept(pitch, clean)
    seed_tokens = sf._content_tokens(pitch)
    floor = max(1, (len(seed_tokens) * 3 + 4) // 5)

    print(f"pitch len={len(pitch)}  stemmed content tokens={len(seed_tokens)}  "
          f"retention floor={floor}  repeats={repeats}")
    print(f"minted fallback concept_name = {concept.concept_name!r}\n")

    stubs = 0
    for i in range(repeats):
        idea = crew._refine_single_concept(
            concept, None, frame="user_seed", focus=focus,
            anchor_pain_titles=_ANCHORS, cell_segment_name=None)
        desc = getattr(idea, "description", "") or ""
        vp = (getattr(idea, "value_proposition", "") or "").strip()
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
        stubs += is_stub
        print(f"--- sample {i + 1} --- {'STUB (pitch in five boxes)' if is_stub else 'GENERATED SPEC'}")
        print(f"  solution_name     ({len(getattr(idea, 'solution_name', '') or ''):>3}): "
              f"{getattr(idea, 'solution_name', None)!r}")
        print(f"  headline          ({len(getattr(idea, 'headline', '') or ''):>3}): "
              f"{(getattr(idea, 'headline', '') or '')!r}")
        print(f"  short_description ({len(getattr(idea, 'short_description', '') or ''):>3}): "
              f"{(getattr(idea, 'short_description', '') or '')[:130]!r}")
        print(f"  description       ({len(desc):>3}): {desc[:130]!r}")
        print(f"  value_proposition ({len(vp):>3}): {vp[:130]!r}")
        print(f"  value_proposition IS the pitch verbatim: {vp == clean}")
        retained = len(seed_tokens & sf._content_tokens(sf._candidate_identity_text(idea)))
        print(f"  retention         : {retained}/{len(seed_tokens)} (floor {floor}) "
              f"-> {'PASS' if retained >= floor else 'FAIL'}")
        print(f"  unpitched routes  : {sf.unpitched_core_dependencies(pitch, idea)}")
        print(f"  seed_clause_drift : {sf.seed_clause_drift(identity_terms, idea)}")
        print()
    print(f"TOTAL: {stubs}/{repeats} shipped the pitch as a stub, "
          f"{repeats - stubs}/{repeats} shipped a generated spec")


if __name__ == "__main__":
    main()
