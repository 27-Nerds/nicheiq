"""
Score validation utilities for go/no-go decisions and thresholds.

This module provides validators for solution scoring and verdict logic,
enabling testable, reusable validation separate from report generation.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


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
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum average score (all 4 dimensions) for Go verdict",
    )
    verdict_go_min_individual_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum individual score (market_fit, tech_feasibility) for Go verdict",
    )
    verdict_conditional_avg_score: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum average score for Conditional verdict",
    )
    verdict_conditional_min_individual_score: float = Field(
        default=0.55,
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
        default=True,
        description="Rule 5 (additive): Monitor & Wait timing raises risk one level",
    )

    # Phase 3: Market Viability Downgrade Flag
    viability_weak_floors_risk_medium: bool = Field(
        default=True,
        description="Phase 3: Weak market viability sets risk floor at Medium",
    )


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
            trend_context = (
                f"Downgraded from {original_verdict}/{original_risk} to {verdict}/{risk_level}: "
                f"Declining trend + Missed Window timing"
            )

        # Rule 2: Fad longevity → cap at Conditional, risk >= Medium
        elif self.thresholds.trend_fad_caps_conditional and is_fad:
            if verdict == "Go":
                verdict = "Conditional"
            if risk_level == "Low":
                risk_level = "Medium"
            trend_context = (
                f"Downgraded from {original_verdict}/{original_risk} to {verdict}/{risk_level}: "
                f"Fad longevity verdict"
            )

        # Rule 3: Declining trend → Go→Conditional only
        elif self.thresholds.trend_declining_downgrades_go and is_declining:
            if verdict == "Go":
                verdict = "Conditional"
                trend_context = (
                    f"Downgraded from Go/{original_risk} to Conditional/{risk_level}: "
                    f"Declining market trend (momentum={momentum_score:.2f})"
                )

        # Rule 4: Risky longevity → Go→Conditional only
        elif self.thresholds.trend_risky_downgrades_go and is_risky:
            if verdict == "Go":
                verdict = "Conditional"
                trend_context = (
                    f"Downgraded from Go/{original_risk} to Conditional/{risk_level}: "
                    f"Risky longevity verdict ({market_maturity} market)"
                )

        # Rule 5: Monitor & Wait → raise risk one level (additive, independent of 1-4)
        if (
            self.thresholds.trend_monitor_wait_raises_risk
            and timing_recommendation == "Monitor & Wait"
        ):
            new_risk = _raise_risk(risk_level)
            if new_risk != risk_level:
                risk_raised = True
                risk_level = new_risk
                rule5_msg = f"Risk raised {original_risk if not trend_context else risk_level}→{risk_level}: Monitor & Wait timing"
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
            market_viability_verdict: "Strong", "Moderate", or "Weak" from Stage 8.6
            recommended_entry_strategy: Entry strategy from Stage 8.6 (e.g. "Reconsider")

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
