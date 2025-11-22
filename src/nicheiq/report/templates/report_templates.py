"""
Reusable report templates for common sections.

These templates generate formatted text sections for the final report.
All methods are static to allow easy reuse across different report types.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.solution_idea import SolutionIdea


class ReportTemplates:
    """Static template generators for report sections."""

    @staticmethod
    def user_journey(solution: "SolutionIdea") -> str | None:
        """
        Generate user journey section from solution features.

        Args:
            solution: SolutionIdea with core_features

        Returns:
            Formatted user journey markdown, or None if no features
        """
        if not solution or not solution.core_features:
            return None

        steps = [
            f"{i}. {feature}"
            for i, feature in enumerate(solution.core_features, 1)
        ]
        return "## User Journey\n\n" + "\n".join(steps)

    @staticmethod
    def implementation_overview(solution: "SolutionIdea") -> str | None:
        """
        Generate implementation overview with 3-phase plan.

        Args:
            solution: SolutionIdea with estimated_development_time and technical_approach

        Returns:
            Formatted implementation overview markdown, or None if no solution
        """
        if not solution:
            return None

        dev_time = solution.estimated_development_time or "Development timeline not estimated"
        tech = solution.technical_approach or "Technical approach not specified"

        return f"""## Implementation Overview

**Phase 1: MVP Development** ({dev_time})
Build core functionality using {tech}. Focus on delivering essential features.

**Phase 2: Enhancement & Scaling**
Add advanced features, optimize performance, implement user feedback.

**Phase 3: Market Expansion**
Expand to new markets or segments based on validated learnings."""

    @staticmethod
    def mvp_scope(solution: "SolutionIdea") -> str | None:
        """
        Generate MVP scope definition with must-have vs post-MVP features.

        Args:
            solution: SolutionIdea with core_features

        Returns:
            Formatted MVP scope markdown, or None if no features
        """
        if not solution or not solution.core_features:
            return None

        # Phase 1.4: Show all features as MVP (removed arbitrary 4-feature split)
        must_have = solution.core_features
        post_mvp = []  # All features considered MVP-critical

        mvp_text = "## MVP Scope\n\n### Must-Have Features\n"
        mvp_text += "\n".join([f"- {f}" for f in must_have])

        if post_mvp:
            mvp_text += "\n\n### Post-MVP Features\n"
            mvp_text += "\n".join([f"- {f}" for f in post_mvp])

        mvp_text += "\n\n### Success Criteria\n"
        mvp_text += "- 100+ active users within 3 months\n"
        mvp_text += "- 60%+ weekly active users\n"
        mvp_text += "- First paying customer within 6 months"

        return mvp_text

    @staticmethod
    def acquisition_strategy(solution: "SolutionIdea") -> str | None:
        """
        Generate customer acquisition strategy overview.

        Args:
            solution: SolutionIdea with estimated_indexable_pages, project_type, value_proposition

        Returns:
            Formatted acquisition strategy markdown, or None if no solution or missing required data
        """
        if not solution:
            return None

        # Return None if critical data is missing
        if not solution.estimated_indexable_pages:
            return None

        page_count = solution.estimated_indexable_pages
        project_type = solution.project_type or "Project type not specified"
        value_prop = solution.value_proposition

        return f"""## Customer Acquisition Strategy

**Content Generation Model:** The solution architecture enables programmatic generation of {page_count:,}+ indexable pages through {project_type} functionality.

**Discovery Patterns:** Users will discover the platform through organic search queries targeting {value_prop}.

**Scaling Strategy:** Each data entity creates a unique landing page, enabling exponential growth in organic traffic as the database expands."""

    @staticmethod
    def cac_breakdown(solution: "SolutionIdea") -> str | None:
        """
        Generate CAC (Customer Acquisition Cost) breakdown table.

        Args:
            solution: SolutionIdea with CAC estimates and SEO scalability

        Returns:
            Formatted CAC breakdown markdown with table, or None if no solution or missing required data
        """
        if not solution:
            return None

        cac_organic = solution.estimated_cac_organic or "N/A"
        cac_paid = solution.estimated_cac_paid or "N/A"

        # Build base table
        table = f"""## CAC Breakdown

| Channel | Estimated CAC | Rationale |
|---------|--------------|-----------|
| Organic (SEO) | {cac_organic} | """

        # Add rationale with page count if available
        if solution.estimated_indexable_pages:
            table += f"Programmatic content via {solution.estimated_indexable_pages:,}+ pages |\n"
        else:
            table += "Page count requires technical analysis |\n"

        table += f"| Paid (SEM) | {cac_paid} | Industry benchmark for paid acquisition |\n"

        # Add SEO scalability section only if score is available
        if solution.seo_scalability_score is not None:
            scalability = solution.seo_scalability_score

            # Determine scalability rating
            if scalability >= 0.8:
                rating = "Excellent"
            elif scalability >= 0.6:
                rating = "Good"
            else:
                rating = "Moderate"

            table += f"\n**SEO Scalability:** {scalability:.1f}/10 - {rating} organic growth potential.\n"

        table += "\n**CAC Advantage:** Organic acquisition through programmatic SEO significantly reduces customer acquisition costs compared to paid channels."

        return table
