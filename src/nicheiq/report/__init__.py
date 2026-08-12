"""
Report Generation Module

This module handles Stage 14 of the research pipeline - Final Report Generation.
Uses a hybrid approach: Python data assembly (80%) + optional LLM synthesis (20%).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .report_generator import ReportGenerator

__all__ = ["ReportGenerator"]


def __getattr__(name: str) -> Any:
    """Keep the public ReportGenerator import without loading it for submodules."""
    if name != "ReportGenerator":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from .report_generator import ReportGenerator

    globals()[name] = ReportGenerator
    return ReportGenerator
