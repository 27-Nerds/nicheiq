"""A/B the seed REFINEMENT call site against the whole vendored corpus, deterministically.

`_refine_single_concept(frame='user_seed')` used to veto its own LLM output with
`is_seed_faithful` (routes AND retention) and fall back to the pitch-shaped stub. It now vetoes
on the retention floor only, and reports the route finding as advisory. This walks all 22
corpus cases through the REAL function with the LLM call replaced by the corpus candidate, and
records which arm each case lands in — so "did an adversarial case flip refused -> accepted
here" is measured rather than argued.

No network. Usage: .venv/bin/python probes/seed_refine_gate_ab.py > file
"""
import json
from pathlib import Path
from types import SimpleNamespace

from loguru import logger

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils.frames import FrameFocus
from nicheiq.utils.seed_fidelity import (
    is_seed_faithful,
    seed_retention_floor_ok,
    unpitched_core_dependencies,
)

CORPUS = json.loads(Path("tests/fixtures/seed_identity_corpus.json").read_text())


def crew():
    c = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    c.cost_tracker = None
    c.niche_context = SimpleNamespace(niche_description="")
    c.allowed_project_types = None
    c._monetization_directive = ""
    c._divergent_usages = []
    return c


def concept_for(pitch):
    return SimpleNamespace(
        concept_name=usc._seed_name_from_pitch(pitch), one_liner=pitch,
        project_type="other", delivery_format="other", target_keywords=["k"],
        why_non_obvious="", mechanism_tag=None, data_source_tag=None, journey_tag=None,
        obviousness_score=-1.0, data_feasibility_score=-1.0, build_feasibility_score=-1.0,
        data_access_model=None, data_acquisition_notes=None, source_pain=None,
    )


def run_case(case):
    """Return (shipped_the_llm_output, stub_reason)."""
    pitch = case["pitch"]
    cand = SimpleNamespace(**case["candidate"])
    for attr in ("solution_name", "delivery_format", "novelty_score", "market_fit_score",
                 "technical_feasibility_score", "value_proposition", "short_description"):
        if not hasattr(cand, attr):
            setattr(cand, attr, None)
    messages = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="WARNING")
    try:
        usc.LLMService.invoke_structured = staticmethod(lambda **kw: (cand, None))
        out = crew()._refine_single_concept(
            concept_for(pitch), None, frame="user_seed",
            focus=FrameFocus(frame="user_seed", key="seed",
                             payload={"seed_text": pitch, "tool_ref": ""},
                             anchor_pain_titles=[]),
            anchor_pain_titles=[], cell_segment_name=None)
    finally:
        logger.remove(sink)
    reason = next((m.split("using stub: ", 1)[1] for m in messages if "using stub: " in m), "")
    return out is cand, reason


def main():
    real_invoke = usc.LLMService.invoke_structured
    print(f"{'arm':<12} {'id':<20} {'ships_llm_output':<18} {'floor':<6} {'routes':<7} "
          f"{'old_is_faithful':<16} reason")
    flips = []
    for arm in ("adversarial", "honest"):
        for case in CORPUS[arm]:
            pitch = case["pitch"]
            cand = SimpleNamespace(**case["candidate"])
            floor_ok = seed_retention_floor_ok(pitch, cand)
            routes = bool(unpitched_core_dependencies(pitch, cand))
            old = is_seed_faithful(pitch, cand)
            ships, reason = run_case(case)
            usc.LLMService.invoke_structured = real_invoke
            print(f"{arm:<12} {case['id']:<20} {str(ships):<18} {str(floor_ok):<6} "
                  f"{str(routes):<7} {str(old):<16} {reason[:50]}")
            if arm == "adversarial" and ships and not old:
                flips.append(case["id"])
    print()
    print(f"ADVERSARIAL cases that flipped refused->shipped at THIS call site: "
          f"{len(flips)} {flips}")


if __name__ == "__main__":
    main()
