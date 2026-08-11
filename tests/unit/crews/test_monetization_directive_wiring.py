"""D1 round 15, Priority 2 — the paying-wallet directive must be REACHABLE in production.

`derive_monetization_directive(pains, segments, niche_wallet_brief=None)` had a verified-paying
branch that fired in unit tests and nowhere else: both production call sites omitted the third
argument, so a niche with web-verified prices still had
"DEFAULT to a free tool with distribution monetization (ads / affiliate / lead-gen), NOT per-seat
subscription" injected into the same generator prompt block that printed
"documented tooling spend is 'paying' — Truckstop $42-159/mo".

Nothing about that failure was semantic. It was an omitted positional argument, and no amount of
prose review of the directive itself could have found it — so it is guarded structurally (every
call site passes a wallet argument) and behaviourally (the seed path actually produces the
paying-wallet directive when the probe found prices).
"""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils import niche_difficulty as nd

_CREW_SOURCE = Path(nd.__file__).parents[1] / "crews" / "unified_solution_crew.py"


def _directive_call_sites() -> list[ast.Call]:
    tree = ast.parse(_CREW_SOURCE.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "derive_monetization_directive"
    ]


def test_every_call_site_passes_the_wallet_brief():
    """The defect class is an omitted argument, so the guard reads the call, not the prose."""
    calls = _directive_call_sites()
    assert len(calls) >= 2, "expected the execute_pipeline and seed call sites"
    for call in calls:
        supplied = len(call.args) + len(call.keywords)
        assert supplied >= 3, (
            f"{_CREW_SOURCE.name}:{call.lineno} calls derive_monetization_directive with "
            f"{supplied} argument(s). Without the wallet brief the verified-paying branch is "
            "unreachable and the generator can be steered away from charging in a niche whose "
            "own prices this run verified."
        )


def _seed_crew(monkeypatch, wallet_brief):
    pain = SimpleNamespace(
        title="Reconciling controlled-substance logs",
        description="A repeated operational pain.",
        representative_quotes=["This wastes hours every week."],
        opportunity_level=SimpleNamespace(value="high"),
        severity_score=0.8,
        commercial_intent=0.2,
    )
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.pain_point_analysis = SimpleNamespace(
        pain_points=[pain],
        content_categorization=None,
        analysis_summary="Test analysis",
        top_categories=[],
        total_mentions=10,
    )
    crew.niche_context = None
    crew.audience_mapping = SimpleNamespace(
        audience_segments=[SimpleNamespace(segment_name="solo vets", payability_score=0.1)]
    )
    crew.allowed_project_types = None
    crew.existing_ideas = []
    crew.cost_tracker = None
    crew._niche_wallet_brief = wallet_brief

    import nicheiq.utils.pain_point_formatters as pain_formatters

    monkeypatch.setattr(
        pain_formatters, "extract_pain_points_by_priority", lambda analysis: ([pain], [], [])
    )
    monkeypatch.setattr(pain_formatters, "format_pain_points_for_agents", lambda **kwargs: "pain")
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_audience_context", lambda self: {})
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_competitor_mentions", lambda self: "")
    monkeypatch.setattr(UnifiedSolutionCrew, "_segment_payability_map", lambda self: {})
    monkeypatch.setattr(
        UnifiedSolutionCrew, "_probe_niche_wallet", lambda self: self._niche_wallet_brief or {}
    )
    monkeypatch.setattr(UnifiedSolutionCrew, "_wallet_prompt_line", lambda self: "")
    return crew


@pytest.mark.parametrize("wallet_brief", [
    {"wallet_class": "paying", "evidence": "$99-399/mo DaySmart Vet"},
    # A `mixed` reading whose evidence quotes real prices is the SAME contradiction — the
    # classifier's bucket is not what makes a prescription contradict a price list.
    {"wallet_class": "mixed", "evidence": "Truckstop $42-159/mo, DAT $45/mo"},
])
def test_priced_wallet_reaches_the_generator_directive(monkeypatch, wallet_brief):
    crew = _seed_crew(monkeypatch, wallet_brief)

    directive = crew._build_seed_crew_inputs()["monetization_directive"]

    assert nd._PAYING_WALLET_MONETIZATION_DIRECTIVE in directive
    assert not nd.has_zero_price_prescription(directive)
    # The corpus signals here (commercial_intent 0.2, payability 0.1) are exactly the weak-wallet
    # combination that used to win, which is what made the contradiction reproducible.
    assert "weak-wallet niche" not in directive


def test_unpriced_wallet_still_gets_the_corpus_derived_directive(monkeypatch):
    """The wallet brief overrides the corpus branch; it does not delete it."""
    crew = _seed_crew(monkeypatch, {"wallet_class": "free-culture", "evidence": "all routes free"})

    directive = crew._build_seed_crew_inputs()["monetization_directive"]

    assert "weak-wallet niche" in directive
    assert nd._PAYING_WALLET_MONETIZATION_DIRECTIVE not in directive
    assert not nd.has_zero_price_prescription(directive)


def test_the_refine_prompt_carries_no_ladder_of_its_own():
    """`_refine_single_concept` built its own WTP ladder, wallet-blind, as a second license.

    It is deleted rather than gated: the directive it already interpolates is wallet-derived and
    is now the single source (Priority 3).
    """
    import inspect

    source = inspect.getsource(UnifiedSolutionCrew._refine_single_concept)
    pricing_block = source.split("pricing_directive = (", 1)[1].split(")\n", 1)[0]
    for banned in ("FREE tool", "lead-gen", "affiliate", "per-seat"):
        assert banned not in pricing_block, (
            f"{banned!r} reappeared in _refine_single_concept's inline pricing block"
        )
    assert "_monetization_directive" in pricing_block
