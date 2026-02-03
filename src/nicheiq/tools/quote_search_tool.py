"""
QuoteSearchTool - Vector search tool for Task 4 quote enrichment.

Wraps CrewAI Knowledge.query() to search embedded discussions and return
results with post_id metadata for reliable source attribution.
"""

from typing import Any, Optional

from crewai.knowledge.knowledge import Knowledge
from crewai.tools import BaseTool
from loguru import logger
from pydantic import Field


class QuoteSearchTool(BaseTool):
    """
    Semantic search through Reddit/Twitter discussions.

    Input: search query (pain point keywords/phrases).
    Returns: relevant discussion chunks with post_id from metadata.

    The agent should extract verbatim quotes from results and use the
    post_id from result headers for source attribution.
    """

    name: str = "search_discussions"
    description: str = (
        "Semantic search through Reddit/Twitter discussions. "
        "Input: search query (pain point keywords/phrases). "
        "Returns relevant discussion chunks with post_id in the header. "
        "IMPORTANT: Extract verbatim quotes from results. "
        "The post_id is provided in each result header - use it for attribution."
    )

    # Private attribute for knowledge instance (not serialized)
    _knowledge: Optional[Knowledge] = None

    def __init__(self, knowledge: Optional[Knowledge] = None, **kwargs: Any):
        """
        Initialize with a Knowledge instance for vector search.

        Args:
            knowledge: CrewAI Knowledge instance with embedded discussions
            **kwargs: Additional BaseTool arguments
        """
        super().__init__(**kwargs)
        self._knowledge = knowledge

    def _run(self, query: str) -> str:
        """
        Execute semantic search against embedded discussions.

        Args:
            query: Search query (pain point keywords or phrases)

        Returns:
            Formatted search results with post_id in headers
        """
        if self._knowledge is None:
            return "Error: Knowledge base not initialized. Cannot search discussions."

        if not query or not query.strip():
            return "Error: Empty query. Provide pain point keywords or phrases to search."

        try:
            # Query the knowledge base
            # Results are TypedDict with: id, content, metadata, score
            results = self._knowledge.query(
                query=[query.strip()],
                results_limit=15,  # Get top 15 results
            )

            if not results:
                return (
                    f"No matches found for query: '{query}'. "
                    "Try different keywords or rephrase your search."
                )

            # Format results with post_id prominently displayed
            formatted = []
            for i, result in enumerate(results, 1):
                # Extract fields from result dict
                content = result.get("content", "")
                metadata = result.get("metadata", {})
                score = result.get("score", 0.0)

                # Get post_id from metadata (key feature of custom knowledge sources)
                post_id = metadata.get("post_id", "unknown")
                source_type = metadata.get("source_type", "unknown")

                # Format with clear post_id header for agent extraction
                formatted.append(
                    f"--- Result {i} (score: {score:.2f}, post_id: {post_id}, source: {source_type}) ---\n"
                    f"{content}"
                )

            logger.debug(f"QuoteSearchTool: Found {len(results)} results for '{query}'")
            return "\n\n".join(formatted)

        except Exception as e:
            logger.error(f"QuoteSearchTool search failed: {e}")
            return f"Search error: {e}. Try rephrasing your query."
