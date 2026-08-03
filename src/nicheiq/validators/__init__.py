"""
Validation utilities for report generation.

This package provides reusable validation logic for scores and report
consistency used throughout the report generation process. Validators are
designed to be testable in isolation and configurable via Settings.
"""

from .report_consistency import ConsistencyWarning, ReportConsistencyValidator
from .score_validators import (
    ConfidenceAdjuster,
    ConfidenceAdjustmentResult,
    ConfidenceThresholds,
    ScoreThresholds,
    VerdictValidator,
)
from .unit_economics import (
    NOT_COMPUTABLE,
    LtvCacGroundingResult,
    validate_ltv_cac_grounding,
)

__all__ = [
    # Report consistency
    "ConsistencyWarning",
    "ReportConsistencyValidator",
    # Score validators
    "ConfidenceAdjuster",
    "ConfidenceAdjustmentResult",
    "ConfidenceThresholds",
    "ScoreThresholds",
    "VerdictValidator",
    # Unit economics
    "NOT_COMPUTABLE",
    "LtvCacGroundingResult",
    "validate_ltv_cac_grounding",
]
