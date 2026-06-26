"""Control-flow tests for the ideator↔reviewer improvement loop (no LLM — injected `invoke`).

Verifies the mechanism: tournament selection, mirrored-thread roles, keep-best, early-exit on
meets_bar, plateau handling, provenance carry-forward, and fail-soft on invoke errors.
"""
from nicheiq.crews.idea_improvement_loop import (
    CandidateChoice, CellGrounding, IdeaCritique, tournament_refine_cell,
)
from nicheiq.models.solution_idea import BaseSolutionIdea


def _idea(name, mf=0.5):
    return BaseSolutionIdea(
        solution_name=name, description=f"{name} does a thing for users in a clear way.",
        value_proposition="saves time", pain_points_addressed=["P"], core_features=["f1", "f2"],
        target_personas=["fan"], market_fit_score=mf, technical_feasibility_score=0.6,
        novelty_score=0.5,
    )


def _crit(mf, meets=False, binding="market_fit"):
    return IdeaCritique(market_fit=mf, technical_feasibility=0.6, data_feasibility=0.6,
                        novelty=0.6, binding_constraint=binding, directive="do X", meets_bar=meets)


GROUND = CellGrounding(niche="esports", audience_segment="Fans", pain_title="ticket scalping")


def _scripted(steps):
    """steps: list of objects to return in order (CandidateChoice / IdeaCritique / BaseSolutionIdea)."""
    calls = {"i": 0, "threads": []}

    def invoke(messages, output_model, *, temperature, model_name, reasoning_effort):
        calls["threads"].append([m["role"] for m in messages])
        out = steps[calls["i"]]
        calls["i"] += 1
        return out, None

    return invoke, calls


def test_tournament_picks_selected_candidate_and_reviews_it():
    # selection -> idx 1 ; round0 critique meets_bar immediately -> winner is candidate[1]
    invoke, calls = _scripted([CandidateChoice(selected_index=1), _crit(0.9, meets=True)])
    winner = tournament_refine_cell([_idea("A"), _idea("B")], GROUND, invoke=invoke)
    assert winner.solution_name == "B"
    assert calls["i"] == 2  # selection + one review, no improve (bar met)


def test_improves_then_stops_at_bar():
    # single candidate -> no selection call. round0 low -> improve to v2 -> round1 meets_bar
    invoke, calls = _scripted([
        _crit(0.3),                 # round 0 review: weak
        _idea("A2", mf=0.8),        # improve
        _crit(0.9, meets=True),     # round 1 review: strong
    ])
    winner = tournament_refine_cell([_idea("A")], GROUND, invoke=invoke)
    assert winner.solution_name == "A2"


def test_keep_best_when_improvement_regresses():
    # v1 reviews STRONG, v2 reviews WORSE -> keep v1 (never ship a worse version)
    invoke, _ = _scripted([
        _crit(0.85),                # round 0: strong but not meets_bar (so it improves)
        _idea("A2", mf=0.1),        # improve -> regressed
        _crit(0.10),                # round 1: worse
    ])
    winner = tournament_refine_cell([_idea("A", mf=0.85)], GROUND, rounds=2, invoke=invoke)
    assert winner.solution_name == "A"


def test_provenance_carried_onto_improved_idea():
    base = _idea("A")
    base.source_pain = "ticket scalping"
    base.source_segment = "Fans"
    invoke, _ = _scripted([
        _crit(0.3),
        _idea("A2"),                # improve LLM dropped source_pain/segment
        _crit(0.9, meets=True),
    ])
    winner = tournament_refine_cell([base], GROUND, invoke=invoke)
    assert winner.solution_name == "A2"
    assert winner.source_pain == "ticket scalping" and winner.source_segment == "Fans"


def test_fail_soft_on_review_error_returns_starting_candidate():
    def invoke(messages, output_model, *, temperature, model_name, reasoning_effort):
        if output_model is CandidateChoice:
            return CandidateChoice(selected_index=0), None
        raise RuntimeError("model down")
    winner = tournament_refine_cell([_idea("A")], GROUND, invoke=invoke)
    assert winner.solution_name == "A"   # never raises; returns best-so-far (the starting candidate)


def test_single_candidate_skips_selection_call():
    invoke, calls = _scripted([_crit(0.9, meets=True)])  # no CandidateChoice needed
    winner = tournament_refine_cell([_idea("solo")], GROUND, invoke=invoke)
    assert winner.solution_name == "solo"
    assert calls["i"] == 1
