"""
Helper utilities for NicheIQ.
"""

import json
import re
from typing import List, Optional

from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings


class QueryGenerator:
    """LLM-based search query generator for finding niche pain points."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.7,
            api_key=settings.openai_api_key,
        )

    def generate_queries(self, niche_description: str, num_queries: int = 15) -> List[dict]:
        """
        Generate strategic search queries for a niche using LLM.

        Args:
            niche_description: Description of the niche to generate queries for
            num_queries: Number of queries to generate

        Returns:
            List of query dictionaries with 'query', 'type', and 'platform' keys
        """
        prompt = f"""You are a search query strategist specializing in finding pain points and problems in specific niches.

Niche: {niche_description}

Generate {num_queries} strategic search queries designed to find genuine user pain points, problems, and frustrations in this niche.

Query Types to Cover:
1. Problem-oriented: Direct mentions of problems, pain points, issues
2. Frustration-oriented: Emotional expressions of frustration, complaints
3. Alternative-seeking: People looking for alternatives, better solutions
4. Solution-seeking: People asking for help, tools, recommendations

Platforms to Target:
- Reddit (discussions, complaints, advice-seeking)
- Twitter (real-time frustrations, quick takes)

Query Specificity Strategy:
Generate mostly GENERIC queries (70-80% of total) to cast a wide net and find diverse discussions:

Generic Query Structure (70-80% of queries):
- "[niche activity] problems"
- "[niche role] challenges"
- "[niche process] frustrations"
- "struggling with [niche task]"
- "[niche outcome] issues"
- "best solutions for [niche problem]"
- "[niche workflow] time consuming"
- "[niche result] not working"

Scenario-Based Queries (20-30% of queries): Specific situations without brand names
- Focus on common scenarios, workflows, or pain points in the niche
- Describe problems in natural language
- Avoid specific product or brand names

CRITICAL RULES:
- DO NOT use specific brand or tool names
- Focus on GENERIC problem categories and pain points
- Use broad, accessible language that captures many discussions
- Keep queries short and natural (3-8 words for generic, up to 12 for scenario-based)
- Think about underlying problems, not specific products
- Extract key concepts from the niche description and build queries around those
- Avoid comparisons between specific products

Return ONLY a valid JSON array with this structure:
[
  {{"query": "the search query text", "type": "problem|frustration|alternative|solution", "platform": "reddit|twitter|both"}},
  ...
]

Generate the queries now:"""

        try:
            logger.info(f"Generating search queries for niche: {niche_description[:50]}...")

            # Log the prompt at DEBUG level
            logger.debug("=" * 80)
            logger.debug("QUERY GENERATION PROMPT")
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

            # Try to find JSON array in the response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                queries = json.loads(json_match.group())
                logger.info(f"✓ Generated {len(queries)} search queries")

                # Log each query at DEBUG level
                logger.debug("Generated queries:")
                for i, q in enumerate(queries, 1):
                    logger.debug(f"  {i}. [{q.get('type', 'unknown')}|{q.get('platform', 'both')}] {q.get('query', 'N/A')}")

                return queries
            else:
                logger.error("Could not extract JSON from LLM response")
                logger.error(f"Response content: {content[:500]}...")
                return []

        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            return []


class SearchHelper:
    """Helper class for working with search results."""

    @staticmethod
    def build_reddit_query(query: str, subreddit: Optional[str] = None) -> str:
        """
        Build a Reddit-specific search query with site operator.

        Args:
            query: Search query
            subreddit: Optional specific subreddit to search

        Returns:
            Formatted search query with site: operator
        """
        if subreddit:
            return f"site:reddit.com/r/{subreddit} {query}"
        return f"site:reddit.com {query}"

    @staticmethod
    def build_twitter_query(query: str) -> str:
        """
        Build a Twitter-specific search query with site operator.

        Args:
            query: Search query

        Returns:
            Formatted search query with site: operator
        """
        return f"(site:twitter.com OR site:x.com) {query}"

    @staticmethod
    def extract_urls_from_serper(search_results: dict, domain: str) -> List[str]:
        """
        Extract URLs for a specific domain from SerperDevTool results.

        Args:
            search_results: Search results dict from SerperDevTool
            domain: Domain to filter for (e.g., 'reddit.com', 'twitter.com')

        Returns:
            List of extracted URLs
        """
        urls = []

        # Extract from organic results
        organic_results = search_results.get('organic', [])
        for result in organic_results:
            link = result.get('link', '')
            if link and domain in link:
                # For Reddit, only include submission URLs (not subreddit pages)
                if 'reddit.com' in domain:
                    # Reddit submission URLs contain '/comments/'
                    if '/comments/' in link:
                        urls.append(link)
                # For Twitter/X, only include tweet status URLs (not profiles or share links)
                elif 'twitter.com' in domain or 'x.com' in domain:
                    # Twitter status URLs contain '/status/'
                    if '/status/' in link:
                        urls.append(link)
                else:
                    urls.append(link)

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls


def generate_competitive_queries(product_idea: str) -> List[str]:
    """
    Generate competitive analysis search queries for a product idea.

    Args:
        product_idea: The product idea to research

    Returns:
        List of search query strings
    """
    queries = [
        f"best {product_idea}",
        f"{product_idea} tools",
        f"top {product_idea} software",
        f"{product_idea} alternatives",
        f"{product_idea} comparison",
        f"{product_idea} reviews",
        f"leading {product_idea} platforms",
    ]
    return queries
