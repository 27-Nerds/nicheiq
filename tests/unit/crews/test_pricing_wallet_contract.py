"""D1 round 16, Priority 1 — Stage 7 is where the report NAMES the money model, and until now
nothing validated that field against the market's own verified prices.

`pricing_strategy` chooses `PricingStrategyResult.pricing_model`, whose Literal still admits
`Ad-Supported-Free` and `Affiliate-Only` with `recommended_starter_price: null`. Every previous
round of this finding tightened PROSE — constants, prompts, verdict cards. The one place the
report states the money model as a structured field had no contract at all, so the crew could
return "free forever" in the same report whose MARKET REALITY block quotes the incumbents'
monthly prices.

Two layers, and both matter:
  * the GUARDRAIL refuses the output, which gives CrewAI a fresh call to correct it (a guardrail
    cannot repair output, only refuse it — see CLAUDE.md);
  * `analyze()` drops the result entirely if the contradiction survives the retries, because a
    missing pricing section is recoverable and a report that contradicts itself about money is
    the finding.
"""

from types import SimpleNamespace

import pytest

import nicheiq.crews.pricing_strategy_crew as psc
from nicheiq.crews.pricing_strategy_crew import PricingStrategyCrew
from nicheiq.utils.market_brief import build_market_brief
from nicheiq.utils.niche_difficulty import zero_price_model_contradicts_wallet

_PAYING = "Niche wallet signal: paying — $99-399/mo DaySmart Vet, $150/mo ezyVet"
_PRICED_MIXED = "Niche wallet signal: mixed — Truckstop $42-159/mo, many run on spreadsheets"
_UNPRICED_MIXED = "Niche wallet signal: mixed — quotes only, no published prices found"
_FREE_CULTURE = "Niche wallet signal: free-culture — every established route here is free"


def _crew(wallet_line: str) -> PricingStrategyCrew:
    crew = PricingStrategyCrew.__new__(PricingStrategyCrew)
    crew._wallet_reading = psc.parse_market_wallet_line(wallet_line)
    return crew


def _output(model: str):
    return SimpleNamespace(pydantic=SimpleNamespace(pricing_model=model, solution_name="X"))


# --------------------------------------------------------------------------------------------
# The predicate.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["Ad-Supported-Free", "Affiliate-Only"])
@pytest.mark.parametrize("wallet_class,evidence", [
    ("paying", "$99-399/mo DaySmart Vet"),
    ("mixed", "Truckstop $42-159/mo"),
    ("Paying", "$150/mo"),
])
def test_a_zero_price_model_contradicts_a_wallet_with_verified_prices(model, wallet_class, evidence):
    assert zero_price_model_contradicts_wallet(model, wallet_class, evidence)


@pytest.mark.parametrize("model,wallet_class,evidence", [
    # Every model that keeps a price on some tier is compatible with any wallet.
    ("Freemium", "paying", "$99/mo"),
    ("Subscription", "paying", "$99/mo"),
    ("Hybrid", "paying", "$99/mo"),
    ("One-time", "mixed", "$42-159/mo"),
    ("Usage-Based", "mixed", "$42-159/mo"),
    # ...and a zero-price model contradicts nothing where no price was verified.
    ("Ad-Supported-Free", "free-culture", "every route here is free"),
    ("Ad-Supported-Free", "mixed", "quotes only, no prices published"),
    ("Affiliate-Only", "", ""),
    ("Affiliate-Only", None, None),
    # `paying` with no evidence at all is not a verified reading.
    ("Ad-Supported-Free", "paying", ""),
])
def test_the_contract_is_silent_where_no_price_was_verified(model, wallet_class, evidence):
    assert not zero_price_model_contradicts_wallet(model, wallet_class, evidence)


# --------------------------------------------------------------------------------------------
# The guardrail.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("wallet_line", [_PAYING, _PRICED_MIXED])
@pytest.mark.parametrize("model", ["Ad-Supported-Free", "Affiliate-Only"])
def test_the_guardrail_refuses_a_free_model_in_a_market_with_verified_prices(wallet_line, model):
    ok, reason = _crew(wallet_line)._wallet_contract_guardrail(_output(model), _output(model))
    assert ok is False
    # The retry prompt is the only thing the next call sees, so it has to carry the evidence.
    assert model in reason
    assert "verified prices" in reason
    assert "Hybrid" in reason, "the retry must be told what a legitimate correction looks like"


@pytest.mark.parametrize("wallet_line", [_UNPRICED_MIXED, _FREE_CULTURE, ""])
@pytest.mark.parametrize("model", ["Ad-Supported-Free", "Affiliate-Only"])
def test_the_guardrail_permits_a_free_model_where_nothing_priced_was_verified(wallet_line, model):
    payload = _output(model)
    assert _crew(wallet_line)._wallet_contract_guardrail(payload, payload) == (True, payload)


@pytest.mark.parametrize("model", ["Freemium", "Subscription", "Hybrid", "One-time", "Usage-Based"])
def test_the_guardrail_never_touches_a_priced_model(model):
    payload = _output(model)
    assert _crew(_PAYING)._wallet_contract_guardrail(payload, payload) == (True, payload)


def test_an_unavailable_wallet_reading_does_not_arm_the_guardrail_either():
    """Fail-closed lives in the prompt gate; the guardrail must not invent a finding from absence."""
    absent = build_market_brief(
        SimpleNamespace(niche_incumbent_map=[], niche_wallet_brief={}, idea_ruled_out=[]),
        {"solution_name": "X"},
    )["market_wallet_line"]
    payload = _output("Ad-Supported-Free")
    assert _crew(absent)._wallet_contract_guardrail(payload, payload) == (True, payload)


def test_the_guardrail_runs_after_the_existing_numeric_validation(monkeypatch):
    """Ordering matters: an unparseable output must still fail with its ORIGINAL reason."""
    crew = _crew(_PAYING)
    crew._suggested_cac_range = None
    monkeypatch.setattr(psc, "validate_pricing_strategy", lambda *a, **k: (False, "bad JSON"))
    assert crew._pricing_guardrail(_output("Ad-Supported-Free")) == (False, "bad JSON")

    monkeypatch.setattr(
        psc, "validate_pricing_strategy", lambda task_output, **k: (True, task_output)
    )
    ok, reason = crew._pricing_guardrail(_output("Ad-Supported-Free"))
    assert ok is False and "Ad-Supported-Free" in reason


# --------------------------------------------------------------------------------------------
# The assembly point: what `analyze()` returns when the retries did not fix it.
# --------------------------------------------------------------------------------------------


def _analyze(monkeypatch, wallet_line: str, model: str):
    crew = PricingStrategyCrew.__new__(PricingStrategyCrew)
    for method in (
        "_extract_competitor_pricing", "_extract_wtp_scores", "_format_solution_features",
        "_format_target_personas", "_extract_competitive_context",
    ):
        monkeypatch.setattr(PricingStrategyCrew, method, lambda *a, **k: "", raising=True)
    monkeypatch.setattr(psc, "compute_wtp_summary", lambda *a: ("summary", 0.5))
    monkeypatch.setattr(psc, "compute_cac_range", lambda *a: "$10-30")
    monkeypatch.setattr(psc, "format_idea_cac", lambda *a: "no estimate")
    monkeypatch.setattr(psc, "format_market_sizing_summary", lambda *a: "")
    monkeypatch.setattr(psc, "format_audience_budget_sensitivity", lambda *a: "")
    monkeypatch.setattr(psc, "format_solution_rank_context", lambda *a: "")

    result = SimpleNamespace(
        pydantic=SimpleNamespace(
            solution_name="X", pricing_model=model, recommended_starter_price=None,
            recommended_pro_price=None, estimated_arpu="$0.02/pageview",
            pricing_confidence="Medium",
        )
    )
    monkeypatch.setattr(
        PricingStrategyCrew, "crew",
        lambda self: SimpleNamespace(kickoff=lambda inputs: result, usage_metrics=None),
    )
    return crew.analyze(
        selected_solution=SimpleNamespace(
            solution_name="X", description="d", market_fit_score=0.5, project_type="directory",
            value_proposition="v",
        ),
        pain_point_analysis=None,
        competitive_analysis=None,
        niche_description="vet clinics",
        market_wallet_line=wallet_line,
    )


@pytest.mark.parametrize("wallet_line", [_PAYING, _PRICED_MIXED])
@pytest.mark.parametrize("model", ["Ad-Supported-Free", "Affiliate-Only"])
def test_analyze_drops_a_contradicting_result_rather_than_publishing_it(
    monkeypatch, wallet_line, model
):
    assert _analyze(monkeypatch, wallet_line, model) is None


@pytest.mark.parametrize("wallet_line,model", [
    (_PAYING, "Freemium"),
    (_PRICED_MIXED, "Subscription"),
    (_FREE_CULTURE, "Ad-Supported-Free"),
    (_UNPRICED_MIXED, "Affiliate-Only"),
    ("", "Ad-Supported-Free"),
])
def test_analyze_returns_every_result_that_does_not_contradict_the_wallet(
    monkeypatch, wallet_line, model
):
    out = _analyze(monkeypatch, wallet_line, model)
    assert out is not None and out.pricing_model == model
