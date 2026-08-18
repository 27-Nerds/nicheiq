"""
Score validation utilities for go/no-go decisions and thresholds.

This module provides validators for solution scoring and verdict logic,
enabling testable, reusable validation separate from report generation.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from ..utils.content_security import prompt_field
from ..models.solution_idea import (
    effective_red_team_state,
    has_affirmative_red_team_findings,
)


class ConfidenceThresholds(BaseModel):
    """
    Thresholds for data-quality-based confidence score adjustments.

    Each multiplier is applied independently. Missing/unknown tiers
    default to 1.0 (no penalty). Final score is clamped to floor.
    """

    # Pain point quality tier multipliers (GOLD = 1.0 implicit)
    pain_point_silver: float = Field(
        default=0.95, ge=0.0, le=1.0,
        description="Multiplier for SILVER pain point quality tier",
    )
    pain_point_bronze: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="Multiplier for BRONZE pain point quality tier",
    )
    pain_point_insufficient: float = Field(
        default=0.70, ge=0.0, le=1.0,
        description="Multiplier for INSUFFICIENT pain point quality tier",
    )

    # Social content quality tier multipliers (EXCELLENT/GOOD = 1.0 implicit)
    social_minimal: float = Field(
        default=0.90, ge=0.0, le=1.0,
        description="Multiplier for MINIMAL social content quality tier",
    )
    social_insufficient: float = Field(
        default=0.75, ge=0.0, le=1.0,
        description="Multiplier for INSUFFICIENT social content quality tier",
    )

    # Pain point confidence score thresholds
    pp_confidence_low_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="PP confidence below this triggers low multiplier",
    )
    pp_confidence_low_multiplier: float = Field(
        default=0.90, ge=0.0, le=1.0,
        description="Multiplier when PP confidence is below low threshold",
    )
    pp_confidence_very_low_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="PP confidence below this triggers very low multiplier",
    )
    pp_confidence_very_low_multiplier: float = Field(
        default=0.80, ge=0.0, le=1.0,
        description="Multiplier when PP confidence is below very low threshold",
    )

    # Floor (minimum adjusted score)
    floor: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description="Minimum adjusted confidence score",
    )


class ConfidenceAdjustmentResult(BaseModel):
    """Result of a confidence score adjustment."""

    base_score: float = Field(description="Original base confidence score")
    adjusted_score: float = Field(description="Adjusted confidence score after quality penalties")
    quality_multiplier: float = Field(description="Combined quality multiplier applied")
    adjustment_notes: list[str] = Field(
        default_factory=list,
        description="Explanation of each adjustment applied",
    )


class ScoreThresholds(BaseModel):
    """
    Validation thresholds for scoring logic.

    Provides type-safe configuration for all score-based validations
    used in report generation. Defaults match production values.
    """

    # Market Validation Levels
    market_validation_strong_volume: int = Field(
        default=100_000,
        ge=0,
        description="Minimum search volume for STRONG market validation",
    )
    market_validation_strong_pain_points: int = Field(
        default=10,
        ge=0,
        description="Minimum pain point count for STRONG market validation",
    )
    market_validation_moderate_volume: int = Field(
        default=30_000,
        ge=0,
        description="Minimum search volume for MODERATE market validation",
    )
    market_validation_moderate_pain_points: int = Field(
        default=5,
        ge=0,
        description="Minimum pain point count for MODERATE market validation",
    )

    # Go/No-Go Verdict Thresholds
    verdict_go_avg_score: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        description="Minimum average score (all 4 dimensions) for Go verdict",
    )
    verdict_go_min_individual_score: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum individual score (market_fit, tech_feasibility) for Go verdict",
    )
    verdict_conditional_avg_score: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Minimum average score for Conditional verdict",
    )
    verdict_conditional_min_individual_score: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Minimum individual score for Conditional verdict",
    )

    # Pain Point & Competitive Thresholds
    pain_point_high_priority_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum severity score for high-priority pain point classification",
    )
    competitive_intensity_low_threshold: int = Field(
        default=3,
        ge=0,
        description="Maximum competitor count for 'Low' competitive intensity",
    )
    competitive_intensity_high_threshold: int = Field(
        default=8,
        ge=0,
        description="Minimum competitor count for 'High' competitive intensity",
    )

    # Confidence adjustment thresholds
    confidence: ConfidenceThresholds = Field(
        default_factory=ConfidenceThresholds,
        description="Thresholds for data-quality-based confidence adjustments",
    )

    # Score Defaults
    score_accessor_default_fallback: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default score when data is missing (ScoreAccessor fallback)",
    )

    # Trend-Based Verdict Downgrade Flags
    trend_missed_window_caps_conditional: bool = Field(
        default=True,
        description="Rule 1: Declining + Missed Window caps verdict at Conditional, risk at least Medium",
    )
    trend_fad_caps_conditional: bool = Field(
        default=True,
        description="Rule 2: Fad longevity caps verdict at Conditional, risk at least Medium",
    )
    trend_declining_downgrades_go: bool = Field(
        default=True,
        description="Rule 3: Declining trend downgrades Go to Conditional (not Conditional to No-Go)",
    )
    trend_risky_downgrades_go: bool = Field(
        default=True,
        description="Rule 4: Risky longevity downgrades Go to Conditional (not Conditional to No-Go)",
    )
    trend_monitor_wait_raises_risk: bool = Field(
        default=False,
        description="Rule 5 (additive): Monitor & Wait timing raises risk one level",
    )

    # Phase 3: Market Viability Downgrade Flag
    viability_weak_floors_risk_medium: bool = Field(
        default=True,
        description="Phase 3: Weak market viability sets risk floor at Medium",
    )

    # Phase 4: SEO kill-question floor tuning.
    # The floor keys on KD-coverage-robust signals: DataForSEO omits KD for many (often easy) long-tail
    # intents, so an absolute winnable-page count collapses to ~0 on niches that are actually winnable.
    # We therefore (a) gate on KD-coverage sufficiency and (b) judge winnability as a SHARE of KD'd intents.
    seo_kill_min_kd_sample: int = Field(
        default=30,
        description="Floor abstains unless this many page-universe intents carried a KD value (coverage denominator)",
    )
    seo_kill_min_kd_coverage: float = Field(
        default=0.5,
        description="Floor abstains unless KD covers >= this fraction of the page universe (else winnable/KD unreliable)",
    )
    seo_kill_min_winnable_share: float = Field(
        default=0.15,
        description="distribution_seo with winnable_pages/kd_sample_size < this = no real winnable universe (floor fires)",
    )
    seo_kill_high_kd: float = Field(
        default=60.0,
        description="Median keyword difficulty >= this = slow/unwinnable on a new domain (secondary floor signal)",
    )

    # Phase 5: payability floor (permanent since the 2026-07-06 calibration-gate pass)
    payability_low_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Segment payability below this counts as LOW (floor trigger)",
    )

    # Phase 6: stacked regulatory-risk downgrade (flagged experiment, default OFF)
    enable_regulatory_risk_downgrade: bool = Field(
        default=False,
        description="Phase 6: an idea carrying BOTH 'regulatory' and 'grey-market' risk flags caps "
                    "verdict at Conditional and floors risk at Medium (drop-only)",
    )

    @classmethod
    def from_settings(cls, app_settings) -> "ScoreThresholds":
        """Build thresholds from application settings (env-overridable).

        Maps every field that exists under the same name on the settings
        object; fields settings doesn't define keep their defaults here.
        Behavior-neutral with default env (settings defaults match these
        defaults) — it only makes deliberate env overrides effective, which
        no-arg ``ScoreThresholds()`` construction silently ignored.
        """
        values = {
            name: getattr(app_settings, name)
            for name in cls.model_fields
            if name != 'confidence' and hasattr(app_settings, name)
        }
        return cls(**values)


class VerdictValidator:
    """
    Validates go/no-go verdicts based on configurable score thresholds.

    Provides reusable, testable logic for verdict calculation separate
    from report generation. Supports custom thresholds for different
    market conditions or business requirements.
    """

    def __init__(self, thresholds: Optional[ScoreThresholds] = None):
        """
        Initialize verdict validator.

        Args:
            thresholds: Custom thresholds (defaults to production values)
        """
        self.thresholds = thresholds or ScoreThresholds()

    def validate_go_verdict(
        self,
        avg_score: float,
        market_fit: float,
        tech_feasibility: float,
    ) -> tuple[Literal["Go", "Conditional", "No-Go"], str]:
        """
        Validate if scores meet Go verdict criteria.

        Args:
            avg_score: Average of all 4 dimension scores (0.0-1.0)
            market_fit: Market fit score (0.0-1.0)
            tech_feasibility: Technical feasibility score (0.0-1.0)

        Returns:
            Tuple of (verdict, rationale):
            - "Go": All thresholds exceeded
            - "Conditional": Meets conditional thresholds but not Go
            - "No-Go": Below all thresholds
        """
        # Check Go verdict
        if (
            avg_score >= self.thresholds.verdict_go_avg_score
            and min(market_fit, tech_feasibility)
            >= self.thresholds.verdict_go_min_individual_score
        ):
            return (
                "Go",
                f"Strong opportunity: avg_score={avg_score:.2f}, "
                f"market_fit={market_fit:.2f}, tech_feasibility={tech_feasibility:.2f}",
            )

        # Check Conditional verdict
        if (
            avg_score >= self.thresholds.verdict_conditional_avg_score
            and min(market_fit, tech_feasibility)
            >= self.thresholds.verdict_conditional_min_individual_score
        ):
            return (
                "Conditional",
                f"Promising with risks: avg_score={avg_score:.2f}, "
                f"market_fit={market_fit:.2f}, tech_feasibility={tech_feasibility:.2f}",
            )

        # No-Go verdict
        return (
            "No-Go",
            f"Below thresholds: avg_score={avg_score:.2f}, "
            f"market_fit={market_fit:.2f}, tech_feasibility={tech_feasibility:.2f}",
        )

    def validate_market_validation_level(
        self,
        total_volume: int,
        pain_point_count: int,
    ) -> Literal["STRONG", "MODERATE", "WEAK"]:
        """
        Determine market validation level based on volume and pain points.

        Args:
            total_volume: Total search volume across validated keywords
            pain_point_count: Number of identified pain points

        Returns:
            Market validation level: "STRONG", "MODERATE", or "WEAK"
        """
        # Strong validation
        if (
            total_volume > self.thresholds.market_validation_strong_volume
            and pain_point_count >= self.thresholds.market_validation_strong_pain_points
        ):
            return "STRONG"

        # Moderate validation
        if (
            total_volume > self.thresholds.market_validation_moderate_volume
            and pain_point_count
            >= self.thresholds.market_validation_moderate_pain_points
        ):
            return "MODERATE"

        # Weak validation
        return "WEAK"

    def classify_competitive_intensity(
        self,
        competitor_count: int,
    ) -> Literal["Low", "Medium", "High"]:
        """
        Classify competitive intensity based on competitor count.

        Args:
            competitor_count: Number of identified competitors

        Returns:
            Competitive intensity: "Low", "Medium", or "High"
        """
        if competitor_count < self.thresholds.competitive_intensity_low_threshold:
            return "Low"
        elif competitor_count < self.thresholds.competitive_intensity_high_threshold:
            return "Medium"
        else:
            return "High"

    def apply_trend_downgrade(
        self,
        verdict: Literal["Go", "No-Go", "Conditional"],
        risk_level: Literal["Low", "Medium", "High"],
        primary_concern: Optional[str],
        trend_direction: str,
        momentum_score: float,
        timing_recommendation: str,
        longevity_verdict: str,
        market_maturity: str,
    ) -> tuple[
        Literal["Go", "No-Go", "Conditional"],
        Literal["Low", "Medium", "High"],
        Optional[str],
        Optional[str],
    ]:
        """
        Apply trend-based downgrades to an existing verdict.

        Downgrades only — never upgrades a verdict. Maximum downgrade is to
        Conditional (never forces No-Go from trend data alone). If no rule
        applies, returns inputs unchanged with trend_context=None.

        Rules (1-4 are mutually exclusive elif chain, 5 is additive):
            1. Declining + Missed Window → cap at Conditional, risk >= Medium
            2. Fad longevity → cap at Conditional, risk >= Medium
            3. Declining trend → Go→Conditional only
            4. Risky longevity → Go→Conditional only
            5. Monitor & Wait → raise risk one level (additive)

        Args:
            verdict: Current verdict from score-based logic
            risk_level: Current risk level
            primary_concern: Current primary concern (may be None)
            trend_direction: "Growing", "Stable", or "Declining"
            momentum_score: 0.0-1.0 momentum score
            timing_recommendation: "Enter Now", "Monitor & Wait", or "Missed Window"
            longevity_verdict: "Sustainable", "Risky", or "Fad"
            market_maturity: "Emerging", "Growth", or "Mature"

        Returns:
            Tuple of (verdict, risk_level, primary_concern, trend_context)
            where trend_context documents the adjustment or None if unchanged.
        """
        original_verdict = verdict
        original_risk = risk_level
        trend_context = None
        risk_raised = False
        from ..utils.score_helpers import score_band  # plain bands, never expose the decimal

        # Helper to raise risk one level
        def _raise_risk(current: str) -> str:
            if current == "Low":
                return "Medium"
            if current == "Medium":
                return "High"
            return "High"  # Already High

        # Rules 1-4: mutually exclusive (elif chain)
        is_declining = trend_direction == "Declining"
        is_missed_window = timing_recommendation == "Missed Window"
        is_fad = longevity_verdict == "Fad"
        is_risky = longevity_verdict == "Risky"

        # Rule 1: Declining + Missed Window → cap at Conditional, risk >= Medium
        if (
            self.thresholds.trend_missed_window_caps_conditional
            and is_declining
            and is_missed_window
        ):
            if verdict == "Go":
                verdict = "Conditional"
            if risk_level == "Low":
                risk_level = "Medium"
            # Three-branch prose (F-035): "Downgraded from Conditional/Medium to
            # Conditional/Medium" was a no-op presented as a downgrade.
            reason = "Declining trend + Missed Window timing"
            if verdict != original_verdict:
                trend_context = (
                    f"Downgraded from {original_verdict}/{original_risk} to {verdict}/{risk_level}: "
                    f"{reason}"
                )
            elif risk_level != original_risk:
                trend_context = f"Risk raised {original_risk}→{risk_level}: {reason}"
            else:
                trend_context = f"Trend risk noted (already at the Conditional/Medium cap): {reason}"

        # Rule 2: Fad longevity → cap at Conditional, risk >= Medium
        elif self.thresholds.trend_fad_caps_conditional and is_fad:
            if verdict == "Go":
                verdict = "Conditional"
            if risk_level == "Low":
                risk_level = "Medium"
            reason = "Fad longevity verdict"
            if verdict != original_verdict:
                trend_context = (
                    f"Downgraded from {original_verdict}/{original_risk} to {verdict}/{risk_level}: "
                    f"{reason}"
                )
            elif risk_level != original_risk:
                trend_context = f"Risk raised {original_risk}→{risk_level}: {reason}"
            else:
                trend_context = f"Trend risk noted (already at the Conditional/Medium cap): {reason}"

        # Rule 3: Declining trend → Go→Conditional only if momentum confirms weakness
        elif self.thresholds.trend_declining_downgrades_go and is_declining and momentum_score < 0.35:
            if verdict == "Go":
                verdict = "Conditional"
                trend_context = (
                    f"Downgraded from Go/{original_risk} to Conditional/{risk_level}: "
                    f"Declining market trend ({score_band(momentum_score)} momentum)"
                )
            else:
                trend_context = (
                    f"Note: Declining market trend ({score_band(momentum_score)} momentum) — "
                    f"verdict already {verdict}, no further downgrade"
                )

        # Rule 4: Risky longevity → Go→Conditional only if momentum confirms weakness
        # (must come before Rule 3b so Declining+Risky+borderline-momentum is caught)
        elif self.thresholds.trend_risky_downgrades_go and is_risky and momentum_score < 0.50:
            if verdict == "Go":
                verdict = "Conditional"
                trend_context = (
                    f"Downgraded from Go/{original_risk} to Conditional/{risk_level}: "
                    f"Risky longevity verdict ({market_maturity} market)"
                )
            else:
                trend_context = (
                    f"Note: Risky longevity verdict ({market_maturity} market) — "
                    f"verdict already {verdict}, no further downgrade"
                )

        # Rule 3b: Barely-Declining — informational only, no downgrade
        # (only reached if momentum >= 0.35 AND not Risky with momentum < 0.50)
        elif self.thresholds.trend_declining_downgrades_go and is_declining:
            trend_context = (
                f"Note: Declining direction but {score_band(momentum_score)} momentum "
                f"near the Stable boundary — no verdict downgrade"
            )

        # Rule 4b: Risky longevity but moderate+ momentum — informational only
        elif self.thresholds.trend_risky_downgrades_go and is_risky:
            trend_context = (
                f"Note: Risky longevity ({market_maturity} market) but {score_band(momentum_score)} "
                f"momentum above the downgrade threshold"
            )

        # Rule 5: Monitor & Wait → raise risk one level (additive, independent of 1-4)
        if (
            self.thresholds.trend_monitor_wait_raises_risk
            and timing_recommendation == "Monitor & Wait"
        ):
            prev_risk = risk_level  # capture BEFORE reassignment (latent "High→High" prose bug)
            new_risk = _raise_risk(risk_level)
            if new_risk != risk_level:
                risk_raised = True
                risk_level = new_risk
                rule5_msg = f"Risk raised {prev_risk}→{new_risk}: Monitor & Wait timing"
                if trend_context:
                    trend_context = f"{trend_context}; {rule5_msg}"
                else:
                    trend_context = rule5_msg

        # Only set primary_concern from trend if none exists from score logic
        if trend_context and primary_concern is None:
            primary_concern = f"Trend concern: {trend_direction} market, {longevity_verdict} longevity, timing={timing_recommendation}"

        return verdict, risk_level, primary_concern, trend_context

    def apply_market_viability_downgrade(
        self,
        verdict: Literal["Go", "No-Go", "Conditional"],
        risk_level: Literal["Low", "Medium", "High"],
        primary_concern: Optional[str],
        market_viability_verdict: str,
        recommended_entry_strategy: str,
    ) -> tuple[
        Literal["Go", "No-Go", "Conditional"],
        Literal["Low", "Medium", "High"],
        Optional[str],
        Optional[str],
    ]:
        """
        Apply market viability risk floor (Phase 3).

        When market_viability_verdict is "Weak", sets a risk floor at Medium
        (Low→Medium, else no-op). Never changes the verdict itself.

        Args:
            verdict: Current verdict (after Phase 1+2)
            risk_level: Current risk level (after Phase 1+2)
            primary_concern: Current primary concern (may be None)
            market_viability_verdict: "Strong", "Moderate", or "Weak" from Stage 9
            recommended_entry_strategy: Entry strategy from Stage 9 (e.g. "Reconsider")

        Returns:
            Tuple of (verdict, risk_level, primary_concern, market_viability_context)
            where market_viability_context documents the adjustment or None if unchanged.
        """
        market_viability_context = None

        # Normalize inputs for case-insensitive matching
        viability = (market_viability_verdict or "").strip().title()
        entry_strategy = (recommended_entry_strategy or "").strip()

        if not viability:
            return verdict, risk_level, primary_concern, market_viability_context

        if self.thresholds.viability_weak_floors_risk_medium and viability == "Weak":
            original_risk = risk_level
            if risk_level == "Low":
                risk_level = "Medium"

            # Build context message
            context_parts = [
                f"Risk floor applied Low\u2192Medium" if original_risk == "Low"
                else f"Risk floor no-op (already {original_risk})"
            ]
            context_parts.append(f"Weak market viability")
            if entry_strategy:
                context_parts.append(f"entry strategy: {entry_strategy}")
            market_viability_context = ": ".join(context_parts[:2])
            if entry_strategy:
                market_viability_context += f" (entry strategy: {entry_strategy})"

            # Set primary_concern from viability if currently None
            if primary_concern is None:
                primary_concern = f"Weak market viability (entry strategy: {entry_strategy})" if entry_strategy else "Weak market viability"

        elif viability == "Moderate" and verdict == "Go":
            # Informational context only — no risk change
            market_viability_context = f"Moderate market viability noted (verdict: {verdict}, entry strategy: {entry_strategy or 'N/A'})"

        return verdict, risk_level, primary_concern, market_viability_context

    def apply_seo_kill_downgrade(
        self,
        verdict: Literal["Go", "No-Go", "Conditional"],
        risk_level: Literal["Low", "Medium", "High"],
        primary_concern: Optional[str],
        winnable_pages: int,
        median_keyword_difficulty: Optional[float],
        penalty_risk_flag: bool,
        kd_sample_size: int,
        page_ceiling: int,
    ) -> tuple[
        Literal["Go", "No-Go", "Conditional"],
        Literal["Low", "Medium", "High"],
        Optional[str],
        Optional[str],
    ]:
        """SEO kill-question floor (Phase 4) — caller gates this to distribution_seo ideas only.

        Grounds an over-OPTIMISTIC distribution_seo verdict in SEO REALITY: a great keyword score is a
        mirage if there's no winnable page universe. Keyed on the KD/winnability axis, which the SEO
        composite excludes by design (seo_helpers.py) — so this is NEW info, not a double-count.
        Downgrade-only: caps Go->Conditional + floors risk at Medium; never forces No-Go. penalty_risk
        is SECONDARY (it overlaps the existing Rule-B thin-page cap, so it never fires the floor alone).

        KD-COVERAGE GATE (A/B-driven, 2026-06-30): DataForSEO omits keyword_difficulty for many (often
        easy) long-tail intents, so an absolute winnable-page count collapses to ~0 on niches that are
        actually winnable. The floor therefore ABSTAINS (fail-soft, returns no-context) unless KD covers
        enough of the page universe, and judges winnability as a SHARE of KD'd intents, not an absolute
        count. Recompute A/B over cached checkpoints showed the old absolute test false-fired on 14/14
        sparse-KD checkpoints while every dense one (winnable share 0.75-0.93) was correctly silent.
        """
        seo_kill_context = None

        # Coverage gate — below this the winnable/median-KD signals are an artifact of missing data, not
        # real difficulty. Abstain (the safe direction: never downgrade a deserving idea on thin data).
        coverage = (kd_sample_size / page_ceiling) if page_ceiling else 0.0
        if (kd_sample_size < self.thresholds.seo_kill_min_kd_sample
                or coverage < self.thresholds.seo_kill_min_kd_coverage):
            return verdict, risk_level, primary_concern, None

        winnable_share = (winnable_pages / kd_sample_size) if kd_sample_size else 0.0
        no_universe = winnable_share < self.thresholds.seo_kill_min_winnable_share
        high_kd = median_keyword_difficulty is not None and median_keyword_difficulty >= self.thresholds.seo_kill_high_kd

        if no_universe or high_kd:
            if verdict == "Go":
                verdict = "Conditional"
            if risk_level == "Low":
                risk_level = "Medium"
            reason = ("almost no winnable page universe" if no_universe
                      else "high keyword difficulty (slow to rank on a new domain)")
            extra = " (thin-content penalty risk)" if penalty_risk_flag else ""
            seo_kill_context = (
                f"SEO kill-question: {reason}{extra} for a distribution play — held to Conditional, "
                f"risk floored at Medium."
            )
            if primary_concern is None:
                primary_concern = "Distribution play lacks a winnable SEO page universe"

        return verdict, risk_level, primary_concern, seo_kill_context

    def apply_payability_downgrade(
        self,
        verdict: Literal["Go", "No-Go", "Conditional"],
        risk_level: Literal["Low", "Medium", "High"],
        primary_concern: Optional[str],
        payability: Optional[float],
        payability_class: Optional[str],
        monetization: Optional[str],
    ) -> tuple[
        Literal["Go", "No-Go", "Conditional"],
        Literal["Low", "Medium", "High"],
        Optional[str],
        Optional[str],
    ]:
        """Payability floor (Phase 5, permanent since the 2026-07-06 gate pass): a Go verdict for an idea sold
        DIRECTLY (subscription/one-time/usage-based) to a low-payability segment overstates the
        business — the pain may be real, but the wallet isn't. Downgrade-only: caps Go->Conditional
        and floors risk at Medium; never forces No-Go; abstains (no context) when payability is
        unscored, above the low threshold, or the idea doesn't monetize by direct payment
        (ads/affiliate/commission plays don't need the buyer's wallet)."""
        direct_paid = (monetization or "").strip().lower() in (
            "subscription", "one-time", "usage-based")
        low = (isinstance(payability, (int, float))
               and payability < self.thresholds.payability_low_threshold)
        if not (low and direct_paid):
            return verdict, risk_level, primary_concern, None

        if verdict == "Go":
            verdict = "Conditional"
        if risk_level == "Low":
            risk_level = "Medium"
        # User-facing (feeds the verdict rationale's downgrade note): qualitative phrase only —
        # never the raw class token or the 0-1 decimal (band-words convention).
        from ..utils.segment_payability import payability_phrase
        payability_context = (
            f"Buyer payability: the target segment is {payability_phrase(payability_class)} "
            f"with weak willingness-to-pay for {monetization} pricing — held to Conditional, "
            "risk floored at Medium; validate real payment intent (pre-sales, paid pilots) "
            "before committing."
        )
        if primary_concern is None:
            primary_concern = "Target segment has weak willingness-to-pay for direct-paid pricing"
        return verdict, risk_level, primary_concern, payability_context

    def apply_red_team_downgrade(
        self,
        verdict: Literal["Go", "No-Go", "Conditional"],
        risk_level: Literal["Low", "Medium", "High"],
        primary_concern: Optional[str],
        red_team_verdict: Optional[str],
        red_team_caveats: Optional[list],
        red_team_findings: Optional[list] = None,
    ) -> tuple[
        Literal["Go", "No-Go", "Conditional"],
        Literal["Low", "Medium", "High"],
        Optional[str],
        Optional[str],
    ]:
        """Red-team floor (Phase 5.5, run-quality fixes §1 2026-07-30): the adversarial
        red-team pass produces evidence-cited 'weakened'/'killed' findings on the selected
        idea, but until this floor they never reached the verdict — a weakened selection
        presented exactly like an unexamined one. Downgrade-only, permanent (mirrors the
        payability floor, not the flagged Phase-6 experiment): caps Go->Conditional;
        'weakened' floors risk Low->Medium; 'killed' floors Medium->High — a killed idea
        can still BE the selection (the sweep demotions run before the red team, and the
        kill path only caps scores); never forces No-Go. primary_concern is set only when
        currently None (standard floor contract) — the caller nulls the GENERIC base
        concern for a killed verdict so this one can land. Abstains (no context) for
        survives/None; a vocabulary-mismatch abstain (red_team_vocab_mismatch) is NOT a
        verdict and never triggers this."""
        rt, typed_findings = effective_red_team_state({
            "red_team_verdict": red_team_verdict,
            "red_team_findings": red_team_findings,
        })
        rt = rt or ""
        if rt not in ("weakened", "killed"):
            return verdict, risk_level, primary_concern, None

        if verdict == "Go":
            verdict = "Conditional"
        if risk_level == "Low":
            risk_level = "Medium"
        if rt == "killed" and risk_level == "Medium":
            risk_level = "High"

        caveats = [c for c in (red_team_caveats or []) if isinstance(c, str) and c.strip()]
        affirmative = [
            finding for finding in (typed_findings or [])
            if has_affirmative_red_team_findings([finding])
        ]
        explicit_incomplete = (
            typed_findings is not None
            and not has_affirmative_red_team_findings(typed_findings)
        )
        # `first` is DISPLAY ONLY: it is interpolated into `red_team_context`, which the
        # report generator appends verbatim to the go/no-go rationale. It is never a match
        # or dedupe key -- the one comparison downstream (`red_team_context != downgrade_note`)
        # tests identity against a value assigned FROM this same string, so its length cannot
        # change which branch fires. A 200-char slice therefore only cut the finding mid-word
        # in the report's most prominent prose. Runaway backstop only.
        if typed_findings is None:
            first = prompt_field(caveats[0].strip()) if caveats else ""
        elif rt == "killed" and affirmative:
            first = prompt_field(affirmative[0].claim)
        else:
            first = prompt_field(typed_findings[0].claim) if typed_findings else ""
        cited = f" — {first}" if first else ""
        # The verdict enum must NOT be interpolated into the sentence. This read
        # "an adversarial evidence probe killed this idea" in the go/no-go block — the most
        # prominent prose in the report, and the one word the product deliberately does not
        # use (the UI says "Premise unproven"). It went unnoticed through a seven-surface
        # vocabulary sweep because the only artifact to check had `executive_dashboard: null`
        # from the project_type defect, so this string was computed and discarded. Fixing
        # that bug put this one on screen (live run 8f35ea6b, 2026-08-03).
        if typed_findings is None:
            # Exact legacy fallback for prose-only checkpoints.
            finding = (
                "could not find evidence for this idea's premise"
                if rt == "killed"
                else "raised a decision-critical objection to this idea"
            )
        elif rt == "killed":
            finding = "found verified counterevidence against this idea's premise"
        elif explicit_incomplete:
            finding = "returned incomplete evidence for this idea's premise"
        else:
            finding = "raised a verified decision-critical objection to this idea"
        red_team_context = (
            f"Red-team review: an adversarial evidence probe {finding}{cited}. "
            "Treat the caveat as a validation task, not a footnote."
        )
        if primary_concern is None:
            if typed_findings is None:
                primary_concern = (
                    "Adversarial red-team review found this idea's core premise refuted by evidence"
                    if rt == "killed"
                    else "Adversarial red-team review raised a decision-critical objection to the "
                         "selected idea"
                )
            elif rt == "killed":
                primary_concern = (
                    "Adversarial red-team review found verified counterevidence against the "
                    "selected idea"
                )
            elif explicit_incomplete:
                primary_concern = (
                    "Adversarial red-team review returned incomplete evidence for the "
                    "selected idea"
                )
            else:
                primary_concern = (
                    "Adversarial red-team review raised a verified decision-critical objection "
                    "to the selected idea"
                )
        return verdict, risk_level, primary_concern, red_team_context

    def apply_regulatory_risk_downgrade(
        self,
        verdict: Literal["Go", "No-Go", "Conditional"],
        risk_level: Literal["Low", "Medium", "High"],
        primary_concern: Optional[str],
        risk_flags: Optional[list],
    ) -> tuple[
        Literal["Go", "No-Go", "Conditional"],
        Literal["Low", "Medium", "High"],
        Optional[str],
        Optional[str],
    ]:
        """Phase 6 (flagged, default OFF): an idea carrying BOTH 'regulatory' AND 'grey-market' risk
        flags stacks a structural compliance blocker on top of a legally gray supply chain — a Go
        here overstates the business. Downgrade-only: caps Go->Conditional and floors risk at Medium
        (Medium->High); never forces No-Go; abstains (no context) when the flag is off or the stacked
        pair isn't present. Gated on the pair — a single 'regulatory' flag is common and not, on its
        own, a downgrade trigger."""
        if not self.thresholds.enable_regulatory_risk_downgrade:
            return verdict, risk_level, primary_concern, None
        flags = {str(f).strip().lower() for f in (risk_flags or [])}
        if not ({"regulatory", "grey-market"} <= flags):
            return verdict, risk_level, primary_concern, None

        if verdict == "Go":
            verdict = "Conditional"
        if risk_level == "Low":
            risk_level = "Medium"
        elif risk_level == "Medium":
            risk_level = "High"
        regulatory_context = (
            "Stacked regulatory exposure: this idea combines a compliance-regulated domain with a "
            "legally gray (grey-market) supply chain — held to Conditional, risk floored; confirm "
            "legal viability and regulatory standing before committing."
        )
        if primary_concern is None:
            primary_concern = "Stacked regulatory + grey-market exposure needs legal validation"
        return verdict, risk_level, primary_concern, regulatory_context

    def is_high_priority_pain_point(self, severity_score: float) -> bool:
        """
        Check if pain point qualifies as high priority (severity-only criterion).

        Note: This single-criterion check feeds the ``high_severity_count`` /
        ``high_severity_pain_points`` report fields.  It is distinct from
        ``opportunity_level == "high"`` which requires *both* severity >= 0.6
        and WTP >= 0.6 (dual criteria).

        Args:
            severity_score: Pain point severity score (0.0-1.0)

        Returns:
            True if severity exceeds high priority threshold
        """
        return severity_score >= self.thresholds.pain_point_high_priority_threshold


class ConfidenceAdjuster:
    """
    Applies data-quality-based penalties to a base confidence score.

    Follows the VerdictValidator pattern: downgrade-only, multiplicative
    penalties. Missing data = multiplier 1.0 (no change). Floor at
    configurable minimum.
    """

    # Tier → multiplier mappings (tiers not listed here get 1.0)
    _PAIN_POINT_TIER_MAP: dict[str, str] = {
        "SILVER": "pain_point_silver",
        "BRONZE": "pain_point_bronze",
        "INSUFFICIENT": "pain_point_insufficient",
    }
    _SOCIAL_TIER_MAP: dict[str, str] = {
        "MINIMAL": "social_minimal",
        "INSUFFICIENT": "social_insufficient",
    }

    def __init__(self, thresholds: Optional[ConfidenceThresholds] = None):
        self.thresholds = thresholds or ConfidenceThresholds()

    def adjust_confidence(
        self,
        base_score: float,
        pain_point_quality_tier: Optional[str] = None,
        social_content_quality_tier: Optional[str] = None,
        pain_point_confidence_score: Optional[float] = None,
    ) -> ConfidenceAdjustmentResult:
        """
        Adjust base confidence score using data quality signals.

        Args:
            base_score: Raw confidence score (0.0-1.0)
            pain_point_quality_tier: GOLD, SILVER, BRONZE, or INSUFFICIENT
            social_content_quality_tier: EXCELLENT, GOOD, MINIMAL, or INSUFFICIENT
            pain_point_confidence_score: Pipeline's PP confidence (0.0-1.0)

        Returns:
            ConfidenceAdjustmentResult with adjusted score and notes.
        """
        notes: list[str] = []
        multiplier = 1.0

        # Short-circuit: zero base score can't be improved
        if base_score == 0.0:
            notes.append("Base score is 0.0; no adjustment possible")
            return ConfidenceAdjustmentResult(
                base_score=base_score,
                adjusted_score=0.0,
                quality_multiplier=1.0,
                adjustment_notes=notes,
            )

        # Pain point quality tier penalty
        if pain_point_quality_tier is not None:
            attr = self._PAIN_POINT_TIER_MAP.get(pain_point_quality_tier)
            if attr is not None:
                tier_mult = getattr(self.thresholds, attr)
                multiplier *= tier_mult
                notes.append(
                    f"Pain point tier {pain_point_quality_tier}: {tier_mult:.2f}x"
                )

        # Social content quality tier penalty
        if social_content_quality_tier is not None:
            attr = self._SOCIAL_TIER_MAP.get(social_content_quality_tier)
            if attr is not None:
                tier_mult = getattr(self.thresholds, attr)
                multiplier *= tier_mult
                notes.append(
                    f"Social tier {social_content_quality_tier}: {tier_mult:.2f}x"
                )

        # Pain point confidence score penalty
        if pain_point_confidence_score is not None:
            if pain_point_confidence_score < self.thresholds.pp_confidence_very_low_threshold:
                pp_mult = self.thresholds.pp_confidence_very_low_multiplier
                multiplier *= pp_mult
                notes.append(
                    f"PP confidence {pain_point_confidence_score:.2f} < "
                    f"{self.thresholds.pp_confidence_very_low_threshold}: {pp_mult:.2f}x"
                )
            elif pain_point_confidence_score < self.thresholds.pp_confidence_low_threshold:
                pp_mult = self.thresholds.pp_confidence_low_multiplier
                multiplier *= pp_mult
                notes.append(
                    f"PP confidence {pain_point_confidence_score:.2f} < "
                    f"{self.thresholds.pp_confidence_low_threshold}: {pp_mult:.2f}x"
                )

        # Apply multiplier and clamp to floor
        adjusted = base_score * multiplier
        adjusted = max(adjusted, self.thresholds.floor)

        return ConfidenceAdjustmentResult(
            base_score=base_score,
            adjusted_score=adjusted,
            quality_multiplier=multiplier,
            adjustment_notes=notes,
        )
