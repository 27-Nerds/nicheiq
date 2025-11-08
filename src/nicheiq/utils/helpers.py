"""
Helper utilities for NicheIQ.
"""

import json
import re
from typing import List, Optional

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ..config.settings import settings


class ValidationResult(BaseModel):
    """Single validation result for a thread."""

    model_config = ConfigDict(extra='forbid')

    is_relevant: bool = Field(..., description="Whether the thread is relevant to the niche")
    confidence: float = Field(..., description="Confidence score 0-1")
    reason: str = Field(..., description="Brief explanation of the decision")


class BatchValidationResponse(BaseModel):
    """Batch validation response containing multiple results."""

    model_config = ConfigDict(extra='forbid')

    results: List[ValidationResult] = Field(..., description="List of validation results, one per thread")


class QueryGenerator:
    """LLM-based search query generator for finding niche pain points."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.7,
            api_key=settings.openai_api_key,
        )

    def generate_queries(self, niche_description: str, num_queries: int) -> List[dict]:
        """
        Generate strategic search queries for a niche using LLM.

        Args:
            niche_description: Description of the niche to generate queries for
            num_queries: Number of queries to generate

        Returns:
            List of query dictionaries with 'query', 'type', and 'platform' keys
        """
        prompt = f"""You are a Reddit/Twitter search query specialist. Your job is to generate DISCOVERY queries that find threads where users NATURALLY EXPRESS their unique problems.

Niche: {niche_description}

Generate {num_queries} search queries for DISCOVERING pain points, not searching FOR known problems.

**CRITICAL PRINCIPLE: DISCOVERY not PRE-LOADED PROBLEMS**

❌ WRONG (Too specific, presupposes the problem):
- "pack fragile items for international move" (why presuppose fragile items?)
- "sell furniture before moving abroad" (why presuppose selling furniture?)
- "transfer bank accounts between countries" (too narrow, misses broader finance issues)

✅ RIGHT (Broad discovery that lets users express THEIR problems):
- "moving abroad problems" (lets users tell you what's hard)
- "international relocation frustrating" (surfaces emotional struggle threads)
- "coordinate international move" (broad action, users share specific struggles)

**Query Types - DISCOVERY FOCUSED:**

1. **Problem Discovery Queries (30%)** - Broad niche + emotion/struggle keywords
   - "[niche] problems"
   - "[niche] frustrating"
   - "struggling with [niche]"
   - "hate [niche]"
   - "[niche] difficult"
   - "[niche] annoying"
   - "tired of [niche]"

   Examples: "freelancing problems", "remote work frustrating", "struggling with meal planning"

2. **Short Action Phrases (25%)** - ONLY 2-3 words, NO specific sub-tasks
   - "[action verb] [broad category]" (e.g., "track expenses" NOT "track business receipts for taxes")
   - Keep extremely short and general
   - Let threads reveal specific struggles

   Examples: "manage clients", "schedule meetings", "track leads", "follow up", "coordinate team"

3. **Open Discovery Questions (20%)** - Let users share methods/tools/struggles
   - "how do you [broad task]"
   - "what's the best way to [broad goal]"
   - "any recommendations for [niche]"
   - "how can I [broad activity]"

   Examples: "how do you manage projects", "what's the best way to find clients", "any recommendations for time tracking"

4. **Tool/Solution Discovery (15%)** - Find what tools exist and gaps
   - "tools for [niche]"
   - "[niche] alternatives"
   - "[niche] recommendations"
   - "apps for [broad activity]"
   - "software for [niche]"
   - "[niche] vs [competitor category]"

   Examples: "tools for content creators", "CRM alternatives", "project management recommendations"

5. **Evidence of Active Struggle (10%)** - Emotional indicators of pain
   - "can't figure out [broad area]"
   - "frustrated with [niche]"
   - "giving up on [broad task]"
   - "[niche] keeps failing"

   Examples: "can't figure out invoicing", "frustrated with freelance platforms", "giving up on content scheduling"

**Construction Guidelines:**

1. **Keep queries SHORT** (2-5 words ideal, max 7 words)
2. **Use broad niche terms**, not specific sub-problems
3. **NO detailed scenarios** - "moving abroad" NOT "moving abroad as a digital nomad with pets"
4. **NO solution assumptions** - let users tell you what they need
5. **Mix platforms** - some queries work better on Reddit, some on Twitter
6. **Include emotion words** - "frustrated", "struggling", "hate", "difficult", "tired of"

**Platform Selection:**
- Reddit: Better for detailed problems, recommendations, "how do you", tool discussions
- Twitter: Better for quick frustrations, "any tool for", real-time struggles
- Both: Broad discovery queries work everywhere

Return ONLY a valid JSON array with this structure:
[
  {{"query": "the search query text", "type": "discovery|action|question|tool|struggle", "platform": "reddit|twitter|both"}},
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
    def extract_results_from_serper(search_results: dict, domain: str) -> List['SearchResultItem']:
        """
        Extract search results with metadata for a specific domain from SerperDevTool results.
        Returns full result objects (URL + title + snippet) for relevance validation.

        Args:
            search_results: Search results dict from SerperDevTool
            domain: Domain to filter for (e.g., 'reddit.com', 'twitter.com')

        Returns:
            List of SearchResultItem objects with url, title, snippet
        """
        from ..models.research_state import SearchResultItem

        results = []

        # Extract from organic results
        organic_results = search_results.get('organic', [])
        for result in organic_results:
            link = result.get('link', '')
            title = result.get('title', '')
            snippet = result.get('snippet', '')

            if link and domain in link:
                # For Reddit, only include submission URLs (not subreddit pages)
                if 'reddit.com' in domain:
                    # Reddit submission URLs contain '/comments/'
                    if '/comments/' in link:
                        results.append(SearchResultItem(
                            url=link,
                            title=title,
                            snippet=snippet
                        ))
                # For Twitter/X, only include tweet status URLs (not profiles or share links)
                elif 'twitter.com' in domain or 'x.com' in domain:
                    # Twitter status URLs contain '/status/'
                    if '/status/' in link:
                        results.append(SearchResultItem(
                            url=link,
                            title=title,
                            snippet=snippet
                        ))
                else:
                    results.append(SearchResultItem(
                        url=link,
                        title=title,
                        snippet=snippet
                    ))

        # Deduplicate by URL while preserving order
        seen = set()
        unique_results = []
        for result in results:
            if result.url not in seen:
                seen.add(result.url)
                unique_results.append(result)

        return unique_results

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


class ThreadRelevanceValidator:
    """
    Validates thread relevance to niche using configured LLM.
    Uses minimal tokens by only analyzing title + snippet.

    Model can be configured via THREAD_VALIDATION_LLM in .env
    (defaults to gpt-4o-mini for cost efficiency).
    """

    def __init__(self):
        # Use configured model for validation (default: gpt-4o-mini)
        self.llm = ChatOpenAI(
            model=settings.thread_validation_llm,
            temperature=0,  # Deterministic for consistency
            api_key=settings.openai_api_key,
        )

    def validate_batch(
        self,
        niche_description: str,
        search_results: List['SearchResultItem'],
        batch_size: int = 10
    ) -> List[tuple['SearchResultItem', bool]]:
        """
        Validate multiple search results in batches.
        Returns list of (SearchResultItem, is_relevant) tuples.

        Args:
            niche_description: Description of the niche to validate against
            search_results: List of SearchResultItem objects to validate
            batch_size: Number of results to validate per API call

        Returns:
            List of (SearchResultItem, is_relevant) tuples
        """
        from ..models.research_state import ThreadRelevanceValidation

        results = []

        for i in range(0, len(search_results), batch_size):
            batch = search_results[i:i + batch_size]

            # Format batch for prompt (title + snippet only)
            threads_text = "\n\n".join([
                f"[{idx}] Title: {result.title}\nSnippet: {result.snippet}"
                for idx, result in enumerate(batch)
            ])

            prompt = f"""You are a relevance classifier. Determine if each thread is DIRECTLY relevant to this niche:

Niche: {niche_description}

Threads to evaluate:
{threads_text}

A thread is RELEVANT if it:
- Discusses problems, pain points, or needs in this niche
- Contains user experiences or frustrations related to the niche
- Asks for solutions, tools, or recommendations for niche-related problems

A thread is NOT RELEVANT if it:
- Only tangentially mentions the niche (keyword match but wrong context)
- Discusses unrelated topics that happened to use similar words
- Is spam, promotional content, or off-topic

Evaluate ALL {len(batch)} threads and return a JSON object with a 'results' array containing {len(batch)} validation objects.

Each validation object must have:
- is_relevant: true/false
- confidence: 0.0-1.0
- reason: "brief explanation"

Be strict - only mark as relevant if the thread clearly discusses niche-related problems or needs."""

            try:
                # Use structured output with Pydantic model for consistent parsing
                structured_llm = self.llm.with_structured_output(BatchValidationResponse)
                response = structured_llm.invoke(prompt)

                # Match results with original SearchResultItems
                for idx, validation_result in enumerate(response.results):
                    if idx < len(batch):
                        is_relevant = validation_result.is_relevant
                        results.append((batch[idx], is_relevant))

                        # Log validation decision at DEBUG level
                        logger.debug(
                            f"Validation [{idx}]: {batch[idx].title[:50]}... -> "
                            f"{'RELEVANT' if is_relevant else 'FILTERED'} "
                            f"(confidence: {validation_result.confidence:.2f}, "
                            f"reason: {validation_result.reason})"
                        )

            except Exception as e:
                logger.warning(f"Validation batch failed: {e} - keeping all {len(batch)} results")
                # On error, keep all results (fail-open)
                results.extend([(result, True) for result in batch])

        return results


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
