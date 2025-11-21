"""
Helper utilities for NicheIQ.

Most utilities are in dedicated submodules:
- generation/ - Query and keyword generators (QueryGenerator, CompetitorQueryGenerator, KeywordSeedGenerator)
- validation/ - Thread and keyword validators (ThreadRelevanceValidator, KeywordRelevanceValidator)
- parsing/ - JSON extraction utilities (extract_json_array_from_text)
"""

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..models.solution_idea import SolutionIdea

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def find_solution_by_name(
    solution_name: str,
    solution_list: list['SolutionIdea']
) -> 'SolutionIdea | None':
    """
    Find solution by name with fuzzy matching fallback.

    Handles cases where LLM returns shortened names (e.g., "PaperPath" instead of
    "PaperPath (Global Paperwork Aggregator)").

    Used by: Stage 9 (SEO), Stage 9.5 (SEO refinement), Stage 10 (Report generation).

    Args:
        solution_name: Name to search for (may be shortened)
        solution_list: List of SolutionIdea objects to search

    Returns:
        Matching SolutionIdea or None if no match found
    """
    # Validate inputs
    if not solution_name or not solution_list:
        return None

    # Try exact match first
    exact_match = next(
        (sol for sol in solution_list
         if hasattr(sol, 'solution_name') and sol.solution_name == solution_name),
        None
    )

    if exact_match:
        return exact_match

    # Try fuzzy match: case-insensitive substring search
    # (handles "PaperPath" matching "PaperPath (Global Paperwork Aggregator)")
    logger.warning(
        f"Exact match failed for solution name '{solution_name}'. "
        f"Attempting fuzzy match..."
    )

    search_name_lower = solution_name.lower()
    for solution in solution_list:
        if not hasattr(solution, 'solution_name'):
            continue
        if search_name_lower in solution.solution_name.lower():
            logger.warning(
                f"✓ Fuzzy match found: '{solution_name}' → '{solution.solution_name}'"
            )
            return solution

    # No match found
    logger.error(
        f"No match found for solution '{solution_name}' in available solutions: "
        f"{[sol.solution_name for sol in solution_list]}"
    )
    return None


def sanitize_collection_name(niche: str, crew_name: str) -> str:
    """
    Generate valid ChromaDB collection name for knowledge isolation.

    ChromaDB requirements:
    - Length: 3-63 characters
    - Valid chars: [a-zA-Z0-9_-] only
    - Cannot be IPv4 pattern

    Args:
        niche: The research niche (e.g., "AI tools for content creators")
        crew_name: Short crew identifier (e.g., "pain", "seo", "solution")

    Returns:
        Valid collection name like "pain_ai_tools_for_content_creators"
    """
    import re

    # Replace invalid chars with underscore
    slug = re.sub(r'[^a-zA-Z0-9_-]', '_', niche.lower())
    # Remove consecutive underscores
    slug = re.sub(r'_+', '_', slug).strip('_')

    # Truncate: crew_name + slug (max 63 chars total)
    max_slug_len = 63 - len(crew_name) - 1  # -1 for underscore separator
    slug = slug[:max_slug_len]

    name = f"{crew_name}_{slug}"

    # Ensure minimum length (3 chars)
    if len(name) < 3:
        name = f"{name}_kb"

    return name
