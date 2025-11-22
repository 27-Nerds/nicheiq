"""
Report generation utilities.

This package contains utility functions for report generation including:
- model_helpers: Dict/model compatibility helpers for checkpoint handling
- state_accessors: Defensive state access layer with null checking
- score_accessor: Score extraction utilities with fallback logic
"""

from .model_helpers import safe_get_attr
from .score_accessor import ScoreAccessor
from .state_accessors import StateAccessor

__all__ = ["safe_get_attr", "StateAccessor", "ScoreAccessor"]
