"""SEO kill-question verdict floor (Phase 4): downgrade-only, keyed on a KD-coverage-gated winnable
SHARE / median KD (the axis the SEO composite excludes), penalty_risk strictly secondary (de-duped vs
the Rule-B thin-page cap). The coverage gate (A/B-driven, 2026-06-30) makes the floor abstain when KD
coverage is too sparse to trust winnable/median_kd — DataForSEO omits KD for many easy long-tail intents."""

import re

from nicheiq.validators.score_validators import ScoreThresholds, VerdictValidator


def _v():
    return VerdictValidator(ScoreThresholds())


class TestSeoKillFloor:
    def test_no_winnable_universe_caps_go(self):
        v, r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=0, median_keyword_difficulty=20.0, penalty_risk_flag=False,
            kd_sample_size=60, page_ceiling=100)
        assert v == "Conditional" and r == "Medium"
        assert ctx and "winnable" in ctx.lower()
        assert not re.search(r"\d\.\d", ctx)  # band-clean

    def test_healthy_universe_unchanged(self):
        v, r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=120, median_keyword_difficulty=15.0, penalty_risk_flag=False,
            kd_sample_size=140, page_ceiling=150)
        assert v == "Go" and r == "Low" and ctx is None

    def test_high_kd_fires(self):
        v, _r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=120, median_keyword_difficulty=70.0, penalty_risk_flag=False,
            kd_sample_size=140, page_ceiling=150)
        assert v == "Conditional" and ctx is not None

    def test_penalty_risk_alone_does_not_fire(self):
        # winnable + KD both fine; penalty_risk is secondary (overlaps Rule-B) → no floor
        v, r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=120, median_keyword_difficulty=15.0, penalty_risk_flag=True,
            kd_sample_size=140, page_ceiling=150)
        assert v == "Go" and ctx is None

    def test_downgrade_only_never_upgrades(self):
        v, _r, _c, _ctx = _v().apply_seo_kill_downgrade("No-Go", "High", "x",
            winnable_pages=0, median_keyword_difficulty=20.0, penalty_risk_flag=False,
            kd_sample_size=60, page_ceiling=100)
        assert v == "No-Go"  # caps Go only; never lifts

    def test_existing_concern_not_overwritten(self):
        _v_, _r, c, _ctx = _v().apply_seo_kill_downgrade("Go", "Low", "existing concern",
            winnable_pages=0, median_keyword_difficulty=20.0, penalty_risk_flag=False,
            kd_sample_size=60, page_ceiling=100)
        assert c == "existing concern"


class TestSeoKillCoverageGate:
    def test_sparse_coverage_abstains(self):
        # The real ab-angle-seo2 artifact: winnable=1 / median_kd=63 looks catastrophic, but only 6 of
        # 439 intents carried a KD value → the floor must NOT fire on missing data.
        v, r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=1, median_keyword_difficulty=63.0, penalty_risk_flag=False,
            kd_sample_size=6, page_ceiling=439)
        assert v == "Go" and r == "Low" and ctx is None

    def test_low_kd_sample_abstains(self):
        # Coverage fraction is fine (20/30) but the absolute KD sample is below the minimum → abstain.
        v, _r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=0, median_keyword_difficulty=20.0, penalty_risk_flag=False,
            kd_sample_size=20, page_ceiling=30)
        assert v == "Go" and ctx is None

    def test_share_based_fires_above_old_absolute_threshold(self):
        # 10 winnable pages would have passed the OLD absolute (<=5) test, but as a SHARE of 100 KD'd
        # intents it's only 0.10 (< 0.15) → the floor correctly fires on a thin winnable share.
        v, _r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=10, median_keyword_difficulty=30.0, penalty_risk_flag=False,
            kd_sample_size=100, page_ceiling=120)
        assert v == "Conditional" and ctx is not None

    def test_healthy_share_with_low_absolute_count_unchanged(self):
        # 10 winnable on 40 KD'd intents = 0.25 share (healthy) → no fire despite a modest absolute count.
        v, r, _c, ctx = _v().apply_seo_kill_downgrade("Go", "Low", None,
            winnable_pages=10, median_keyword_difficulty=30.0, penalty_risk_flag=False,
            kd_sample_size=40, page_ceiling=50)
        assert v == "Go" and r == "Low" and ctx is None
