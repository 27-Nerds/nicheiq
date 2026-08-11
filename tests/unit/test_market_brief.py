"""build_market_brief — the Stage-2 market-reality handoff (mirrors test_angle_brief.py)."""

from types import SimpleNamespace

import pytest

from nicheiq.utils.market_brief import build_market_brief, parse_market_wallet_line
from nicheiq.utils.niche_difficulty import (
    has_zero_price_prescription,
    zero_price_model_contradicts_wallet,
)


def _state(**kwargs):
    defaults = {"niche_incumbent_map": [], "niche_wallet_brief": {}, "idea_ruled_out": []}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_empty_state_is_a_noop_except_for_the_wallet_line():
    out = build_market_brief(_state(), {"solution_name": "X"})
    assert out["market_brief"] == ""
    assert out["market_incumbent_table"] == ""
    # D1 round 16, Priority 4: '' is NOT a no-op for the wallet, because the pricing prompt reads
    # an empty wallet line as "no verified prices in this market" — the trigger of its zero-price
    # branch. A probe failure in a paying niche re-armed the very prescription this finding is
    # about, so an absent reading is now stated and the branch fails closed.
    assert out["market_wallet_line"] != ""
    assert "UNAVAILABLE" in out["market_wallet_line"]


def test_incumbent_parity_finding_front_loads_kill_question():
    solution = {
        "solution_name": "Selected",
        "incumbent_parity": "Aftershoot ships partial parity — depth/pricing/roadmap",
    }
    out = build_market_brief(_state(), solution)
    assert "VERIFY DEEPLY: Aftershoot ships partial parity" in out["market_brief"]
    assert "KILL-QUESTION" in out["market_brief"]


def test_none_found_parity_is_a_noop():
    solution = {"solution_name": "Selected", "incumbent_parity": "none found",
                "adjacent_market_parity": "None"}
    out = build_market_brief(_state(), solution)
    assert out["market_brief"] == ""


def test_adjacent_market_parity_included():
    solution = {"solution_name": "Selected", "adjacent_market_parity": "Zapier-adjacent automation exists"}
    out = build_market_brief(_state(), solution)
    assert "Adjacent-market parity" in out["market_brief"]
    assert "Zapier-adjacent automation exists" in out["market_brief"]


def test_sibling_ruled_out_ideas_become_substitute_pressure_context_excluding_self():
    ruled_out = [
        {"idea_name": "Other Idea", "pain_title": "p1", "reason": "buyers wont pay"},
        {"idea_name": "Selected", "pain_title": "p2", "reason": "should be excluded (self)"},
    ]
    out = build_market_brief(_state(idea_ruled_out=ruled_out), {"solution_name": "Selected"})
    assert "Other Idea" in out["market_brief"]
    assert "buyers wont pay" in out["market_brief"]
    assert "should be excluded (self)" not in out["market_brief"]


def test_incumbent_table_formats_rows():
    incumbents = [{"name": "Aftershoot", "pricing": "$29/mo", "focus": "AI culling", "gap": "no galleries"}]
    out = build_market_brief(_state(niche_incumbent_map=incumbents), {"solution_name": "X"})
    assert "Aftershoot" in out["market_incumbent_table"]
    assert "$29/mo" in out["market_incumbent_table"]
    assert "no galleries" in out["market_incumbent_table"]


def test_wallet_line_includes_class_and_evidence():
    wallet = {"wallet_class": "mixed", "evidence": "most tools $10-30/mo", "free_density": "few free routes"}
    out = build_market_brief(_state(niche_wallet_brief=wallet), {"solution_name": "X"})
    assert "mixed" in out["market_wallet_line"]
    assert "most tools $10-30/mo" in out["market_wallet_line"]


def test_reads_model_attrs_not_just_dict():
    solution = SimpleNamespace(solution_name="X", incumbent_parity="Some Tool covers this",
                                adjacent_market_parity=None)
    out = build_market_brief(_state(), solution)
    assert "Some Tool covers this" in out["market_brief"]


def test_seo_crew_market_vars_reads_constructor_precomputed_dict():
    import nicheiq.crews.seo_strategy_crew as sc
    crew = sc.SEOStrategyCrew.__new__(sc.SEOStrategyCrew)
    crew._market_brief_vars = {"market_brief": "brief text", "market_incumbent_table": "table text"}
    out = crew._market_vars()
    assert out["market_brief"] == "brief text"
    assert out["market_incumbent_table"] == "table text"
    assert out["market_wallet_line"] == ""  # missing key defaults to empty, not KeyError


def test_seo_crew_market_vars_noop_when_no_brief_passed():
    import nicheiq.crews.seo_strategy_crew as sc
    crew = sc.SEOStrategyCrew.__new__(sc.SEOStrategyCrew)
    crew._market_brief_vars = {}
    assert crew._market_vars() == {
        "market_brief": "", "market_incumbent_table": "", "market_wallet_line": ""
    }


# --------------------------------------------------------------------------------------------
# D1 round 16, Priority 4 — an absent wallet reading must fail CLOSED.
# --------------------------------------------------------------------------------------------



@pytest.mark.parametrize("wallet", [None, {}, {"wallet_class": ""}, {"wallet_class": "   "}])
def test_a_missing_wallet_probe_says_so_instead_of_going_silent(wallet):
    """The hole: `{}` from the probe rendered as '', and '' reads downstream as a FINDING.

    `pricing_strategy_tasks.yaml` gates its zero-price branch on the market showing no verified
    prices. An empty gate is indistinguishable from that finding, so a probe FAILURE in a
    demonstrably paying niche re-armed the prescription.
    """
    out = build_market_brief(_state(niche_wallet_brief=wallet), {"solution_name": "X"})
    line = out["market_wallet_line"]
    assert "UNAVAILABLE" in line
    assert "not a finding" in line
    assert "does NOT apply" in line
    # The line itself must not be a prescription — it is read by an LLM as prompt context.
    assert not has_zero_price_prescription(line)


def test_an_absent_reading_parses_back_as_no_reading_never_as_a_wallet_class():
    """Consumers get the rendered LINE, not the probe dict, so the parse is the contract."""
    absent = build_market_brief(_state(), {"solution_name": "X"})["market_wallet_line"]
    assert parse_market_wallet_line(absent) == ("", "")
    assert parse_market_wallet_line("") == ("", "")
    assert parse_market_wallet_line("something else entirely") == ("", "")

    priced = build_market_brief(
        _state(niche_wallet_brief={"wallet_class": "paying", "evidence": "$99-399/mo DaySmart"}),
        {"solution_name": "X"},
    )["market_wallet_line"]
    assert parse_market_wallet_line(priced) == ("paying", "$99-399/mo DaySmart")

    no_evidence = build_market_brief(
        _state(niche_wallet_brief={"wallet_class": "free-culture"}), {"solution_name": "X"}
    )["market_wallet_line"]
    assert parse_market_wallet_line(no_evidence) == ("free-culture", "")


def test_an_absent_reading_never_licenses_a_zero_price_model():
    """Absence of evidence is not evidence of absence, all the way to the structured field."""
    absent = parse_market_wallet_line(
        build_market_brief(_state(), {"solution_name": "X"})["market_wallet_line"]
    )
    # Nothing is CONTRADICTED by an absent reading either — it is simply not a finding. The
    # fail-closed behaviour lives in the prompt gate; what must never happen is the absent reading
    # being parsed back as a wallet class that reads like "nobody here pays".
    assert absent == ("", "")
    assert not zero_price_model_contradicts_wallet("Ad-Supported-Free", *absent)
