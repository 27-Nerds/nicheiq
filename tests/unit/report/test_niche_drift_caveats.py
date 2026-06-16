"""Phase-4: niche-drift observability caveats in the data-quality summary.

These caveats are NON-scoring: they must appear when drift telemetry is poor but
must NOT change the tier/confidence numbers.
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.report.report_generator import ReportGenerator


def _generator(telemetry=None, coverage_caveats=None):
    state = MagicMock()
    state.seeded_from_catalog = False
    state.social_content_quality_tier = "EXCELLENT"
    state.pain_point_quality_tier = "GOLD"
    state.pain_point_confidence_score = 0.97
    state.seo_strategy_report = None
    state.fallback_stages = []
    state.filtering_stats = {}
    state.niche_drift_telemetry = telemetry or {}
    state.idea_coverage_caveats = coverage_caveats or []
    gen = ReportGenerator(state)
    gen.accessor = MagicMock()
    gen.accessor.get_volume_filter_ratio.return_value = None
    return gen


def test_low_coverage_emits_caveat_without_changing_tier():
    gen = _generator(telemetry={"anchors_active": True, "pain_evidence_anchor_coverage": 0.1})
    summary = gen._generate_data_quality_summary()
    assert any("Niche-fidelity" in c for c in summary.quality_caveats)
    # Tier/confidence are unchanged (EXCELLENT x GOLD => HIGH).
    assert summary.overall_data_quality == "HIGH"
    assert summary.pain_point_confidence_score == 0.97


def test_healthy_coverage_no_caveat():
    gen = _generator(telemetry={"anchors_active": True, "pain_evidence_anchor_coverage": 0.85})
    summary = gen._generate_data_quality_summary()
    assert not any("Niche-fidelity" in c for c in summary.quality_caveats)
    assert summary.overall_data_quality == "HIGH"


def test_on_niche_partial_coverage_does_not_false_positive():
    # Calibrated on real runs: a clearly on-niche run scored ~0.29 (most on-niche
    # quotes lack a literal anchor token); it must NOT trip the drift caveat.
    gen = _generator(telemetry={"anchors_active": True, "pain_evidence_anchor_coverage": 0.29})
    summary = gen._generate_data_quality_summary()
    assert not any("Niche-fidelity" in c for c in summary.quality_caveats)


def test_clearly_drifted_run_fires():
    # A clearly-drifted run scored ~0.05; it should fire.
    gen = _generator(telemetry={"anchors_active": True, "pain_evidence_anchor_coverage": 0.05})
    summary = gen._generate_data_quality_summary()
    assert any("Niche-fidelity" in c for c in summary.quality_caveats)


def test_inactive_anchors_emits_caveat():
    gen = _generator(telemetry={"anchors_active": False})
    summary = gen._generate_data_quality_summary()
    assert any("drift protection inactive" in c for c in summary.quality_caveats)


def test_low_query_anchor_pct_emits_caveat():
    gen = _generator(telemetry={"anchors_active": True, "query_anchor_pct": 0.2})
    summary = gen._generate_data_quality_summary()
    assert any("niche-anchored" in c for c in summary.quality_caveats)


def test_idea_coverage_caveats_surface():
    gen = _generator(coverage_caveats=["High-severity pain 'X' is not addressed by any solution."])
    summary = gen._generate_data_quality_summary()
    assert any("not addressed" in c for c in summary.quality_caveats)
