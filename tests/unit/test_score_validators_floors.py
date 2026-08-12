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
        # The finding must reach the reader; the ENUM must not. This block is the go/no-go
        # prose — the most prominent text in the report — and it read "an adversarial
        # evidence probe weakened this idea" until 2026-08-03.
        assert ctx and "decision-critical objection" in ctx and "Krock.io" in ctx
        assert "weakened" not in ctx.lower()
        assert c and "decision-critical objection" in c
        assert "weakened" not in c.lower()

    def test_killed_floors_risk_to_high(self):
        v, r, c, ctx = self._t().apply_red_team_downgrade(
            "Conditional", "Medium", None, red_team_verdict="killed",
            red_team_caveats=["deterministic COA checks cannot detect fabricated certificates"])
        assert v == "Conditional" and r == "High"
        assert ctx and "could not find evidence for this idea's premise" in ctx
        assert "killed" not in ctx.lower()
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

    def test_typed_affirmative_kill_reports_verified_counterevidence(self):
        _v, risk, concern, context = self._t().apply_red_team_downgrade(
            "Conditional",
            "Medium",
            None,
            red_team_verdict="killed",
            red_team_caveats=["legacy compatibility claim"],
            red_team_findings=[{
                "kind": "verified_incumbent_overlap",
                "claim": "Named vendor ships the core workflow.",
            }],
        )

        assert risk == "High"
        assert context and "verified counterevidence" in context
        assert "Named vendor" in context
        assert concern and "verified counterevidence" in concern

    def test_typed_gap_only_weakness_reports_incomplete_evidence(self):
        _v, risk, concern, context = self._t().apply_red_team_downgrade(
            "Go",
            "Low",
            None,
            red_team_verdict="weakened",
            red_team_caveats=["legacy compatibility claim"],
            red_team_findings=[{
                "kind": "evidence_gap",
                "claim": "Search did not establish a buyer.",
            }],
        )

        assert risk == "Medium"
        assert context and "incomplete evidence" in context
        assert "Search did not establish" in context
        assert concern and "incomplete evidence" in concern

    def test_explicit_zero_affirmative_matrix_never_claims_verified_or_high(self):
        explicit_zero_affirmative = [
            [],
            [{"kind": "not_a_kind", "claim": "Unsupported raw row."}],
            [{"kind": "evidence_gap", "claim": "Search did not establish a buyer."}],
        ]
        for findings in explicit_zero_affirmative:
            _verdict, risk, concern, context = self._t().apply_red_team_downgrade(
                "Go",
                "Low",
                None,
                red_team_verdict="killed",
                red_team_caveats=["Legacy compatibility caveat."],
                red_team_findings=findings,
            )

            assert risk == "Medium", findings
            assert context and "incomplete evidence" in context, findings
            assert concern and "incomplete evidence" in concern, findings
            assert "verified" not in context.lower(), findings
            assert "objection" not in context.lower(), findings

    def test_legacy_null_and_mixed_affirmative_keep_distinct_floor_semantics(self):
        _verdict, legacy_risk, legacy_concern, legacy_context = (
            self._t().apply_red_team_downgrade(
                "Conditional",
                "Medium",
                None,
                red_team_verdict="killed",
                red_team_caveats=["Legacy prose-only caveat."],
                red_team_findings=None,
            )
        )
        assert legacy_risk == "High"
        assert legacy_context and "could not find evidence" in legacy_context
        assert legacy_concern and "refuted" in legacy_concern

        mixed = [
            {"kind": "evidence_gap", "claim": "Search coverage was incomplete."},
            {"kind": "verified_payer_mismatch", "claim": "The user cannot buy."},
        ]
        _verdict, mixed_risk, mixed_concern, mixed_context = (
            self._t().apply_red_team_downgrade(
                "Conditional",
                "Medium",
                None,
                red_team_verdict="killed",
                red_team_caveats=[],
                red_team_findings=mixed,
            )
        )
        assert mixed_risk == "High"
        assert mixed_context and "verified counterevidence" in mixed_context
        assert "The user cannot buy" in mixed_context
        assert mixed_concern and "verified counterevidence" in mixed_concern


class TestGeographicPrioritiesMayBeEmpty:
    """Most niches have no geographic signal, and forcing an entry guaranteed fabrication.

    The field was `min_length=1` with `Examples: ['Spain', 'Portugal', 'France']` in its
    description — mandatory, plus the only concrete strings in scope — so runs shipped a
    Spain-first go-to-market plan for US-only niches. Removing the example moved the model
    to an honest sentinel ("Not geographically differentiated..."), which then rendered AS a
    ranked market (live run 8f35ea6b). Empty is the correct answer; the frontend guards on
    `.length > 0` and omits the section.
    """

    def _payload(self, **over):
        base = {
            "geographic_priorities": [],
            "feature_priorities": [{
                "feature_name": "Lot intake check", "priority": 1,
                "keyword_support": 0.5, "rationale": "traced to validated keywords",
            }],
            "strategic_insights": ["insight one", "insight two", "insight three"],
        }
        base.update(over)
        return base

    def test_empty_list_is_accepted(self):
        from nicheiq.models.solution_refinement import SolutionRefinement
        r = SolutionRefinement.model_validate(self._payload())
        assert r.geographic_priorities == []

    def test_field_is_not_required(self):
        from nicheiq.models.solution_refinement import SolutionRefinement
        f = SolutionRefinement.model_fields["geographic_priorities"]
        assert not f.is_required()
        assert f.get_default(call_default_factory=True) == []

    def test_description_names_no_country(self):
        """A worked example here is a fabrication anchor — the model copies it verbatim."""
        from nicheiq.models.solution_refinement import SolutionRefinement
        desc = SolutionRefinement.model_fields["geographic_priorities"].description or ""
        for country in ("Spain", "Portugal", "France", "Germany", "United Kingdom"):
            assert country not in desc, f"{country!r} is an anchor the model will copy"

    def test_real_markets_still_accepted(self):
        from nicheiq.models.solution_refinement import SolutionRefinement
        r = SolutionRefinement.model_validate(
            self._payload(geographic_priorities=["United States", "Canada"]))
        assert r.geographic_priorities == ["United States", "Canada"]
