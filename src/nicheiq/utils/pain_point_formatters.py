"""
Pain point formatting utilities for consistent data passing across crews.

Provides unified formatting helpers to eliminate duplication between
UnifiedSolutionCrew and SEOStrategyCrew.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.pain_point import PainPoint, PainPointAnalysisResult

def format_pain_points_for_agents(
    pain_points: list,
    format_type: str = "detailed",
    priority_filter: str | None = None,
    sort_by: str = "severity",
    limit: int = 10,
    include_quotes: bool = False
) -> str:
    """
    Unified pain point formatting helper for consistent data passing across crews.

    Eliminates duplication between UnifiedSolutionCrew and SEOStrategyCrew while
    ensuring all required fields are consistently included.

    Args:
        pain_points: List of PainPoint objects
        format_type: Output format (str). Valid values:
            - "detailed": Full context with description, metrics, quotes (UnifiedSolutionCrew)
              Example: "**1. Title**\\n- Problem: desc\\n- Severity: 8.5 | WTP: 7.2\\n- Mentions: 42"
            - "compact": Inline metrics only (SEOStrategyCrew, medium priority)
              Example: "**Title** (Severity: 8.5, WTP: 7.2)"
            - "metrics_only": Title + metrics in standardized format
              Example: "- Title (Severity: 8.5/10, WTP: 7.2/10, Mentions: 42)"
        priority_filter: Filter by opportunity_level (str or None). Valid values:
            - "high": Only high-opportunity pain points
            - "medium": Only medium-opportunity pain points
            - "low": Only low-opportunity pain points
            - None: All pain points (default if not specified)
        sort_by: Sort order (str). Valid values:
            - "severity": Sort by severity_score descending (highest first)
            - "wtp": Sort by willingness_to_pay descending
            - "mentions": Sort by mention_count descending
            - "title": Sort alphabetically by title ascending
        limit: Maximum number of pain points to include (int, default: 10)
        include_quotes: Include representative quote (bool). Only applies to "detailed" format.
            If True and format_type="detailed", adds quote line to output.

    Returns:
        Formatted string ready for crew kickoff inputs

    Example Usage:
        # UnifiedSolutionCrew - high priority with quotes
        high_priority_list = format_pain_points_for_agents(
            pain_points=pain_point_analysis.pain_points,
            format_type="detailed",
            priority_filter="high",
            sort_by="severity",
            limit=10,
            include_quotes=True
        )

        # SEOStrategyCrew - top 10 by severity
        top_pain_points = format_pain_points_for_agents(
            pain_points=pain_point_analysis.pain_points,
            format_type="metrics_only",
            sort_by="severity",
            limit=10
        )
    """
    # Validate inputs
    if not pain_points:
        return ""

    # Validate priority_filter
    if priority_filter and priority_filter not in ["high", "medium", "low"]:
        raise ValueError(
            f"Invalid priority_filter: '{priority_filter}'. "
            f"Must be one of: 'high', 'medium', 'low', or None"
        )

    # Validate sort_by
    valid_sort_options = ["severity", "wtp", "mentions", "title"]
    if sort_by not in valid_sort_options:
        raise ValueError(
            f"Invalid sort_by: '{sort_by}'. "
            f"Must be one of: {valid_sort_options}"
        )

    # Filter by priority if specified
    if priority_filter:
        filtered = [pp for pp in pain_points if pp.opportunity_level.value == priority_filter]
    else:
        filtered = pain_points

    # Sort
    if sort_by == "severity":
        filtered = sorted(filtered, key=lambda p: p.severity_score, reverse=True)
    elif sort_by == "wtp":
        filtered = sorted(filtered, key=lambda p: p.willingness_to_pay, reverse=True)
    elif sort_by == "mentions":
        filtered = sorted(filtered, key=lambda p: p.mention_count, reverse=True)
    elif sort_by == "title":
        filtered = sorted(filtered, key=lambda p: p.title)

    # Limit
    filtered = filtered[:limit]

    # Format based on type
    if format_type == "detailed":
        # UnifiedSolutionCrew format: Full context with description and metrics
        lines = []
        for i, pp in enumerate(filtered):
            parts = [
                f"**{i+1}. {pp.title}**",
                f"- Problem: {pp.description}",
                f"- Severity: {pp.severity_score * 10:.1f}/10 | WTP: {pp.willingness_to_pay * 10:.1f}/10",
                f"- Mentions: {pp.mention_count}"
            ]
            if include_quotes and pp.representative_quotes:
                # Select 2 diverse quotes: pick longest, then longest non-overlapping
                quotes = pp.representative_quotes
                sorted_by_len = sorted(quotes, key=len, reverse=True)
                selected = [sorted_by_len[0]]
                if len(sorted_by_len) > 1:
                    # Pick second quote with least word overlap
                    first_words = set(sorted_by_len[0].lower().split())
                    best_idx, best_overlap = 1, 1.0
                    for i, q in enumerate(sorted_by_len[1:], 1):
                        q_words = set(q.lower().split())
                        overlap = len(first_words & q_words) / max(len(q_words), 1)
                        if overlap < best_overlap:
                            best_overlap = overlap
                            best_idx = i
                    selected.append(sorted_by_len[best_idx])
                for q in selected:
                    parts.append(f"  - \"{q}\"")
            lines.append("\n".join(parts))
        return "\n\n".join(lines) if lines else ""

    elif format_type == "compact":
        # Medium priority format: Inline metrics
        lines = [
            f"**{pp.title}** (Severity: {pp.severity_score * 10:.1f}/10, WTP: {pp.willingness_to_pay * 10:.1f}/10)"
            for pp in filtered
        ]
        return "\n".join(lines) if lines else ""

    elif format_type == "metrics_only":
        # SEOStrategyCrew format: Standardized metrics with /10 scale
        lines = [
            f"- {pp.title} (Severity: {pp.severity_score * 10:.1f}/10, WTP: {pp.willingness_to_pay * 10:.1f}/10, Mentions: {pp.mention_count})"
            for pp in filtered
        ]
        return "\n".join(lines) if lines else ""

    else:
        raise ValueError(f"Unknown format_type: {format_type}. Must be 'detailed', 'compact', or 'metrics_only'")

def extract_pain_points_by_priority(
    pain_point_analysis: 'PainPointAnalysisResult'
) -> tuple[list['PainPoint'], list['PainPoint'], list['PainPoint']]:
    """
    Extract pain points grouped by opportunity level.

    Helper for crews that need separate high/medium/low priority lists.

    Args:
        pain_point_analysis: PainPointAnalysisResult from Stage 6

    Returns:
        Tuple of (high_priority, medium_priority, low_priority) lists

    Example Usage:
        high_priority, medium_priority, low_priority = extract_pain_points_by_priority(
            self.pain_point_analysis
        )
    """
    high_priority = [
        pp for pp in pain_point_analysis.pain_points
        if pp.opportunity_level.value == "high"
    ]
    medium_priority = [
        pp for pp in pain_point_analysis.pain_points
        if pp.opportunity_level.value == "medium"
    ]
    low_priority = [
        pp for pp in pain_point_analysis.pain_points
        if pp.opportunity_level.value == "low"
    ]

    return high_priority, medium_priority, low_priority
