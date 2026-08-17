"""D-4 evidence: a REAL seed-identity trace file, written off disk, from a run whose walk
judged more than one candidate.

Drives `ResearchFlow._inject_validate_seed` -> `execute_seed_pipeline` -> `_run_seed_cell` ->
`_tournament_cell` -> `_expand_seed_until_judged` with only the provider boundary, the
generator and the refiner replaced. The judge REFUSES the highest-fidelity concept and ACCEPTS
the next one, which is the S23 defect's own shape and the run the trace used to describe as a
single candidate.

Run:  .venv/bin/python probes/seed_walk_trace_probe.py > /tmp/walk_trace.txt
"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import nicheiq.crews.idea_improvement_loop_v4 as v4  # noqa: E402
import nicheiq.flows.research_flow as rf  # noqa: E402
from nicheiq.crews.unified_solution_crew import (  # noqa: E402
    SeedRequest,  # noqa: F401  (kept for parity with the flow's own import)
    UnifiedSolutionCrew,
)
from nicheiq.flows.research_flow import ResearchFlow  # noqa: E402
from nicheiq.models.research_state import ResearchState  # noqa: E402

SEED = ("A simple web app that monitors your visibility across AI assistants for local "
        "businesses in London")

ACCEPTED_BY_THE_JUDGE = "TheRealProduct"


def _concept(name, one_liner):
    return SimpleNamespace(
        concept_name=name, one_liner=one_liner, project_type="saas",
        delivery_format="web-app", target_keywords=[], why_non_obvious="w",
        source_pain=None, source_segment=None, obviousness_score=0.3,
        data_feasibility_score=0.7, build_feasibility_score=0.8,
        data_access_model="public", critic_no_route=False,
        mechanism_tag=f"m-{name}", data_source_tag=f"d-{name}", journey_tag=f"j-{name}")


def _spec(concept):
    """A refined candidate carrying enough identity prose that `capture_gate_input` has
    something to record — otherwise the probe would 'pass' on empty candidate dicts."""
    name = concept.concept_name
    return SimpleNamespace(
        solution_name=f"spec-of-{name}",
        short_description=f"{name}: monitors AI assistant answers for London businesses.",
        description=(f"{name} runs a fixed library of local-intent prompts across AI "
                     "assistants and stores the answers for London businesses."),
        value_proposition=f"{name} shows how AI assistants describe a London business.",
        project_type="saas", delivery_format="web-app",
        data_access_model="public",
        data_acquisition_notes=f"{name} reads public assistant answers.",
        source_pain=None, source_segment=None, mechanism_tag=None, data_source_tag=None,
        journey_tag=None, obviousness_score=None, data_feasibility_score=None,
        build_feasibility_score=None, pain_points_addressed=[], unanchored_hypothesis=None,
        incumbent_parity="unclear", candidate_status="active",
        generation_operation_id=None, duplicate_of=None)


def main():
    pool = [_concept("EchoOfThePitch", SEED),
            _concept(ACCEPTED_BY_THE_JUDGE,
                     "A web app that monitors visibility across AI assistants")]

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

    judged = []

    def judge(_self, _seed, candidate, evidence=None):
        name = getattr(candidate, "solution_name", "")
        judged.append(name)
        return name == f"spec-of-{ACCEPTED_BY_THE_JUDGE}"

    crew._semantic_seed_identity_matches = judge.__get__(crew, UnifiedSolutionCrew)

    for name, fn in (
        ("_build_seed_crew_inputs", lambda self: {}),
        ("_one_sample", lambda self, *a, **kw: (pool, [])),
        ("_score_concepts", lambda self, concepts, idx=None: []),
        ("_refine_single_concept", lambda self, c, p, **kw: _spec(c)),
        ("_score_cell_winner", lambda self, w, **kw: w),
        ("_repair_blank_idea_fields", lambda self, i: None),
        ("_record_divergent_usage", lambda self, u: None),
        ("_score_wave", lambda self, wave, **kw: None),
        ("_finalize_seed_tail", lambda self, wave: None),
    ):
        setattr(UnifiedSolutionCrew, name, fn)
    v4.tournament_refine_cell_v4 = lambda cands, grounding, **kw: cands[0]

    tmp = Path(tempfile.mkdtemp(prefix="seedtrace-"))
    rf.settings.checkpoint_dir = tmp / "checkpoints"
    rf.settings.output_dir = tmp / "output"

    flow = ResearchFlow.__new__(ResearchFlow)
    flow.entry_mode = "validate_idea"
    flow._state = ResearchState()
    flow._state.user_idea_text = SEED
    flow.job_id = "walk-probe"
    flow._emit_progress = lambda *a, **k: None

    flow._inject_validate_seed(crew, SimpleNamespace(solution_ideas=[]))

    files = sorted((tmp / "checkpoints").glob("seed_identity_trace_*.json"))
    print(f"\ntrace files written: {[f.name for f in files]}")
    if not files:
        print("NO TRACE FILE — nothing to show")
        return
    payload = json.loads(files[0].read_text())
    print(f"path      : {files[0]}")
    print(f"outcome   : {payload['outcome']}")
    print(f"judge saw : {judged}")
    print(f"gate records: {len(payload['gates'])}")
    for g in payload["gates"]:
        cand = g.get("candidate") or {}
        print(f"  - gate={g['gate']:<14} verdict={g['verdict']:<10} reason={g['reason']!r}")
        print(f"      candidate.solution_name = {cand.get('solution_name')!r} "
              f"({len(cand)} field(s) captured)")


if __name__ == "__main__":
    main()
