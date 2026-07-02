"""P3b — fold beachhead demand MAGNITUDE into the ratio-based selection demand (dark until A/B'd).

The ratio-based keyword_demand_score ignores magnitude, so a thin-but-clean beachhead scores ~1.0
(observed live: MountLimit demand 0.98 vs beachhead 720/mo). demand_with_beachhead_magnitude blends in
a log-scaled niche-relevant volume so demand tracks real magnitude, floored (not zeroed) for thin ideas.
"""

import pytest

from nicheiq.utils.score_helpers import demand_with_beachhead_magnitude


def test_thin_beachhead_downweights_clean_ratio():
    # the live case: 0.98 ratio demand on a 720/mo beachhead → blended down toward reality
    d = demand_with_beachhead_magnitude(0.98, niche_relevant_volume=720, total_volume=187080)
    assert d == pytest.approx(0.776, abs=2e-3)   # 0.5*0.98 + 0.5*(log10(721)/5)
    assert d < 0.98  # magnitude pulls it down


def test_large_beachhead_keeps_demand_high():
    d = demand_with_beachhead_magnitude(0.98, niche_relevant_volume=100_000, total_volume=200_000)
    assert d == pytest.approx(0.99, abs=1e-3)  # magnitude ~1.0


def test_prefers_niche_relevant_over_total():
    # uses the 720 niche-relevant slice, NOT the 187k category total
    thin = demand_with_beachhead_magnitude(0.9, niche_relevant_volume=720, total_volume=187080)
    rich = demand_with_beachhead_magnitude(0.9, niche_relevant_volume=187080, total_volume=187080)
    assert thin < rich


def test_falls_back_to_total_when_niche_relevant_missing():
    # niche-relevant absent → use total_volume 50k: 0.5*0.9 + 0.5*(log10(50001)/5)
    d = demand_with_beachhead_magnitude(0.9, niche_relevant_volume=None, total_volume=50_000)
    assert d == pytest.approx(0.920, abs=3e-3)


def test_noop_when_no_volume():
    assert demand_with_beachhead_magnitude(0.98, None, 0) == 0.98
    assert demand_with_beachhead_magnitude(0.98, 0, 0) == 0.98


def test_explicit_zero_nrv_gets_no_magnitude_credit():
    """Bug-fix 2026-07-02 (cottage-food run): nrv == 0 means graded-and-NOTHING-passed — total_volume is
    then the drifted category number and must NOT be blended (it lifted demand 0.88→0.94 live). Neutral
    no-op instead."""
    assert demand_with_beachhead_magnitude(0.88, niche_relevant_volume=0, total_volume=1_628_480) == 0.88


def test_none_nrv_still_falls_back_to_total():
    # legacy/not-computed path unchanged: blends total_volume
    d = demand_with_beachhead_magnitude(0.9, niche_relevant_volume=None, total_volume=50_000)
    assert d == pytest.approx(0.920, abs=3e-3)
