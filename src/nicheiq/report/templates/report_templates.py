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

        # Data-driven CAC advantage sentence
        cac_advantage = ReportTemplates._compute_cac_advantage(
            cac_organic, cac_paid, solution
        )
        table += f"\n{cac_advantage}"

        return table

    @staticmethod
    def _compute_cac_advantage(
        cac_organic: str, cac_paid: str, solution: "SolutionIdea"
    ) -> str:
        """Compute a data-driven CAC advantage sentence from actual values."""
        niche = getattr(solution, 'solution_name', 'this niche') or 'this niche'
        indexable_pages = solution.estimated_indexable_pages if solution else None

        # Try to extract midpoint numbers from CAC strings like "$5-15" or "$10"
        def extract_midpoint(val: str) -> float | None:
            if not val or val == "N/A":
                return None
            import re
            numbers = re.findall(r'\d+\.?\d*|\.\d+', val)
            if not numbers:
                return None
            nums = []
            for n in numbers:
                try:
                    nums.append(float(n))
                except ValueError:
                    continue
            if not nums:
                return None
            return sum(nums) / len(nums)

        org_mid = extract_midpoint(cac_organic) if isinstance(cac_organic, str) else None
        paid_mid = extract_midpoint(cac_paid) if isinstance(cac_paid, str) else None

        if org_mid and paid_mid and org_mid > 0:
            ratio = paid_mid / org_mid
            page_note = f", driven by {indexable_pages:,}+ programmatic pages" if indexable_pages else ""
            return f"**CAC Advantage:** Organic acquisition costs approximately {ratio:.0f}x less than paid channels for {niche}{page_note}."

        # Fallback with whatever data is available
        if indexable_pages:
            return f"**CAC Advantage:** Programmatic SEO across {indexable_pages:,}+ pages enables low-cost organic acquisition for {niche}."
        return f"**CAC Advantage:** Organic acquisition through programmatic SEO reduces customer acquisition costs for {niche}."
