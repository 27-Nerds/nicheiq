"""Prose summary of a single competitive landscape.

Extracted from `flows/research_flow.py` so the report can build the summary for the
SELECTED solution. `CompetitiveAnalysisResult.strategic_recommendations` is one scalar
field that every landscape overwrites as Stage 5.5 walks the top-N, so whatever it holds
at report time describes the LAST idea analysed. In the 2026-08 8ef396eb report that made
the report say "Identified 7 competitors" (a runner-up's landscape) directly beside an
"Alternatives reviewed: 2" tile counting the selected idea's landscape — two numbers about
two different products, reading as a contradiction about one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..models.competitor import CompetitiveLandscape

__all__ = ["build_strategic_recommendations"]


def build_strategic_recommendations(landscape: "CompetitiveLandscape") -> str:
    """Strategic-recommendations text for one landscape (min 50 chars).

    The competitor count is stated as "for <solution>", never bare: it counts the
    competitors found for THAT idea, not the run's competitor universe.
    """
    parts = []
    parts.append(
        f"Competitive intensity for {landscape.solution_name}: "
        f"{landscape.competitive_intensity}."
    )

    comp_count = len(landscape.competitors) if landscape.competitors else 0
    parts.append(
        f"Identified {comp_count} direct competitor{'s' if comp_count != 1 else ''} "
        f"for {landscape.solution_name}."
    )

    if landscape.market_gaps:
        gaps_preview = ", ".join(landscape.market_gaps[:3])
        parts.append(f"Key market gaps: {gaps_preview}.")

    if landscape.differentiation_opportunities:
        opps_preview = ", ".join(landscape.differentiation_opportunities[:3])
        parts.append(f"Differentiation opportunities: {opps_preview}.")

    parts.append(f"Recommended positioning: {landscape.recommended_positioning}")

    text = " ".join(parts)
    # Ensure min_length=50 for CompetitiveAnalysisResult.strategic_recommendations
    if len(text) < 50:
        text += " Further analysis recommended for detailed competitive strategy."
    return text
