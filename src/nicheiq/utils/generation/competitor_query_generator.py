"""
LLM-based competitive search query generator with semantic validation.

Generates strategic competitor search queries using context-aware prompting.
"""

import json
import re
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from loguru import logger

from ...config.settings import settings
from ..parsing.json_extractor import extract_json_array_from_text
from ..prompts import get_prompt

if TYPE_CHECKING:
    from ...models.research_state import NicheContext

class CompetitorQueryGenerator:
    """LLM-based competitive search query generator with semantic validation."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.7,
            api_key=settings.openai_api_key,
            timeout=120,
        )

    def _sanitize_for_prompt(self, text: str, max_length: int = 500) -> str:
        """
        Sanitize user input for safe prompt inclusion.

        Args:
            text: User-provided text to sanitize
            max_length: Maximum length to allow

        Returns:
            Sanitized text safe for prompt inclusion
        """
        # Strip excessive whitespace and newlines to prevent instruction injection
        text = " ".join(text.split())
        # Truncate to reasonable length
        text = text[:max_length]
        return text

    def _extract_json_array(self, text: str) -> list | None:
        """Extract first complete JSON array from text."""
        return extract_json_array_from_text(text)

    def generate_competitor_queries(
        self,
        solution_name: str,
        project_type: str,
        niche_context: "NicheContext | None" = None,
        pain_points_addressed: list[str | None] = None,
        num_queries: int = 8
    ) -> list[dict]:
        """
        Generate strategic competitor search queries for a solution.

        Args:
            solution_name: Name of the solution to find competitors for
            project_type: Solution type (saas, directory, aggregator, comparison-tool, marketplace)
            niche_context: Optional structured context with market segments and boundaries
            pain_points_addressed: Optional list of pain points the solution addresses
            num_queries: Number of queries to generate (default: 8)

        Returns:
            List of query dictionaries with 'query', 'type', and 'rationale' keys
        """

        # Sanitize inputs
        sanitized_solution = self._sanitize_for_prompt(solution_name)
        sanitized_project_type = self._sanitize_for_prompt(project_type, max_length=50)

        # Build context section
        if niche_context:
            sanitized_description = self._sanitize_for_prompt(niche_context.niche_description)
            sanitized_segments = [self._sanitize_for_prompt(seg, max_length=300) for seg in niche_context.market_segments]
            sanitized_boundaries = self._sanitize_for_prompt(niche_context.industry_boundaries)

            segments_formatted = "\n".join([f"{i+1}. {seg}" for i, seg in enumerate(sanitized_segments)])
            context_section = f"""
**SOLUTION CONTEXT:**

Solution Name: {sanitized_solution}
Project Type: {sanitized_project_type}
Niche Description: {sanitized_description}

Market Segments:
{segments_formatted}

Industry Boundaries: {sanitized_boundaries}
"""
        else:
            # Fallback mode
            context_section = f"""
**SOLUTION CONTEXT:**

Solution Name: {sanitized_solution}
Project Type: {sanitized_project_type}
Niche Description: [Not provided]
Market Segments: [Not provided]
Industry Boundaries: [Not provided]
"""

        # Add pain points if available
        if pain_points_addressed:
            sanitized_pain_points = [self._sanitize_for_prompt(pp, max_length=200) for pp in pain_points_addressed[:5]]
            pain_points_formatted = "\n".join([f"- {pp}" for pp in sanitized_pain_points])
            context_section += f"""
Pain Points Addressed:
{pain_points_formatted}
"""

        prompt = get_prompt(
            "competitor_query",
            context_section=context_section,
            num_queries=num_queries,
            project_type=sanitized_project_type
        )

        try:
            logger.info(f"Generating competitor search queries for: {solution_name} (type: {project_type})")

            # Log context availability
            if niche_context:
                logger.info(f"[OK] Using NicheContext with {len(niche_context.market_segments)} market segments")
            else:
                logger.warning("No NicheContext provided - using minimal context for competitor search")

            # Log the prompt at DEBUG level
            logger.debug("=" * 80)
            logger.debug("COMPETITOR QUERY GENERATION PROMPT")
            logger.debug("=" * 80)
            logger.debug(prompt)
            logger.debug("=" * 80)

            response = self.llm.invoke(prompt)

            # Extract JSON from response
            content = response.content

            # Log the raw response at DEBUG level
            logger.debug("=" * 80)
            logger.debug("COMPETITOR QUERY GENERATION RESPONSE")
            logger.debug("=" * 80)
            logger.debug(content)
            logger.debug("=" * 80)

            # Extract JSON array using robust bracket matching
            queries = self._extract_json_array(content)
            if queries:
                # Validate query structure
                valid_queries = []
                for i, q in enumerate(queries):
                    if not isinstance(q, dict):
                        logger.warning(f"Skipping query {i}: not a dictionary")
                        continue

                    if 'query' not in q:
                        logger.warning(f"Skipping query {i}: missing 'query' field")
                        continue

                    # Ensure all expected fields exist with defaults
                    q.setdefault('type', 'category')
                    q.setdefault('rationale', 'No rationale provided')

                    valid_queries.append(q)

                if len(valid_queries) < len(queries):
                    logger.warning(f"Filtered out {len(queries) - len(valid_queries)} invalid competitor queries")

                queries = valid_queries
                logger.info(f"[OK] Generated {len(queries)} valid competitor search queries")

                # Log each query at DEBUG level with rationale
                logger.debug("Generated competitor queries with rationale:")
                for i, q in enumerate(queries, 1):
                    logger.debug(
                        f"  {i}. [{q.get('type', 'unknown')}] "
                        f"{q.get('query', 'N/A')}\n"
                        f"     Rationale: {q.get('rationale', 'N/A')}"
                    )

                # Validate queries semantically (log warnings for suspicious patterns)
                # Using word boundaries to avoid false positives (e.g., "app" in "appliance")
                suspicious_count = 0
                for q in queries:
                    query_text = q.get('query', '').lower()

                    # Check for mismatched type patterns with word boundaries
                    if project_type == 'directory':
                        # Flag standalone "software", "app" (not "apps"), or "tool" (not "tools")
                        if re.search(r'\bsoftware\b', query_text):
                            logger.warning(f"[WARN] Suspicious query (software term for directory solution): {q.get('query')}")
                            suspicious_count += 1

                    if project_type == 'saas':
                        # Flag "directory" or "catalog" or "guide" as standalone words
                        if re.search(r'\b(directory|catalog|guide)\b', query_text):
                            logger.warning(f"[WARN] Suspicious query (directory term for SaaS solution): {q.get('query')}")
                            suspicious_count += 1

                if suspicious_count > 0:
                    logger.warning(f"[WARN] Found {suspicious_count} potentially mismatched competitor queries - review rationales above")

                return queries
            else:
                logger.error("Could not extract valid JSON array from LLM response")
                logger.error(f"Response content: {content[:500]}...")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"Raw content: {content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in competitor query generation: {e}", exc_info=True)
            return []
