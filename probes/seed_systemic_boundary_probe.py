"""D-3 reproduction: does an `LLMSystemicError` raised inside `_expand_seed_until_judged`
reach the OUTER boundary (`execute_seed_pipeline`), or is it absorbed on the way out?

Drives the REAL `_expand_seed_until_judged` -> `_tournament_cell` -> `_run_seed_cell` ->
`execute_seed_pipeline` chain. Only the LLM boundaries are replaced: the generator
(`_one_sample`), the concept critic (`_score_concepts`), the refiner
(`_refine_single_concept`), the in-cell scorer and the v4 loop. The judge is the thing under
test and raises.

Run:  .venv/bin/python probes/seed_systemic_boundary_probe.py
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[0] / ".." / "src"))

import nicheiq.crews.idea_improvement_loop_v4 as v4  # noqa: E402
from nicheiq.crews.unified_solution_crew import (  # noqa: E402
    SeedRequest,
    UnifiedSolutionCrew,
)
from nicheiq.utils.llm_service import LLMSystemicError  # noqa: E402

SEED = ("A simple web app that monitors your visibility across AI assistants for local "
        "businesses in London")


def _concept(name, one_liner):
    return SimpleNamespace(
        concept_name=name, one_liner=one_liner, project_type="saas",
        delivery_format="web-app", target_keywords=[], why_non_obvious="w",
        source_pain=None, source_segment=None, obviousness_score=0.3,
        data_feasibility_score=0.7, build_feasibility_score=0.8,
        data_access_model="public", critic_no_route=False,
        mechanism_tag=f"m-{name}", data_source_tag=f"d-{name}", journey_tag=f"j-{name}")


def _raise(exc, rec):
    """Raise from the REFINER — the one site inside the walk that `_expand_seed_until_judged`
    does not guard, so it lands on `_tournament_cell`'s handler directly."""
    if exc is not None:
        rec.setdefault("refined", []).append("raised")
        raise exc
    rec.setdefault("refined", []).append("ok")
    return None


def _crew(rec, judge_raises):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[], tools_currently_used=[],
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew.allowed_project_types = None
    crew.search_tool = None
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []

    def _judge(_self, _seed, candidate, evidence=None):
        rec.setdefault("judged", []).append(getattr(candidate, "solution_name", "?"))
        raise judge_raises

    crew._semantic_seed_identity_matches = _judge.__get__(crew, UnifiedSolutionCrew)
    return crew


def drive(judge_raises, refiner_raises=None):
    rec = {}
    crew = _crew(rec, judge_raises)
    pool = [_concept("EchoOfThePitch", SEED),
            _concept("TheRealProduct",
                     "A web app that monitors visibility across AI assistants")]

    orig = {}
    for name, fn in (
        ("_build_seed_crew_inputs", lambda self: {}),
        ("_one_sample", lambda self, *a, **kw: (pool, [])),
        ("_score_concepts", lambda self, concepts, idx=None: []),
        ("_refine_single_concept", lambda self, c, p, **kw: _raise(refiner_raises, rec) or SimpleNamespace(
            solution_name=f"spec-of-{c.concept_name}",
            source_pain=None, source_segment=None, mechanism_tag=None,
            data_source_tag=None, journey_tag=None, project_type=None,
            delivery_format=None, obviousness_score=None,
            data_feasibility_score=None, build_feasibility_score=None,
            pain_points_addressed=[], unanchored_hypothesis=None)),
        ("_score_cell_winner", lambda self, w, **kw: w),
        ("_repair_blank_idea_fields", lambda self, i: None),
        ("_record_divergent_usage", lambda self, u: None),
    ):
        orig[name] = getattr(UnifiedSolutionCrew, name, None)
        setattr(UnifiedSolutionCrew, name, fn)
    orig_v4 = v4.tournament_refine_cell_v4
    v4.tournament_refine_cell_v4 = lambda cands, grounding, **kw: cands[0]
    try:
        out = crew.execute_seed_pipeline(SeedRequest(seed_text=SEED, dispatch_id="validate"))
        return ("NO RAISE — returned " + repr(out), out, rec,
                getattr(crew, "_seed_failure_reason", None))
    except LLMSystemicError as e:
        return ("RAISED LLMSystemicError", str(e)[:40], rec,
                getattr(crew, "_seed_failure_reason", None))
    except Exception as e:  # noqa: BLE001
        return (f"RAISED {type(e).__name__}", str(e)[:40], rec,
                getattr(crew, "_seed_failure_reason", None))
    finally:
        for name, fn in orig.items():
            if fn is None:
                delattr(UnifiedSolutionCrew, name)
            else:
                setattr(UnifiedSolutionCrew, name, fn)
        v4.tournament_refine_cell_v4 = orig_v4


ARMS = (
    ("A. JUDGE raises LLMSystemicError (the S23 window)",
     dict(judge_raises=LLMSystemicError("402 payment required"))),
    ("B. REFINER raises LLMSystemicError (straight onto the bare handler)",
     dict(judge_raises=LLMSystemicError("unused"),
          refiner_raises=LLMSystemicError("402 payment required"))),
    ("C. REFINER raises ValueError (ordinary — fail-soft must survive)",
     dict(judge_raises=LLMSystemicError("unused"),
          refiner_raises=ValueError("an ordinary prompt-assembly bug"))),
)

if __name__ == "__main__":
    for label, kwargs in ARMS:
        verdict, payload, rec, reason = drive(**kwargs)
        print(f"\n=== execute_seed_pipeline — {label} ===")
        print(f"  outcome        : {verdict}")
        print(f"  detail         : {payload!r}")
        print(f"  refiner calls  : {rec.get('refined')}")
        print(f"  judge reached  : {rec.get('judged')}")
        print(f"  failure_reason : {reason!r}")
