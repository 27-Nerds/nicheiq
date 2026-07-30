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


class TestPayabilityFloor:
    def _t(self):
        return VerdictValidator(ScoreThresholds())

    def test_low_payability_direct_paid_caps_go(self):
        v, r, c, ctx = self._t().apply_payability_downgrade(
            "Go", "Low", None, payability=0.25, payability_class="personal-wallet",
            monetization="subscription")
        assert v == "Conditional" and r == "Medium"
        assert ctx and "spending personal money" in ctx      # human phrase, not the enum token
        assert "personal-wallet" not in ctx                  # raw class token never shown
        assert not re.search(r"\d\.\d", ctx)                # band-clean: no decimals
        assert c and "willingness-to-pay" in c

    def test_unscored_payability_abstains(self):
        v, _r, _c, ctx = self._t().apply_payability_downgrade(
            "Go", "Low", None, payability=None, payability_class=None,
            monetization="subscription")
        assert v == "Go" and ctx is None

    def test_above_threshold_abstains(self):
        v, _r, _c, ctx = self._t().apply_payability_downgrade(
            "Go", "Low", None, payability=0.6, payability_class="smb-budget",
            monetization="subscription")
        assert v == "Go" and ctx is None

    def test_non_direct_paid_abstains(self):
        # ads/affiliate/commission plays don't need the buyer's wallet
        for m in ("advertising", "affiliate", "commission", None):
            v, _r, _c, ctx = self._t().apply_payability_downgrade(
                "Go", "Low", None, payability=0.25, payability_class="personal-wallet",
                monetization=m)
            assert v == "Go" and ctx is None, m

    def test_never_upgrades_no_go_and_keeps_conditional(self):
        v, r, _c, ctx = self._t().apply_payability_downgrade(
            "No-Go", "High", "x", payability=0.2, payability_class="personal-wallet",
            monetization="one-time")
        assert v == "No-Go" and r == "High" and ctx is not None
        v2, _r2, _c2, _ctx2 = self._t().apply_payability_downgrade(
            "Conditional", "Medium", "y", payability=0.2,
            payability_class="personal-wallet", monetization="usage-based")
        assert v2 == "Conditional"

    def test_existing_concern_not_overwritten(self):
        _v, _r, c, _ctx = self._t().apply_payability_downgrade(
            "Go", "Low", "existing concern", payability=0.2,
            payability_class="personal-wallet", monetization="subscription")
        assert c == "existing concern"

    def test_payability_context_field_on_verdict_model(self):
        from nicheiq.models.executive_summary import GoNoGoVerdict
        v = GoNoGoVerdict(verdict="Conditional", rationale="r", risk_level="Medium",
                          payability_context="Buyer payability: …")
        assert v.payability_context.startswith("Buyer payability")


class TestRedTeamFloor:
    """Phase 5.5 (run-quality fixes §1): adversarial weakened/killed findings reach the verdict."""

    def _t(self):
        return VerdictValidator(ScoreThresholds())

    def test_weakened_caps_go_and_floors_risk(self):
        v, r, c, ctx = self._t().apply_red_team_downgrade(
            "Go", "Low", None, red_team_verdict="weakened",
            red_team_caveats=["Krock.io ships this identically"])
        assert v == "Conditional" and r == "Medium"
        assert ctx and "weakened" in ctx and "Krock.io" in ctx
        assert c and "weakened" in c

    def test_killed_floors_risk_to_high(self):
        v, r, c, ctx = self._t().apply_red_team_downgrade(
            "Conditional", "Medium", None, red_team_verdict="killed",
            red_team_caveats=["deterministic COA checks cannot detect fabricated certificates"])
        assert v == "Conditional" and r == "High"
        assert ctx and "killed" in ctx
        assert c and "refuted" in c

    def test_survives_and_none_abstain(self):
        for rt in ("survives", None, ""):
            v, r, c, ctx = self._t().apply_red_team_downgrade(
                "Go", "Low", None, red_team_verdict=rt, red_team_caveats=None)
            assert v == "Go" and r == "Low" and c is None and ctx is None, rt

    def test_never_forces_no_go(self):
        v, r, _c, ctx = self._t().apply_red_team_downgrade(
            "Conditional", "Medium", "x", red_team_verdict="weakened", red_team_caveats=[])
        assert v == "Conditional" and r == "Medium" and ctx is not None

    def test_existing_concern_not_overwritten(self):
        _v, _r, c, _ctx = self._t().apply_red_team_downgrade(
            "Go", "Low", "existing concern", red_team_verdict="killed",
            red_team_caveats=["caveat"])
        assert c == "existing concern"

    def test_caveat_truncated_to_200_chars(self):
        _v, _r, _c, ctx = self._t().apply_red_team_downgrade(
            "Go", "Low", None, red_team_verdict="weakened",
            red_team_caveats=["z" * 500])
        assert ctx and "z" * 200 in ctx and "z" * 201 not in ctx

    def test_red_team_context_field_on_verdict_model(self):
        from nicheiq.models.executive_summary import GoNoGoVerdict
        v = GoNoGoVerdict(verdict="Conditional", rationale="r", risk_level="High",
                          red_team_context="Red-team review: …")
        assert v.red_team_context.startswith("Red-team review")
