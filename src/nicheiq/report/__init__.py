"""
Report Generation Module

This module handles Stage 10 of the research pipeline - Final Report Generation.
Uses a hybrid approach: Python data assembly (80%) + optional LLM synthesis (20%).
"""

from .report_generator import ReportGenerator

__all__ = ["ReportGenerator"]
