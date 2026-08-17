"""Capture what the seed cell's GENERATOR actually produces, and what the prefilter does to it.

Drives the real `UnifiedSolutionCrew._run_seed_cell` on a real hydrated run (checkpoint +
pitch), with three RECORDERS and no re-implementation of any production logic:

  * `_one_sample`   — wrapped: calls the real generator, records the concepts it returned.
  * `_score_concepts` — stubbed to a no-op recorder (critic tokens only; it runs strictly
                        AFTER the prefilter, so it cannot change the prefilter's verdict).
  * `_tournament_cell` — stubbed to a recorder returning None, so nothing downstream runs.

The generator model is whatever `settings.brainstorm_pool_resolved[0]` is — the SAME model
production uses for this call. Nothing is substituted on this path.

Every generated concept is dumped to JSON so the prefilter A/B can be replayed deterministically
(`probes/seed_prefilter_gate_ab.py`) without paying for generation again.

Usage:  .venv/bin/python probes/seed_prefilter_capture.py <checkpoint_dir> <trace.json> <repeats> <out.json>
Redirect to a file; never pipe.
"""
import json
import sys
from pathlib import Path

import nicheiq.utils.seed_fidelity as sf
from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def build_crew(checkpoint_dir: str, niche: str):
    from nicheiq.flows.research_flow import ResearchFlow

    flow = ResearchFlow(niche_description=niche, job_id="prefilter-probe")
    if not flow.resume_from_checkpoint(Path(checkpoint_dir)):
        raise RuntimeError(f"could not load checkpoint {checkpoint_dir}")
    state = flow.state
    crew = UnifiedSolutionCrew(
        pain_point_analysis=getattr(state, "pain_point_analysis", None),
        social_content=getattr(state, "social_content", None),
        allowed_project_types=flow.allowed_project_types,
        niche_context=getattr(state, "niche_context", None),
        audience_mapping=getattr(state, "audience_mapping", None),
        checkpoint_mgr=flow.checkpoint_mgr,
        job_id="prefilter-probe",
        competitor_mentions_text=getattr(state, "competitor_mentions_formatted", None),
        idea_focus=(getattr(flow, "idea_focus", "auto") or "auto"),
        cost_tracker=flow.cost_tracker,
    )
    crew.hydrate_from_state(state)
    return crew


def concept_row(pitch: str, c) -> dict:
    seed_tokens = sf._content_tokens(pitch)
    floor = max(1, (len(seed_tokens) * 3 + 4) // 5)
    retained = len(seed_tokens & sf._content_tokens(sf._candidate_identity_text(c)))
    routes = sf.unpitched_core_dependencies(pitch, c)
    return {
        "concept_name": getattr(c, "concept_name", None),
        "one_liner": getattr(c, "one_liner", None),
        "project_type": getattr(c, "project_type", None),
        "delivery_format": getattr(c, "delivery_format", None),
        "target_keywords": list(getattr(c, "target_keywords", None) or []),
        "why_non_obvious": getattr(c, "why_non_obvious", None),
        "ideation_technique": getattr(c, "ideation_technique", None),
        "data_access_model": getattr(c, "data_access_model", None),
        "data_acquisition_notes": getattr(c, "data_acquisition_notes", None),
        "retained": retained,
        "total_tokens": len(seed_tokens),
        "floor": floor,
        "retention_ok": retained >= floor,
        "routes": [str(r) for r in routes],
        "is_seed_faithful": sf.is_seed_faithful(pitch, c),
    }


def main():
    checkpoint_dir, trace_path, repeats, out_path = (
        sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
    trace = json.load(open(trace_path))
    pitch = trace["pitch"]
    identity_terms = trace["identity_terms"]

    # The live job's niche IS the pitch (checkpoint metadata) — pass it verbatim so the
    # checkpoint loads without a niche mismatch.
    crew = build_crew(checkpoint_dir, pitch)
    model, effort = settings.brainstorm_pool_resolved[0]
    print(f"GENERATOR MODEL (production, unsubstituted): {model} effort={effort}")
    seed_tokens = sf._content_tokens(pitch)
    print(f"pitch stemmed content tokens={len(seed_tokens)}  "
          f"retention floor={max(1, (len(seed_tokens) * 3 + 4) // 5)}")

    generated: list = []
    reached_tournament: list = []
    real_one_sample = UnifiedSolutionCrew._one_sample

    def recording_one_sample(self, *a, **kw):
        concepts, usages = real_one_sample(self, *a, **kw)
        generated.append(list(concepts))
        return concepts, usages

    def stub_score_concepts(self, concepts, idx=None):
        return []

    def stub_tournament(self, *, cell, candidates, search, usages, skip_selection=False):
        reached_tournament.append(list(candidates or []))
        return None

    UnifiedSolutionCrew._one_sample = recording_one_sample
    UnifiedSolutionCrew._score_concepts = stub_score_concepts
    UnifiedSolutionCrew._tournament_cell = stub_tournament

    samples = []
    for i in range(repeats):
        generated.clear()
        reached_tournament.clear()
        usages: list = []
        crew._run_seed_cell(seed_text=pitch, dispatch_id="seed", search=None,
                            usages=usages, identity_terms=identity_terms)
        gen = generated[0] if generated else []
        reached = reached_tournament[0] if reached_tournament else []
        rows = [concept_row(pitch, c) for c in gen]
        reached_rows = [concept_row(pitch, c) for c in reached]
        samples.append({"generated": rows, "reached_tournament": reached_rows})
        print(f"\n=== SAMPLE {i + 1}: {len(gen)} generated concept(s) ===")
        for n, r in enumerate(rows, 1):
            print(f"  [{n}] {r['concept_name']!r}")
            print(f"      one_liner: {(r['one_liner'] or '')[:120]!r}")
            print(f"      retention {r['retained']}/{r['total_tokens']} (floor {r['floor']}) -> "
                  f"{'PASS' if r['retention_ok'] else 'FAIL'}")
            print(f"      routes: {r['routes']}")
            print(f"      is_seed_faithful (routes AND retention): {r['is_seed_faithful']}")
        print(f"  -> reached the tournament: {len(reached)} candidate(s): "
              f"{[r['concept_name'] for r in reached_rows]}")

    json.dump({"pitch": pitch, "identity_terms": identity_terms,
               "model": model, "samples": samples},
              open(out_path, "w"), indent=1)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
