"""Unit tests for the Stage-5 ideation-quality fixes surfaced by job 65b05ea7 (peptides run):

- Fix #3a: _sources_pivoted / _carry_forward_fields no longer bleed pre-pivot mechanism text.
- Fix #3b: crew._provenance_segment_for_pain re-derives honest source_segment (or None).
- Fix #2 : derive_monetization_directive deterministic WTP-first prior.
"""
from __future__ import annotations

from types import SimpleNamespace

from nicheiq.crews.idea_improvement_loop import _carry_forward_fields, _sources_pivoted
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils.niche_difficulty import derive_monetization_directive


# ---------------------------------------------------------------- Fix #3a

_IDEA_FIELDS = dict(
    description="d", short_description="s", value_proposition="v", why_it_works="w",
    why_it_works_short="ws", technical_approach="", pricing_strategy="p",
    conventional_approach="c", data_acquisition_notes="n", core_features=["f"],
    target_personas=["t"], data_sources=[], differentiation_factors=[],
    pain_points_addressed=["pp"], market_fit_score=0.5, technical_feasibility_score=0.5,
    novelty_score=0.5,
)


def _idea(**over):
    return SimpleNamespace(**{**_IDEA_FIELDS, **over})


def test_sources_pivoted_detects_real_pivot():
    prior = _idea(data_sources=["WADA Prohibited List", "PubChem"])
    improved = _idea(data_sources=["FDA FAERS", "CBP seizure records", "FDA enforcement"])
    assert _sources_pivoted(improved, prior) is True


def test_sources_pivoted_ignores_cosmetic_rename():
    prior = _idea(data_sources=["FDA MAUDE"])
    improved = _idea(data_sources=["FDA MAUDE database"])
    assert _sources_pivoted(improved, prior) is False


def test_carry_forward_skips_mechanism_fields_on_pivot():
    prior = _idea(data_sources=["WADA Prohibited List"],
                  technical_approach="parse WADA PDFs quarterly",
                  differentiation_factors=["always-current WADA checker"])
    improved = _idea(data_sources=["FDA FAERS", "CBP seizures"],
                     technical_approach="", differentiation_factors=[])
    _carry_forward_fields(improved, prior)
    # Pivoted: the stale WADA text must NOT be reinstated.
    assert improved.technical_approach == ""
    assert improved.differentiation_factors == []


def test_carry_forward_still_fills_on_non_pivot():
    prior = _idea(data_sources=["FDA FAERS"],
                  technical_approach="FAERS ETL pipeline",
                  differentiation_factors=["FAERS co-report dashboards"])
    improved = _idea(data_sources=["FDA FAERS"],  # same route → not a pivot
                     technical_approach="", differentiation_factors=[])
    _carry_forward_fields(improved, prior)
    assert improved.technical_approach == "FAERS ETL pipeline"
    assert improved.differentiation_factors == ["FAERS co-report dashboards"]


# ---------------------------------------------------------------- Fix #2

def _pain(ci):
    return SimpleNamespace(commercial_intent=ci)


def _seg(pay):
    return SimpleNamespace(payability_score=pay)


def test_directive_weak_wallet_no_commercial_pain():
    from nicheiq.utils.niche_difficulty import has_zero_price_prescription

    out = derive_monetization_directive([_pain(0.2), _pain(0.3)], [_seg(0.15), _seg(0.2)])
    assert "weak-wallet niche" in out
    # The wallet FACT survives; the commercial shape it used to prescribe ("DEFAULT to a free
    # tool with distribution monetization ... NOT per-seat subscription") does not (D1 round 15).
    assert "mean segment payability" in out
    assert "commercial-intent bar" in out
    assert not has_zero_price_prescription(out)


def test_directive_mixed_niche_has_override():
    out = derive_monetization_directive([_pain(0.2), _pain(0.8)], [_seg(0.15), _seg(0.2)])
    assert "mostly weak-wallet" in out
    assert "WTP" in out  # keeps the per-pain override so the high-intent pain can still charge


def test_directive_viable_wallets():
    out = derive_monetization_directive([_pain(0.5)], [_seg(0.7), _seg(0.6)])
    assert "wallets look viable" in out


def test_directive_no_payability_data_is_neutral():
    out = derive_monetization_directive([_pain(0.5)], [])
    assert "MONETIZATION DIRECTIVE" in out
    assert "freemium subscription is not the automatic answer" in out


# ---------------------------------------------------------------- Fix #3b

def _bare_crew():
    return UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)


def test_provenance_segment_returns_affinity_match():
    crew = _bare_crew()
    seg = SimpleNamespace(segment_name="Metabolic Weight Seekers",
                          pain_point_alignment=["glp-1 weight loss nausea muscle"],
                          motivation_drivers=["metabolic health"])
    crew.audience_mapping = SimpleNamespace(audience_segments=[seg])
    pain = SimpleNamespace(title="GLP-1 muscle loss and nausea", categories=["weight"],
                           description="managing nausea on glp-1")
    crew.pain_point_analysis = SimpleNamespace(pain_points=[pain])
    assert crew._provenance_segment_for_pain(pain) == "Metabolic Weight Seekers"


def test_provenance_segment_none_when_no_affinity():
    crew = _bare_crew()
    seg = SimpleNamespace(segment_name="Competitive Bodybuilders",
                          pain_point_alignment=["muscle hypertrophy strength gains"],
                          motivation_drivers=["bodybuilding"])
    crew.audience_mapping = SimpleNamespace(audience_segments=[seg])
    pain = SimpleNamespace(title="Long COVID immune modulation guidance",
                           categories=["immune"], description="thymosin alpha-1 long covid")
    crew.pain_point_analysis = SimpleNamespace(pain_points=[pain])
    # No token overlap → honest None, not the arbitrary bodybuilder segment.
    assert crew._provenance_segment_for_pain(pain) is None


def test_provenance_segment_title_miss_degrades_to_none():
    crew = _bare_crew()
    crew.audience_mapping = SimpleNamespace(audience_segments=[])
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    assert crew._provenance_segment_for_pain("a pain title not in the list") is None


