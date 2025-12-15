"""
LLM-based competitive search query generator with semantic validation.

Generates strategic competitor search queries using context-aware prompting.
"""

import json
import re
from typing import TYPE_CHECKING

from loguru import logger

from ...config.settings import settings
from ..llm_service import LLMService
from ..parsing.json_extractor import extract_json_array_from_text
from ..prompts import get_prompt

if TYPE_CHECKING:
    from ...models.research_state import NicheContext

class CompetitorQueryGenerator:
    """LLM-based competitive search query generator with semantic validation."""

    def __init__(self):
        pass  # No longer need to initialize LLM instance

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

    def _calculate_specificity_score(self, query: str) -> int:
        """
        Calculate specificity score for a competitor query (0-5 scale).

        Checks for presence of specificity markers:
        1. Named competitors (explicit product/brand names)
        2. Comparison operators (vs, versus, alternatives)
        3. Ranking signals (top N, best, leading)
        4. Concrete constraints (price, size, feature)
        5. Discovery intent (alternatives to, switching from)

        Args:
            query: The search query text

        Returns:
            Score from 0-5 based on marker presence
        """
        query_lower = query.lower()
        score = 0

        # A. Named Competitors (explicit product/brand names)
        # Common incumbents across various niches
        named_competitors = [
            # Review/comparison sites
            'wirecutter', 'consumer reports', 'cnet', 'tom\'s guide', 'reviewed',
            # B2B directories
            'g2', 'capterra', 'trustradius', 'software advice', 'getapp',
            # Tech/startup platforms
            'producthunt', 'product hunt', 'betalist', 'indie hackers', 'alternativeto',
            # Service marketplaces
            'angi', 'thumbtack', 'homeadvisor', 'taskrabbit', 'rover', 'wag',
            # Travel
            'kayak', 'skyscanner', 'google flights', 'expedia', 'tripadvisor', 'booking.com',
            # E-commerce/retail
            'amazon', 'walmart', 'target', 'costco', 'best buy',
            # Legal/professional
            'avvo', 'findlaw', 'martindale', 'lawyers.com', 'justia',
            # Finance
            'nerdwallet', 'bankrate', 'creditkarma', 'mint',
            # Pet care
            'chewy', 'petco', 'petsmart',
            # General
            'yelp', 'google maps', 'facebook marketplace', 'craigslist',
            # Developer resources
            'github', 'gitlab', 'stackoverflow', 'stack overflow', 'codepen', 'codesandbox',
            'dev.to', 'devdocs', 'mdn', 'readthedocs', 'postman', 'rapidapi', 'swagger',
            'jsfiddle', 'replit', 'glitch', 'gist', 'pastebin',
            # Payment/FinTech
            'stripe', 'stripe docs', 'paypal developer', 'square', 'plaid', 'twilio',
            'chargebee', 'recurly', 'paddle', 'braintree', 'adyen',
            # Package registries
            'npm', 'pypi', 'rubygems', 'maven', 'nuget', 'crates.io', 'packagist',
            # Data/Analytics
            'tableau', 'looker', 'metabase', 'grafana', 'superset',
        ]
        if any(competitor in query_lower for competitor in named_competitors):
            score += 1

        # B. Comparison Operators
        comparison_markers = [
            'vs', 'versus', 'compared to', 'better than', 'cheaper than',
            'instead of', 'or', ' v ', 'comparison'
        ]
        if any(marker in query_lower for marker in comparison_markers):
            score += 1

        # C. Ranking Signals
        ranking_markers = [
            'top 5', 'top 10', 'top 15', 'top 20', 'best', 'leading', 'popular',
            '2024', '2025', 'ranking', 'rated', 'reviewed', 'ranked'
        ]
        if any(marker in query_lower for marker in ranking_markers):
            score += 1

        # D. Concrete Constraints
        price_markers = ['free', 'cheap', 'affordable', 'budget', 'premium', 'enterprise', 'pricing', 'cost', 'under $', 'less than $']
        size_markers = ['small business', 'solo', 'startup', 'enterprise', 'team', 'individual', 'personal']
        feature_markers = ['with api', 'self-hosted', 'open source', 'verified', 'no ads', 'unbiased', 'transparent']
        all_constraints = price_markers + size_markers + feature_markers
        if any(marker in query_lower for marker in all_constraints):
            score += 1

        # E. Discovery Intent
        discovery_markers = [
            'alternatives', 'alternative to', 'like', 'similar to', 'switching from',
            'replacing', 'instead of', 'reviews of', 'comparing', 'deciding',
            'evaluation', 'which', 'what are'
        ]
        if any(marker in query_lower for marker in discovery_markers):
            score += 1

        return score

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

            # Use centralized LLM service for plain text invocation
            content, _usage = LLMService.invoke_plain(
                prompt=prompt,
                temperature=0.7,
                timeout=120,
                model_name=settings.openai_model_name
            )

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
                    # Support new intent-based types
                    valid_types = [
                        'named_competitor', 'evaluation', 'established_alternative',
                        'segment_discovery', 'problem_alternative',
                        # Legacy types (for backwards compatibility)
                        'category', 'alternative', 'segment', 'problem'
                    ]
                    if q.get('type') not in valid_types:
                        q['type'] = 'named_competitor'  # Default to highest priority type
                    q.setdefault('type', 'named_competitor')
                    q.setdefault('rationale', 'No rationale provided')

                    # Calculate specificity score for quality tracking
                    q['specificity_score'] = self._calculate_specificity_score(q.get('query', ''))

                    valid_queries.append(q)

                if len(valid_queries) < len(queries):
                    logger.warning(f"Filtered out {len(queries) - len(valid_queries)} invalid competitor queries")

                queries = valid_queries
                logger.info(f"[OK] Generated {len(queries)} valid competitor search queries")

                # Log each query at DEBUG level with rationale and specificity score
                logger.debug("Generated competitor queries with rationale and specificity:")
                high_specificity_count = 0
                for i, q in enumerate(queries, 1):
                    score = q.get('specificity_score', 0)
                    if score >= 3:
                        high_specificity_count += 1
                    score_indicator = "✓" if score >= 3 else "⚠"
                    logger.debug(
                        f"  {i}. [{q.get('type', 'unknown')}] "
                        f"(spec:{score}/5 {score_indicator}) {q.get('query', 'N/A')}\n"
                        f"     Rationale: {q.get('rationale', 'N/A')}"
                    )

                # Log specificity distribution
                specificity_pct = (high_specificity_count / len(queries) * 100) if queries else 0
                logger.info(f"  Specificity: {high_specificity_count}/{len(queries)} queries scored 3+/5 ({specificity_pct:.0f}%)")

                # Validate queries semantically (log warnings for suspicious patterns)
                # Using word boundaries to avoid false positives (e.g., "app" in "appliance")
                suspicious_count = 0
                low_specificity_count = 0
                for q in queries:
                    query_text = q.get('query', '').lower()
                    spec_score = q.get('specificity_score', 0)

                    # Check for low specificity (score < 3)
                    if spec_score < 3:
                        low_specificity_count += 1
                        logger.warning(f"[WARN] Low specificity ({spec_score}/5): {q.get('query')}")

                    # Check for generic terms that should be avoided
                    generic_terms = ['platforms', 'sites', 'tools', 'solutions', 'services']
                    if any(term in query_text for term in generic_terms):
                        # Only warn if combined with low specificity (no named competitors/intent)
                        if spec_score < 2:
                            logger.warning(f"[WARN] Generic term with low specificity: {q.get('query')}")
                            suspicious_count += 1

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
                if low_specificity_count > len(queries) * 0.3:  # More than 30% low specificity
                    logger.warning(f"[WARN] {low_specificity_count}/{len(queries)} queries have low specificity (<3/5)")

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
