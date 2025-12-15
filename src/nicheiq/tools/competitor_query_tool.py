"""
CompetitorQueryTool - CrewAI tool for generating context-aware competitor search queries.
Uses CompetitorQueryGenerator with semantic validation.
"""

from crewai.tools import BaseTool

from ..models.research_state import NicheContext
from ..utils.generation import CompetitorQueryGenerator


class CompetitorQueryTool(BaseTool):
    """
    Tool for generating context-aware competitor search queries.
    Uses CompetitorQueryGenerator with semantic validation.
    """

    name: str = "generate_competitor_queries"
    description: str = (
        "Generate strategic competitor search queries for a solution. "
        "Input format: 'solution_name|project_type|pain_points' "
        "(pain_points is comma-separated list, optional). "
        "Returns list of validated search queries with rationale."
    )

    _generator: CompetitorQueryGenerator = None
    _niche_context: NicheContext | None = None

    def __init__(self, niche_context: NicheContext | None = None, **kwargs):
        super().__init__(**kwargs)
        self._generator = CompetitorQueryGenerator()
        self._niche_context = niche_context

    def _run(self, input_str: str) -> str:
        """Generate competitor queries from input string."""
        parts = input_str.split("|")
        solution_name = parts[0].strip() if len(parts) > 0 else ""
        project_type = parts[1].strip() if len(parts) > 1 else "saas"
        pain_points = (
            [p.strip() for p in parts[2].split(",")]
            if len(parts) > 2 and parts[2].strip()
            else None
        )

        queries = self._generator.generate_competitor_queries(
            solution_name=solution_name,
            project_type=project_type,
            niche_context=self._niche_context,
            pain_points_addressed=pain_points,
            num_queries=8,
        )

        if not queries:
            return "No queries generated. Try with different input."

        # Format output for agent consumption
        result = f"Generated {len(queries)} competitor search queries:\n\n"
        for i, q in enumerate(queries, 1):
            result += f"{i}. [{q.get('type', 'category')}] {q.get('query')}\n"
            result += f"   Rationale: {q.get('rationale', 'N/A')}\n\n"

        return result
