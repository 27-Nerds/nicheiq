from types import SimpleNamespace

from nicheiq.utils.niche_difficulty import (
    TOOLING_DENSE,
    assess_niche_difficulty,
    derive_market_crowding_brief,
)
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _rows(count):
    return [{"name": f"Tool {i}", "pricing": "$20" if i % 2 == 0 else "free"} for i in range(count)]


def test_crowding_threshold_is_dense_at_eight_not_seven():
    assert not derive_market_crowding_brief(incumbent_map=_rows(TOOLING_DENSE - 1)).tooling_dense
    dense = derive_market_crowding_brief(incumbent_map=_rows(TOOLING_DENSE))
    assert dense.tooling_dense
    assert dense.incumbent_count == 8 and dense.priced_count == 4
    assert dense.key_point and dense.generator_directive


def test_empty_crowding_brief_is_neutral():
    brief = derive_market_crowding_brief()
    assert brief.incumbent_count == 0
    assert not brief.tooling_dense
    assert brief.key_point is None and brief.generator_directive is None


def test_crowding_brief_carries_preidea_addressability_wallet_and_payability():
    pains = [SimpleNamespace(tool_addressable="full"), SimpleNamespace(tool_addressable="partial")]
    segments = [SimpleNamespace(payability_score=0.2), SimpleNamespace(payability_score=0.6)]
    brief = derive_market_crowding_brief(
        pains, segments, {"wallet_class": "mixed", "free_density": "several free tools"}, [])
    assert brief.software_addressability == 0.7
    assert brief.segment_payability_mean == 0.4
    assert brief.wallet_class == "mixed" and brief.free_density == "several free tools"


def test_full_verdict_reuses_crowding_counts_and_exact_key_point():
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.5)]
    rows = _rows(8)
    brief = derive_market_crowding_brief(pains=pains, incumbent_map=rows)
    facts = assess_niche_difficulty(pains, [], SimpleNamespace(audience_scope=None), incumbent_map=rows)
    assert facts.incumbent_count == brief.incumbent_count
    assert facts.priced_count == brief.priced_count
    assert facts.key_points.count(brief.key_point) == 1


def test_existing_market_reality_block_consumes_single_crowding_authority():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew._incumbent_rows = _rows(8)
    crew._niche_wallet_brief = {}
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[])
    block = crew._build_market_reality_block()
    assert "Crowding authority:" in block
    assert block.count("Crowding authority:") == 1
    assert crew._market_crowding_brief.tooling_dense
