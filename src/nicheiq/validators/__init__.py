"""
Validation utilities for report generation.

This package provides reusable validation logic for scores, text, and fields
used throughout the report generation process. Validators are designed to be
testable in isolation and configurable via Settings.
"""

from .field_validators import (
    validate_non_empty_string,
    validate_non_negative_int,
    validate_optional_non_empty_string,
    validate_optional_score_range,
    validate_optional_url,
    validate_percentage,
    validate_score_range,
    validate_url,
)
from .score_validators import ScoreThresholds, VerdictValidator
from .text_validators import TextValidator

__all__ = [
    # Score validators
    "ScoreThresholds",
    "VerdictValidator",
    # Text validators
    "TextValidator",
    # Field validators (Pydantic)
    "validate_score_range",
    "validate_optional_score_range",
    "validate_non_negative_int",
    "validate_non_empty_string",
    "validate_optional_non_empty_string",
    "validate_percentage",
    "validate_url",
    "validate_optional_url",
]
