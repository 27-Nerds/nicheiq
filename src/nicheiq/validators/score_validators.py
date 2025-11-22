"""
Score validation utilities for go/no-go decisions and thresholds.

This module provides validators for solution scoring and verdict logic,
enabling testable, reusable validation separate from report generation.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


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

    # Score Defaults
    score_accessor_default_fallback: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default score when data is missing (ScoreAccessor fallback)",
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

    def is_high_priority_pain_point(self, severity_score: float) -> bool:
        """
        Check if pain point qualifies as high priority.

        Args:
            severity_score: Pain point severity score (0.0-1.0)

        Returns:
            True if severity exceeds high priority threshold
        """
        return severity_score >= self.thresholds.pain_point_high_priority_threshold
