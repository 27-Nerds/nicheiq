"""
LLM-based search query generator for finding niche pain points.

Generates strategic search queries using context-aware prompting.
"""

import json
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from loguru import logger

from ...config.settings import settings
from ..parsing.json_extractor import extract_json_array_from_text
from ..prompts import get_prompt

if TYPE_CHECKING:
    from ...models.research_state import NicheContext

class QueryGenerator:
    """LLM-based search query generator for finding niche pain points."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.7,
            api_key=settings.openai_api_key,
            timeout=120,
        )

    def _sanitize_for_prompt(self, text: str, max_length: int = 1000) -> str:
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

    def generate_queries(
        self,
        niche_description: str,
        niche_context: "NicheContext | None" = None,
        num_queries: int = 20
    ) -> list[dict]:
        """
        Generate strategic search queries for a niche using LLM.

        Args:
            niche_description: Description of the niche to generate queries for
            niche_context: Optional structured context with market segments and boundaries
            num_queries: Number of queries to generate

        Returns:
            List of query dictionaries with 'query', 'type', 'platform', and 'rationale' keys
        """

        # Use context if available, otherwise create minimal context
        if niche_context:
            # Sanitize all user-provided inputs to prevent prompt injection
            sanitized_description = self._sanitize_for_prompt(niche_context.niche_description)
            sanitized_segments = [self._sanitize_for_prompt(seg, max_length=500) for seg in niche_context.market_segments]
            sanitized_boundaries = self._sanitize_for_prompt(niche_context.industry_boundaries)

            segments_formatted = "\n".join([f"{i+1}. {seg}" for i, seg in enumerate(sanitized_segments)])
            context_section = f"""
**NICHE CONTEXT:**

Niche Description: {sanitized_description}

Market Segments:
{segments_formatted}

Industry Boundaries: {sanitized_boundaries}
"""
        else:
            # Fallback mode: minimal context (sanitized)
            sanitized_niche = self._sanitize_for_prompt(niche_description)
            context_section = f"""
**NICHE CONTEXT:**

Niche Description: {sanitized_niche}

Market Segments: [Not provided - use broad discovery queries]

Industry Boundaries: [Not provided - use general heuristics]
"""

        prompt = get_prompt(
            "query_generation",
            context_section=context_section,
            num_queries=num_queries
        )

        try:
            logger.info(f"Generating search queries for niche: {niche_description[:50]}...")

            # Log context availability
            if niche_context:
                logger.info(f"[OK] Using structured NicheContext with {len(niche_context.market_segments)} market segments")
            else:
                logger.warning("No NicheContext provided - using fallback mode with minimal context")

            # Log the prompt at DEBUG level
            logger.debug("=" * 80)
            logger.debug("QUERY GENERATION PROMPT (Context-Aware)")
            logger.debug("=" * 80)
            logger.debug(prompt)
            logger.debug("=" * 80)

            response = self.llm.invoke(prompt)

            # Extract JSON from response
            content = response.content

            # Log the raw response at DEBUG level
            logger.debug("=" * 80)
            logger.debug("QUERY GENERATION RESPONSE")
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
                    q.setdefault('type', 'problem')
                    q.setdefault('platform', 'both')
                    q.setdefault('rationale', 'No rationale provided')

                    valid_queries.append(q)

                if len(valid_queries) < len(queries):
                    logger.warning(f"Filtered out {len(queries) - len(valid_queries)} invalid queries")

                queries = valid_queries
                logger.info(f"[OK] Generated {len(queries)} valid search queries")

                # Log each query at DEBUG level with rationale
                logger.debug("Generated queries with rationale:")
                for i, q in enumerate(queries, 1):
                    logger.debug(
                        f"  {i}. [{q.get('type', 'unknown')}|{q.get('platform', 'both')}] "
                        f"{q.get('query', 'N/A')}\n"
                        f"     Rationale: {q.get('rationale', 'N/A')}"
                    )

                # Validate queries semantically (log warnings for suspicious patterns)
                suspicious_count = 0
                for q in queries:
                    query_text = q.get('query', '').lower()

                    # Check for potentially nonsensical patterns
                    if 'apps for' in query_text or 'app for' in query_text:
                        # Only warn if this seems like a physical product niche
                        if any(word in niche_description.lower() for word in ['appliance', 'furniture', 'tool', 'hardware', 'physical']):
                            logger.warning(f"[WARN] Suspicious query (apps for physical product): {q.get('query')}")
                            suspicious_count += 1

                    if 'enterprise' in query_text or 'for teams' in query_text:
                        # Only warn if this seems like a consumer niche
                        if any(word in niche_description.lower() for word in ['personal', 'home', 'individual', 'consumer', 'household']):
                            logger.warning(f"[WARN] Suspicious query (B2B terms for B2C niche): {q.get('query')}")
                            suspicious_count += 1

                if suspicious_count > 0:
                    logger.warning(f"[WARN] Found {suspicious_count} potentially nonsensical queries - review rationales above")

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
            logger.error(f"Unexpected error in query generation: {e}", exc_info=True)
            return []
