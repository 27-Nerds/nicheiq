"""
Final Report Generator - Transform FinalReport Pydantic model into comprehensive markdown.

Generates a professional, comprehensive market research report similar to the
translation services example, combining:
- Problem (pain points)
- Solution (solution ideas)
- Competitors (competitive analysis)
- SEO Strategy (comprehensive keyword strategy)
"""


from ..models.research_state import FinalReport
from ..models.seo_strategy import (
    SEOStrategyReport,
)


def generate_markdown_report(final_report: FinalReport) -> str:
    """
    Generate comprehensive markdown report from FinalReport model.

    Args:
        final_report: Complete FinalReport with all sections

    Returns:
        Formatted markdown string (3000-5000+ words)
    """
    sections = []

    # Header
    sections.append(_generate_header(final_report))

    # Executive Summary
    sections.append(_generate_executive_summary(final_report))

    # Solution Selection (Stage 5)
    sections.append(_generate_solution_selection_section(final_report))

    # Problem Section (Pain Points)
    sections.append(_generate_pain_points_section(final_report))

    # Solution Section (Solution Ideas)
    sections.append(_generate_solutions_section(final_report))

    # Competitive Section
    sections.append(_generate_competitive_section(final_report))

    # Market Validation
    sections.append(_generate_market_validation(final_report))

    # SEO Strategy (Comprehensive)
    if final_report.seo_strategy:
        sections.append(_generate_seo_strategy_section(final_report.seo_strategy))

    # Data Sourcing
    sections.append(_generate_data_sourcing_section(final_report))

    # Next Steps
    sections.append(_generate_next_steps(final_report))

    return "\n\n".join(sections)

def _generate_header(report: FinalReport) -> str:
    """Generate report header."""
    timestamp = report.generated_at.strftime("%B %Y")
    return f"""# {report.niche.upper()} - MARKET RESEARCH & STRATEGY REPORT
## Comprehensive Analysis & Implementation Plan

---

**Generated:** {timestamp}
**Research Pipeline:** NicheIQ 16-Stage Analysis"""

def _generate_executive_summary(report: FinalReport) -> str:
    """Generate executive summary section."""
    return f"""## EXECUTIVE SUMMARY

{report.executive_summary}"""

def _generate_solution_selection_section(report: FinalReport) -> str:
    """Generate solution selection section (Stage 5)."""
    section = [
        "---",
        "",
        "## SOLUTION SELECTION (Stage 5)",
        "",
        f"### Selected Solution: {report.selected_solution_name}",
        "",
        "**Selection Rationale:**",
        "",
        report.selection_rationale,
        "",
    ]

    # Add runner-up solutions if any (from alternative_solutions)
    if report.alternative_solutions:
        section.extend([
            "**Runner-up Solutions Considered:**",
            "",
        ])
        for i, alt in enumerate(report.alternative_solutions, 1):
            section.append(f"{i}. {alt.solution_name}")
        section.append("")

    # Add note about SEO focus
    section.extend([
        "*Note: The keyword research and SEO strategy (Stage 9) are focused exclusively on the selected solution above.*",
        "",
    ])

    return "\n".join(section)

def _generate_pain_points_section(report: FinalReport) -> str:
    """Generate pain points section."""
    section = [
        "---",
        "",
        "## VALIDATED PAIN POINTS",
        "",
        report.pain_points_summary,
        "",
        "### Top Pain Points Identified:",
        "",
    ]

    if report.detailed_pain_points:
        for i, pain_point in enumerate(report.detailed_pain_points, 1):
            section.append(f"{i}. **{pain_point.title}**")

    return "\n".join(section)

def _generate_solutions_section(report: FinalReport) -> str:
    """Generate solutions section."""
    section = [
        "---",
        "",
        "## RECOMMENDED SOLUTIONS",
        "",
        report.solutions_summary,
        "",
        "### Priority Solutions:",
        "",
    ]

    for i, solution in enumerate(report.recommended_solutions, 1):
        section.append(f"{i}. **{solution}**")

    return "\n".join(section)

def _generate_competitive_section(report: FinalReport) -> str:
    """Generate competitive landscape section."""
    return f"""---

## COMPETITIVE LANDSCAPE

{report.competitive_summary}"""

def _generate_market_validation(report: FinalReport) -> str:
    """Generate market validation section."""
    return f"""---

## MARKET VALIDATION

{report.market_validation}"""

def _generate_seo_strategy_section(seo: SEOStrategyReport) -> str:
    """
    Generate comprehensive SEO strategy section matching translation services example.
    """
    sections = [
        "---",
        "",
        "## KEYWORD RESEARCH & SEO STRATEGY",
        "## Comprehensive SEO Implementation Plan",
        "",
        "---",
        "",
        f"**Total Keywords Analyzed:** {seo.total_keywords_analyzed:,} keywords with measurable search volume",
        f"**Total Monthly Search Volume:** {seo.total_monthly_volume:,} searches/month",
        "",
        "### Key Findings",
        "",
    ]

    # Add key findings
    for finding in seo.key_findings:
        sections.append(f"- {finding}")

    sections.extend([
        "",
        "---",
        "",
        "## TOP KEYWORD OPPORTUNITIES (Priority Targets)",
        "",
    ])

    # TIER 1: Immediate Implementation
    if seo.tier_1_keywords:
        sections.extend([
            "### TIER 1: Immediate Implementation (High Volume + Low Competition)",
            "",
            "| Keyword | Monthly Volume | Difficulty | Competition | Opportunity Score | Strategy |",
            "|---------|---------------|------------|-------------|-------------------|----------|",
        ])

        for kw in seo.tier_1_keywords:
            opp_score = f"{kw.opportunity_score:,}" if kw.opportunity_score else "N/A"
            difficulty = f"{kw.keyword_difficulty:.0f}" if kw.keyword_difficulty is not None else "N/A"
            sections.append(
                f"| **{kw.keyword}** | {kw.search_volume:,} | {difficulty} | {kw.competition} | {opp_score} | {kw.strategy} |"
            )

        sections.append("")

        # Tier 1 strategy narrative
        if seo.tier_1_quick_win_strategy:
            sections.extend([
                f"**Quick Win Strategy:** {seo.tier_1_quick_win_strategy}",
                "",
            ])

    # TIER 2: High Value Keywords
    if seo.tier_2_keywords:
        sections.extend([
            "---",
            "",
            "### TIER 2: High Value Keywords",
            "",
            "| Keyword | Monthly Volume | Difficulty | Competition | Intent |",
            "|---------|---------------|------------|-------------|--------|",
        ])

        for kw in seo.tier_2_keywords:
            intent = kw.intent if kw.intent else "N/A"
            difficulty = f"{kw.keyword_difficulty:.0f}" if kw.keyword_difficulty is not None else "N/A"
            sections.append(
                f"| **{kw.keyword}** | {kw.search_volume:,} | {difficulty} | {kw.competition} | {intent} |"
            )

        sections.append("")

        # Tier 2 strategy narrative
        if seo.tier_2_strategy:
            sections.extend([
                f"**Strategy:** {seo.tier_2_strategy}",
                "",
            ])

    # TIER 3: Geographic Opportunities
    if seo.tier_3_geographic_groups:
        sections.extend([
            "---",
            "",
            "### TIER 3: Geographic Market Opportunities",
            "",
        ])

        for group in seo.tier_3_geographic_groups:
            sections.extend([
                f"#### {group.region_name}",
                f"**Total Volume: {group.total_volume:,}/month | Competition: {group.competition_level}**",
                "",
                "| City/Region | Keyword | Monthly Volume | Notes |",
                "|------------|---------|---------------|-------|",
            ])

            for kw in group.keywords:
                city = kw.get("city", "N/A")
                keyword = kw.get("keyword", "N/A")
                volume = kw.get("monthly_volume", 0)
                notes = kw.get("notes", "")
                sections.append(f"| {city} | {keyword} | {volume:,} | {notes} |")

            sections.extend([
                "",
                f"**Strategy:** {group.strategy_notes}",
                "",
            ])

    # TIER 4: Category/Specialized Opportunities
    if seo.tier_4_category_groups:
        sections.extend([
            "---",
            "",
            "### TIER 4: Specialized/Category Opportunities",
            "",
        ])

        for group in seo.tier_4_category_groups:
            sections.extend([
                f"#### {group.category_name}",
                f"**Total Volume: {group.total_volume:,}/month**",
                "",
                "| Type/Category | Monthly Volume | Competition | Notes |",
                "|--------------|---------------|-------------|-------|",
            ])

            for kw in group.keywords:
                doc_type = kw.get("document_type") or kw.get("category", "N/A")
                volume = kw.get("monthly_volume", 0)
                comp = kw.get("competition", "N/A")
                cpc = kw.get("cpc") or 0
                cpc_formatted = f"${cpc:.2f}" if cpc > 0 else "N/A"
                sections.append(f"| {doc_type} | {volume:,} | {comp} | {cpc_formatted} |")

            sections.extend([
                "",
                f"**Strategy:** {group.strategy_recommendation}",
                "",
            ])

    # Content Strategy
    sections.extend([
        "---",
        "",
        seo.content_strategy,
        "",
    ])

    # Topic Clusters (if any)
    if seo.topic_clusters:
        sections.extend([
            "### Topic Clusters / Content Pillars",
            "",
        ])

        for cluster in sorted(seo.topic_clusters, key=lambda x: x.priority):
            sections.extend([
                f"#### {cluster.cluster_name} (Priority: {cluster.priority}/5)",
                f"**Primary Keyword:** {cluster.primary_keyword}",
                f"**Total Monthly Volume:** {cluster.total_monthly_volume:,}",
                f"**Estimated Traffic Potential:** {cluster.estimated_traffic_potential}",
                "",
                "**Supporting Keywords:**",
            ])

            for kw in cluster.supporting_keywords:
                sections.append(f"- {kw}")

            sections.extend([
                "",
                f"**Content Recommendation:** {cluster.content_recommendation}",
                "",
            ])

    # Technical SEO
    sections.extend([
        "---",
        "",
        seo.technical_seo_recommendations,
        "",
    ])

    # Competitive Positioning
    sections.extend([
        "---",
        "",
        seo.competitive_positioning,
        "",
    ])

    # Implementation Roadmap
    sections.extend([
        "---",
        "",
        seo.implementation_roadmap,
        "",
    ])

    # Key Metrics
    sections.extend([
        "---",
        "",
        "## KEY METRICS TO TRACK",
        "",
    ])

    for metric in seo.key_metrics_to_track:
        sections.append(f"- {metric}")

    sections.append("")

    # Risk Mitigation (optional)
    if seo.risk_mitigation:
        sections.extend([
            "---",
            "",
            seo.risk_mitigation,
            "",
        ])

    # Budget Allocation (optional)
    if seo.budget_allocation:
        sections.extend([
            "---",
            "",
            seo.budget_allocation,
            "",
        ])

    # Conclusion
    sections.extend([
        "---",
        "",
        "## CONCLUSION",
        "",
        f"**Bottom Line:** {seo.conclusion_bottom_line}",
        "",
    ])

    # Next Steps Checklist
    sections.extend([
        "---",
        "",
        "## NEXT STEPS (SEO Implementation)",
        "",
    ])

    for step in seo.next_steps_checklist:
        sections.append(step)

    return "\n".join(sections)

def _generate_data_sourcing_section(report: FinalReport) -> str:
    """Generate data sourcing recommendations."""
    return f"""---

## DATA SOURCING RECOMMENDATIONS

{report.data_sourcing_recommendations}"""

def _generate_next_steps(report: FinalReport) -> str:
    """Generate next steps section."""
    section = [
        "---",
        "",
        "## NEXT STEPS (Implementation Roadmap)",
        "",
    ]

    for i, step in enumerate(report.next_steps, 1):
        section.append(f"{i}. {step}")

    section.extend([
        "",
        "---",
        "",
        f"**Report Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "*This report was generated by NicheIQ - AI-Powered Market Research Pipeline*",
    ])

    return "\n".join(section)
