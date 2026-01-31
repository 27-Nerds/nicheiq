"""
Report generation utilities.

This package contains utility functions for report generation including:
- model_helpers: Dict/model compatibility helpers for checkpoint handling
- state_accessors: Defensive state access layer with null checking
- score_accessor: Score extraction utilities with fallback logic
- prompt_formatters: Prompt formatting utilities for LLM inputs
"""

from .model_helpers import safe_get_attr
from .prompt_formatters import (
    format_channels_for_prompt,
    format_icp_for_prompt,
    format_pain_points_for_prompt,
)
from .report_pre_compute import (
    compute_budget_range,
    compute_metric_calibration,
    format_pain_point_with_scores,
)
from .score_accessor import ScoreAccessor
from .state_accessors import StateAccessor

__all__ = [
    "safe_get_attr",
    "StateAccessor",
    "ScoreAccessor",
    "format_pain_points_for_prompt",
    "format_channels_for_prompt",
    "format_icp_for_prompt",
    "compute_budget_range",
    "compute_metric_calibration",
    "format_pain_point_with_scores",
]
