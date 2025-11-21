"""
Helper utilities for NicheIQ.
"""

import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ..config.settings import settings

if TYPE_CHECKING:
    from ..models.research_state import NicheContext
    from ..models.solution_idea import SolutionIdea
    from ..models.pain_point import PainPoint, PainPointAnalysisResult
    from ..models.competitor import CompetitiveAnalysisResult
    from ..models.seo_strategy import ExpandedKeywordList


class ValidationResult(BaseModel):
    """Single validation result for a thread."""

    model_config = ConfigDict(extra='forbid')

    thread_index: int = Field(..., description="Index of the thread being validated (0-based)")
    is_relevant: bool = Field(..., description="Whether the thread is relevant to the niche")
    confidence: float = Field(..., description="Confidence score 0-1")
    reason: str = Field(..., description="Brief explanation of the decision")


class BatchValidationResponse(BaseModel):
    """Batch validation response containing multiple results."""

    model_config = ConfigDict(extra='forbid')

    results: List[ValidationResult] = Field(..., description="List of validation results, one per thread")


def _extract_json_array_from_text(text: str) -> Optional[list]:
    """
    Extract first complete JSON array from text (shared utility).

    Performance optimization: Try direct parsing first, then regex, then bracket matching.

    Args:
        text: Raw text containing JSON array

    Returns:
        Parsed JSON array or None if extraction fails
    """
    # Fast path: Try direct JSON parse if text is clean
    text_stripped = text.strip()
    if text_stripped.startswith('['):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass  # Fall through to extraction methods

    # Medium path: Extract JSON with regex (handles common cases like "Here's the list: [...]")
    json_match = re.search(r'\[.*\]', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass  # Fall through to bracket matching

    # Slow path: Manual bracket matching for complex cases (brackets in strings, etc.)
    start_idx = text.find('[')
    if start_idx == -1:
        return None

    bracket_count = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start_idx:], start=start_idx):
        # Handle string literals (ignore brackets inside strings)
        if char == '"' and not escape_next:
            in_string = not in_string
        elif char == '\\' and in_string:
            escape_next = not escape_next
            continue

        if not in_string:
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    try:
                        return json.loads(text[start_idx:i+1])
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON parse failed at bracket close: {e}")
                        return None

        escape_next = False

    logger.warning("No matching closing bracket found")
    return None


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

    def _extract_json_array(self, text: str) -> Optional[list]:
        """Extract first complete JSON array from text."""
        return _extract_json_array_from_text(text)

    def generate_queries(
        self,
        niche_description: str,
        niche_context: Optional["NicheContext"] = None,
        num_queries: int = 20
    ) -> List[dict]:
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

        prompt = f"""You are an expert search query strategist specializing in market research discovery. Your goal is to generate semantically valid search queries that help discover genuine user pain points in Reddit and Twitter discussions.

{context_section}

---

**TASK: Generate {num_queries} discovery-focused search queries**

Follow this process in order:

## STEP 1: ANALYZE NICHE CHARACTERISTICS

Before generating queries, analyze the niche context to understand:

**Market Type:**
- Is this B2C (consumer-facing), B2B (business-facing), or hybrid?
- Evidence: Look for words like "business", "enterprise", "teams", "professional" vs "personal", "home", "individual", "consumer"

**Product/Service Nature:**
- Physical product, digital service, software/SaaS, platform, or information service?
- Does software/apps typically exist in this space?
- Evidence: Context clues about tangible vs digital offerings, common tools in this category

**Price Positioning:**
- Budget/value-focused, mid-range, premium, or luxury?
- Is authenticity/counterfeiting a real concern? (Only for: luxury fashion, designer items, high-value collectibles, supplements/health products)
- Evidence: Market segment demographics, keywords like "affordable", "premium", "luxury", "high-end"

**Decision Journey:**
- Quick impulse purchase or extended research/comparison?
- Individual decision or committee/team decision?
- Evidence: Product complexity, price point, market type

## STEP 2: APPLY SEMANTIC VALIDATION RULES

**RULE 1: No "apps for X" unless software naturally exists in that space**
- Valid: "apps for meal planning", "apps for habit tracking", "apps for project management" (software ecosystems exist)
- Invalid: "apps for home appliances", "apps for furniture", "apps for gardening tools" (physical products without app ecosystems)
- Test: Would typical users actually search for apps in this category?

**RULE 2: No "enterprise X" unless B2B variant exists**
- Valid: "enterprise project management", "enterprise CRM", "enterprise accounting software" (B2B products)
- Invalid: "enterprise home appliances", "enterprise skincare", "enterprise cooking" (purely consumer products)
- Test: Do businesses actually purchase this as a company expense?

**RULE 3: No "counterfeit X" unless authenticity is a documented concern**
- Valid: "counterfeit luxury handbags", "counterfeit designer sneakers", "counterfeit supplements", "counterfeit electronics"
- Invalid: "counterfeit home appliances", "counterfeit gardening tools", "counterfeit stationery" (not real market concerns)
- Test: Is there a significant fake market for this product category?

**RULE 4: No "X for teams" unless collaboration is natural**
- Valid: "project management for teams", "design tools for teams", "communication software for teams" (collaborative work)
- Invalid: "home appliances for teams", "skincare for teams", "meal planning for teams" (individual use products)
- Test: Do multiple people actually use this together simultaneously?

**RULE 5: Use market segments as query modifiers**
- Extract key characteristics from segments: demographics (age, role), constraints (budget, space), priorities (eco-friendly, efficiency)
- Examples:
  - "First-time homebuyers aged 25-35 seeking affordable appliances" → "affordable appliances first home", "budget appliances young homeowners"
  - "Eco-conscious consumers prioritizing energy-efficient products" → "energy efficient appliances reviews", "sustainable appliances worth it"
  - "Urban apartment dwellers needing compact solutions" → "compact appliances small apartment", "space-saving appliances urban"

**RULE 6: Respect industry boundaries**
- Do NOT generate queries for adjacent markets that fall outside the stated boundaries
- Example: If boundaries say "excludes furniture and decor", avoid "furniture for small spaces"

## STEP 3: GENERATE QUERIES WITH DISCOVERY FOCUS

Use these query patterns, adapted to your Step 1 analysis:

**1. Problem Discovery (30% of queries)** - Broad niche + emotion/struggle
- "[niche] problems"
- "[niche] frustrating"
- "struggling with [niche]"
- "[niche] difficult"
- "why is [niche] so hard"
- "hate [niche]"
- "[niche] annoying"

Examples: "home appliances problems", "appliance shopping frustrating", "choosing appliances difficult"

**2. Segment-Specific Discovery (25% of queries)** - Use market segment characteristics as modifiers
- "[segment constraint/priority] + [niche category]"
- Extract from segments: budget level, space constraints, demographic, priorities, pain points
- Keep queries 3-5 words, focus on discoverable user language

Examples:
- From "budget-conscious first-time homebuyers" → "affordable appliances first home", "cheap appliances quality"
- From "eco-conscious consumers" → "energy efficient appliances", "sustainable appliances reviews"
- From "urban apartment dwellers" → "compact appliances apartment", "space-saving appliances"

**3. Open Discovery Questions (20% of queries)** - Let users share methods/struggles
- "how do you [broad task related to niche]"
- "what's the best way to [niche goal]"
- "anyone else [struggle verb] with [niche]"
- "how can I [broad activity]"

Examples: "how do you choose appliances", "what's the best way to compare appliances", "anyone else confused by appliance ratings"

**4. Tool/Solution Discovery (15% of queries)** - ONLY if semantically valid per RULE 1
- "tools for [niche]" (only if tools/software actually exist in this space)
- "[niche] alternatives"
- "best [niche category]"
- "recommended [niche]"
- Skip "apps for X" unless Step 1 analysis confirms software ecosystem exists

Examples:
- For software niches: "tools for project management", "apps for habit tracking"
- For physical product niches: "best appliance brands", "appliance recommendations" (NOT "apps for appliances")

**5. Evidence of Active Struggle (10% of queries)** - Emotional indicators
- "frustrated with [niche]"
- "giving up on [niche]"
- "[niche] not working"
- "terrible experience [niche]"
- "can't figure out [niche]"

Examples: "frustrated with appliance shopping", "giving up on finding good appliances", "terrible experience buying appliances"

## STEP 4: PLATFORM SELECTION

**Reddit**: Best for long-form discussions, detailed experiences, niche communities, "how do you" questions, tool discussions
**Twitter**: Best for real-time reactions, trending topics, quick complaints, emotional frustrations
**Both**: General discovery queries that work on both platforms

## STEP 5: OUTPUT FORMAT

Return ONLY a valid JSON array. No preamble, no explanation, just the array:

[
  {{
    "query": "the exact search query text",
    "type": "problem|segment|question|tool|struggle",
    "platform": "reddit|twitter|both",
    "rationale": "brief 1-sentence explanation of why this query is semantically valid for this niche"
  }},
  ...
]

**Quality Checklist (Self-Validate Before Outputting):**
- [ ] Does this query make semantic sense for the analyzed niche type?
- [ ] Would real users actually search/discuss this?
- [ ] Does it respect industry boundaries from context?
- [ ] Does it leverage market segment insights where relevant?
- [ ] Is it broad enough to discover problems (not presuppose specific solutions)?
- [ ] Does it pass all semantic validation rules (Rules 1-6)?

Generate {num_queries} queries now, following Steps 1-5 in order.
"""

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

    def _extract_json_array(self, text: str) -> Optional[list]:
        """Extract first complete JSON array from text."""
        return _extract_json_array_from_text(text)

    def generate_competitor_queries(
        self,
        solution_name: str,
        project_type: str,
        niche_context: Optional["NicheContext"] = None,
        pain_points_addressed: Optional[List[str]] = None,
        num_queries: int = 8
    ) -> List[dict]:
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

        prompt = f"""You are an expert competitive intelligence researcher specializing in discovering and validating market competitors. Your goal is to generate semantically valid search queries that discover actual competitors for a specific solution.

{context_section}

---

**TASK: Generate {num_queries} strategic competitor search queries**

Follow this process in order:

## STEP 1: ANALYZE SOLUTION & NICHE CHARACTERISTICS

Before generating queries, analyze the solution context to understand:

**Solution Type Analysis:**
- Project Type: {sanitized_project_type}
- What category of product is this?
  - SaaS → software/tools/platforms competitors
  - Directory → curated lists/catalogs/directories competitors
  - Aggregator → data platforms/comparison sites/aggregators competitors
  - Comparison-tool → comparison engines/review platforms competitors
  - Marketplace → platforms/exchanges/marketplaces competitors

**Market Type:**
- Is this B2C (consumer-facing), B2B (business-facing), or hybrid?
- Evidence: Look for "business", "teams", "enterprise" vs "personal", "home", "individual"

**Product Nature:**
- Physical products, digital services, software, platform, or information service?
- Does the niche have established digital competitors?
- Evidence: Industry boundaries, niche description

**Competitor Landscape:**
- Established players likely? (mature market) vs Fragmented/emerging? (new market)
- Evidence: Pain points mention existing tools/platforms?

## STEP 2: APPLY SEMANTIC VALIDATION RULES

**RULE 1: Match competitor category to solution type**
- SaaS → Search: "software", "tools", "platforms", "apps"
- Directory → Search: "directories", "catalogs", "curated lists", "guides"
- Aggregator → Search: "comparison sites", "data aggregators", "vs platforms"
- Comparison-tool → Search: "comparison engines", "review sites", "ranking platforms"
- Marketplace → Search: "marketplaces", "platforms", "exchanges"

**RULE 2: Adapt search terms to product nature**
- Physical products → "sites", "directories", "guides", "reviews", "comparison sites"
- Digital/SaaS → "software", "tools", "platforms", "apps", "solutions"
- Services → "platforms", "marketplaces", "networks", "directories"
- Information → "guides", "databases", "resources", "directories"

**RULE 3: Use market segments for targeted competitor searches**
- Extract key characteristics from market segments (if provided)
- Examples:
  - "First-time homebuyers" → search "[category] for first-time buyers"
  - "Budget-conscious families" → search "affordable [category]", "cheap [category] alternatives"
  - "Remote teams" → search "[category] for remote teams", "distributed team [category]"

**RULE 4: Focus on competitor discovery, not solution promotion**
- Search for what EXISTS in the market (competitors), not marketing terms
- Use established category names, not branded terms
- Examples:
  - Good: "project management software", "expense tracking apps"
  - Bad: "[SolutionName] competitors" (unless SolutionName is already established)

**RULE 5: Use pain points to find problem-specific competitors**
- If pain points mention existing tools/brands, search for those
- Search for solutions addressing the same pain points
- Examples:
  - Pain point: "Hard to find reliable contractors" → "contractor directories", "verified contractor platforms"
  - Pain point: "Comparing appliances is confusing" → "appliance comparison sites", "appliance review platforms"

**RULE 6: Respect industry boundaries**
- Only search within the defined scope from industry_boundaries
- Avoid adjacent markets explicitly excluded

## STEP 3: GENERATE QUERIES (5 Types)

**1. Direct Competitor Category (30% of queries)** - Core competitor type
- "[solution category] [type]" where type matches project_type
- Examples:
  - SaaS: "project management software", "expense tracking tools"
  - Directory: "contractor directories", "restaurant guides"
  - Aggregator: "flight comparison sites", "insurance aggregators"
  - Marketplace: "freelance marketplaces", "rental platforms"

**2. Alternative/Comparison Searches (25% of queries)** - What users search
- "best [category]"
- "[category] alternatives"
- "[category] comparison"
- "top [category] platforms/tools/sites"

**3. Segment-Specific Competitors (20% of queries)** - Use market segment characteristics
- "[category] for [segment characteristic]"
- Extract from market segments: demographics, constraints, priorities
- Examples:
  - "project management for small teams"
  - "affordable appliance directories"
  - "contractor platforms for homeowners"

**4. Problem-Specific Solutions (15% of queries)** - Pain point targeting
- "solve [pain point] tools/platforms"
- "[pain point] solutions"
- Examples:
  - "reliable contractor platforms"
  - "verified service provider directories"
  - "compare [product category] easily"

**5. Established Player Searches (10% of queries)** - Known competitors
- Only if you can infer likely established players from niche/category
- "[established player] vs"
- "[established player] alternatives"
- "better than [established player]"
- Examples:
  - "Upwork alternatives" (if marketplace for freelancers)
  - "Zillow competitors" (if real estate directory)

## STEP 4: OUTPUT FORMAT

Return ONLY a valid JSON array. No preamble, no explanation, just the array:

[
  {{
    "query": "the exact search query text",
    "type": "category|alternative|segment|problem|established",
    "rationale": "1-sentence explanation of why this query finds relevant competitors for this solution type"
  }},
  ...
]

**Quality Checklist (Self-Validate Before Outputting):**
- [ ] Does this query match the project_type? (e.g., "directories" for directory solutions)
- [ ] Would this query actually find competitors, not just general info?
- [ ] Does it respect industry boundaries?
- [ ] Does it leverage market segment insights where available?
- [ ] Is it specific enough to find actual products/platforms?
- [ ] Does it pass semantic validation rules (Rules 1-6)?

Generate {num_queries} queries now, following Steps 1-4 in order.
"""

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
                import re
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


class KeywordSeedGenerator:
    """
    Context-aware seed keyword generator for SEO strategy.

    Generates 40-50 strategically selected seed keywords using chain-of-thought
    reasoning and semantic validation. Follows proven patterns from QueryGenerator
    and CompetitorQueryGenerator with NicheContext integration.

    Output Mix:
    - 70% Broad Seeds (28-35 keywords, 1-2 words): Core category terms
    - 30% Targeted Keywords (12-15 keywords, 3-5 words): Long-tail combinations

    Semantic Validation Rules:
    1. No "apps for X" unless software ecosystem exists
    2. No "enterprise X" unless B2B variant exists
    3. Extract segment characteristics for seed modifiers
    4. Respect industry boundaries (exclusions)
    5. Geographic context for local services
    6. Solution type alignment (directory/SaaS/aggregator terminology)
    7. Avoid invented/novel solution names as keywords
    """

    def __init__(self):
        """Initialize the keyword seed generator."""
        self.llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.5,  # Balanced creativity for keyword diversity
            api_key=settings.openai_api_key,
            timeout=120,
        )

    def generate_seeds(
        self,
        solution: "SolutionIdea",
        niche_context: Optional["NicheContext"] = None,
        pain_points: Optional["PainPointAnalysisResult"] = None,
        competitive_analysis: Optional["CompetitiveAnalysisResult"] = None,
        num_broad_seeds: int = 30,
        num_targeted_seeds: int = 15
    ) -> Optional["ExpandedKeywordList"]:
        """
        Generate context-aware seed keywords with semantic validation.

        Args:
            solution: Selected solution with full details
            niche_context: Optional NicheContext with market_segments and industry_boundaries
            pain_points: Optional pain point analysis for keyword grounding
            competitive_analysis: Optional competitive context
            num_broad_seeds: Target count for broad seeds (1-2 words)
            num_targeted_seeds: Target count for targeted keywords (3-5 words)

        Returns:
            ExpandedKeywordList with keywords, topic_clusters, and expansion_rationale
        """
        try:
            # Build context inputs
            niche_description = niche_context.niche_description if niche_context else "Not provided"
            market_segments = "\n".join([f"- {seg}" for seg in niche_context.market_segments]) if niche_context else "Not provided"
            industry_boundaries = niche_context.industry_boundaries if niche_context else "Not provided"

            # Extract solution details
            solution_name = self._sanitize_for_prompt(solution.solution_name)
            solution_type = solution.project_type or "unknown"
            value_proposition = self._sanitize_for_prompt(solution.value_proposition)
            core_features = ", ".join(solution.core_features[:5]) if solution.core_features else "Not provided"
            target_personas = ", ".join(solution.target_personas[:3]) if solution.target_personas else "Not provided"
            pain_points_addressed = ", ".join(solution.pain_points_addressed[:5]) if solution.pain_points_addressed else "Not provided"

            # Extract competitive context
            competitors = "Not provided"
            if competitive_analysis and competitive_analysis.solution_landscapes:
                # Find matching landscape for this solution
                matching_landscape = next(
                    (l for l in competitive_analysis.solution_landscapes if l.solution_name == solution.solution_name),
                    None
                )
                if matching_landscape and matching_landscape.competitors:
                    competitor_names = [c.name for c in matching_landscape.competitors[:8]]
                    competitors = ", ".join(competitor_names)

            # Build the chain-of-thought prompt
            prompt = f"""You are an SEO keyword strategist generating seed keywords for expansion.

NICHE CONTEXT:
**Niche Description:** {niche_description}

**Target Market Segments:**
{market_segments}

**Industry Boundaries:** {industry_boundaries}

SOLUTION DETAILS:
**Solution Name:** {solution_name}
**Solution Type:** {solution_type}
**Value Proposition:** {value_proposition}
**Core Features:** {core_features}
**Target Personas:** {target_personas}
**Pain Points Addressed:** {pain_points_addressed}
**Known Competitors:** {competitors}

═══════════════════════════════════════════════════════════════════════════

TASK: Generate {num_broad_seeds + num_targeted_seeds} strategically selected seed keywords for SEO expansion.

**REQUIRED OUTPUT MIX:**
- {num_broad_seeds} Broad Seeds (1-2 words): Core category terms with high search volume potential
- {num_targeted_seeds} Targeted Keywords (3-5 words): Long-tail combinations addressing specific user needs

═══════════════════════════════════════════════════════════════════════════

**CHAIN-OF-THOUGHT PROCESS (FOLLOW IN ORDER):**

**STEP 1: ANALYZE NICHE CHARACTERISTICS**

Before generating keywords, analyze:
1. **Market Type:** B2B vs B2C? (evidence from market segments, personas)
2. **Product Nature:** Physical products, digital service, SaaS platform, marketplace? (evidence from solution type, features)
3. **Geographic Scope:** Local, national, international? (evidence from personas, niche description)
4. **Price Positioning:** Budget, mid-tier, premium? (evidence from market segments, value proposition)
5. **User Intent:** Informational, transactional, navigational? (evidence from pain points)

Write 2-3 sentences summarizing your analysis.

**STEP 2: EXTRACT MARKET SEGMENT CHARACTERISTICS**

From the market_segments above, extract:
1. **Demographics:** Age groups, experience levels, roles (e.g., "beginner", "professional", "enterprise")
2. **Constraints:** Budget limitations, space constraints, time pressures (e.g., "affordable", "compact", "fast")
3. **Priorities:** Values and preferences (e.g., "eco-friendly", "energy efficient", "convenient", "quality")
4. **Context:** Usage scenarios (e.g., "first home", "small business", "remote teams")

List 5-8 segment characteristics you'll use as keyword modifiers.

**STEP 3: APPLY SEMANTIC VALIDATION RULES**

Before generating keywords, review these rules:

**RULE 1: No "apps for X" unless software ecosystem exists**
- ✓ Valid: "apps for meal planning", "apps for project management" (software categories)
- ✗ Invalid: "apps for home appliances", "apps for furniture" (physical products)
- Check: Does the niche involve software/digital tools? If not, avoid "app/apps" keywords.

**RULE 2: No "enterprise X" unless B2B variant exists**
- ✓ Valid: "enterprise project management", "enterprise CRM" (B2B software markets)
- ✗ Invalid: "enterprise home appliances", "enterprise consumer products" (B2C markets)
- Check: Do market_segments mention businesses/teams? If not, use "consumer", "home", "personal".

**RULE 3: Extract segment characteristics for seed modifiers**
- Use characteristics from STEP 2 as keyword modifiers
- Examples: "affordable [category]", "compact [category]", "eco-friendly [category]"
- This grounds keywords in actual user needs (not generic guesses)

**RULE 4: Respect industry boundaries**
- Review the "Industry Boundaries" section above
- If it says "OUT OF SCOPE: furniture, decor" → DO NOT generate keywords for those categories
- Only generate keywords within the "IN SCOPE" boundaries

**RULE 5: Geographic context for local services**
- If niche is location-specific (relocation, local services, regional markets):
  * Include city/region names in targeted keywords
  * Add "international", "global", "expat" for cross-border niches
- If niche is global/online, skip geographic modifiers

**RULE 6: Solution type alignment**
- Match keyword terminology to solution_type:
  * **directory** → use "directory", "listing", "catalog", "database", "guide"
  * **saas** → use "software", "tool", "platform", "app", "system"
  * **aggregator** → use "comparison", "aggregator", "search engine", "finder"
  * **marketplace** → use "marketplace", "platform", "exchange", "network"
  * **comparison-tool** → use "comparison", "vs", "alternative", "review"

**RULE 7: Avoid invented/novel solution names as keywords**
- The solution_name field may contain branded terms, portmanteaus, or novel compound words
- These invented brands have ZERO search volume until established through marketing
- **Your task:** Extract the CATEGORY/PROBLEM the solution addresses, NOT the brand name itself

**How to identify invented brands:**
- Portmanteaus: "ExpatEase", "RefactorHub", "NicheSignal" (blended words)
- Compound words with mid-word capitals: "TravelBuddy", "CodeMentor"
- Unfamiliar terms not recognized as existing products/services
- Terms that appear to be marketing names vs descriptive categories

**What to do:**
1. Analyze solution_name to understand the UNDERLYING CATEGORY
2. Extract category keywords from value_proposition, core_features, pain_points_addressed
3. Generate keywords for the category/problem space, NOT the brand

**Examples:**
- ✅ "ExpatEase" → Extract "expat relocation", "expat services", "international moving" (NOT "ExpatEase")
- ✅ "NicheSignal Atlas" → Extract "niche research", "market research", "business ideas" (NOT "NicheSignal")
- ✅ "RefactorHub" → Extract "code refactoring", "developer tools", "refactoring software" (NOT "RefactorHub")
- ✅ "HealthTrack Pro" → Extract "health tracking", "fitness tracker", "health app" (NOT "HealthTrack")

**Exception:** Only use solution_name as a keyword if:
- It matches an existing competitor name in the competitors list
- It's a well-established product with known search volume
- The prompt explicitly instructs you to include it

Write 1 sentence confirming you'll extract categories instead of using invented brand names.

**RULE 8: Domain-lock ambiguous terms with mandatory qualifiers**

Polysemous terms (words with multiple meanings) MUST include domain-qualifying modifiers:

**High-Risk Ambiguous Terms:**
- "validate" → "business validation" or "idea validation" (NOT bare "validate")
- "test" → "market testing" or "user testing" (NOT bare "test")
- "track" → "customer tracking" or "analytics tracking" (NOT bare "track")
- "monitor" → "performance monitoring" or "uptime monitoring" (NOT bare "monitor")
- "discover" → "market discovery" or "pain point discovery" (NOT bare "discover")
- "manage" → "project management" or "team management" (NOT bare "manage")
- "optimize" → "conversion optimization" or "SEO optimization" (NOT bare "optimize")

**Domain-locking examples:**
✅ "Struggle to Validate Ideas" → "business idea validation", "startup validation tools"
✅ "Track Customer Behavior" → "customer behavior tracking", "user analytics tracking"
❌ "Struggle to Validate Ideas" → "validate", "validation" (expands to code validation)
❌ "Track Behavior" → "track", "tracking" (expands to GPS tracking)

**Self-Check:** If keyword is 1-2 words with action verb → Add domain qualifier

Write 1 sentence confirming you'll add domain qualifiers to ambiguous terms.

Write 1-2 sentences confirming you've reviewed all 8 rules.

**STEP 4: PLAN TOPIC CLUSTERS**

Create 5-8 thematic topic clusters to organize keywords:
1. Core product/service cluster
2. Problem/need cluster (from pain_points_addressed)
3. Segment-specific clusters (1-2 clusters per major segment)
4. Geographic cluster (if applicable)
5. Competitive cluster (alternatives, comparisons)

For each cluster, define:
- **name:** Short cluster name (e.g., "Affordable Solutions", "International Shipping")
- **description:** What keywords belong here
- **strategic_importance:** 1-5 (1=critical, 5=nice-to-have)

List your 5-8 planned clusters.

**STEP 5: GENERATE KEYWORD MIX**

Now generate keywords following this structure:

**5.1 Broad Seeds ({num_broad_seeds} keywords, 1-2 words each):**

Generate by extracting:
- **Type 1:** Core nouns from niche_description, solution_name (5-8 keywords)
  * Extract NOUNS only (not full phrases)
  * Example: "appliances", "tools", "software", "directory"

- **Type 2:** Problem/need terms from pain_points_addressed (5-8 keywords)
  * Extract core PROBLEMS with domain-qualifying context (apply RULE 8)
  * Transform into user search queries (what would they type on Google?)

  **Correct extraction patterns:**
  ✅ "Struggle to Validate Ideas" → "business idea validation", "startup validation tools"
  ✅ "Difficulty Finding Niches" → "niche market research", "profitable niche finder"
  ✅ "Can't Track ROI" → "marketing ROI tracking", "campaign analytics tools"

  **Incorrect patterns (avoid bare ambiguous terms):**
  ❌ "Struggle to Validate Ideas" → "validate", "validation"
  ❌ "Difficulty Testing Markets" → "test", "testing"
  ❌ "Can't Track Metrics" → "track", "tracking"

  **Validation:** Would this keyword return business tools (correct) or code libraries (incorrect)?

- **Type 3:** Category/industry terms (5-8 keywords)
  * Broad category descriptors
  * Example: "home", "business", "enterprise", "consumer"

- **Type 4:** Action/intent terms (5-8 keywords)
  * User intent verbs + nouns
  * Example: "find", "compare", "choose", "select", "buy"

- **Type 5:** Segment modifiers from STEP 2 (5-8 keywords)
  * Single-word characteristics
  * Example: "affordable", "compact", "efficient", "professional"

**5.2 Targeted Keywords ({num_targeted_seeds} keywords, 3-5 words each):**

Generate by combining:
- Segment modifier + category + intent (e.g., "affordable home appliances comparison")
- Problem + solution type (e.g., "energy efficient appliance reviews")
- Geographic + category (if applicable: "international relocation services directory")
- Competitor alternative (e.g., "alternative to [major competitor]")

**CRITICAL REQUIREMENTS:**

1. **Diversity:** Cover ALL personas, pain points, and market segments
2. **No repetition:** Each keyword must be unique
3. **Rationale:** Provide brief rationale for each keyword (why it's strategically valuable)
4. **Cluster assignment:** Assign each keyword to one of your topic clusters from STEP 4
5. **Priority scoring:** Assign priority 1-5 (1=critical/highest, 5=nice-to-have/lowest) based on:
   - Priority 1-2: Core category terms, high-volume problems, critical segment keywords
   - Priority 3-4: Segment-specific, geographic, competitive alternatives
   - Priority 5: Nice-to-have variations, low-priority modifiers
6. **Semantic validation:** Ensure all keywords pass the 7 validation rules from STEP 3

═══════════════════════════════════════════════════════════════════════════

**OUTPUT FORMAT:**

Return a JSON object with this exact structure:

{{
  "keywords": [
    {{
      "keyword": "affordable appliances",
      "rationale": "Targets budget-conscious segment (first-time homebuyers)",
      "cluster": "Affordable Solutions",
      "priority": 1
    }},
    // ... {num_broad_seeds + num_targeted_seeds} total keywords
  ],
  "topic_clusters": [
    {{
      "name": "Affordable Solutions",
      "description": "Keywords targeting budget-conscious consumers",
      "strategic_importance": 1
    }},
    // ... 5-8 total clusters
  ],
  "expansion_rationale": "2-3 sentence summary of overall keyword strategy and coverage"
}}

Generate the keywords now, following STEP 1-5 process."""

            logger.info(f"Generating {num_broad_seeds + num_targeted_seeds} seed keywords for: {solution_name}")

            # Import here to avoid circular dependency
            from ..models.seo_strategy import ExpandedKeywordList

            # Use structured output for type-safe Pydantic response
            structured_llm = self.llm.with_structured_output(ExpandedKeywordList)
            result = structured_llm.invoke(prompt)

            # Validate output
            if not result or not result.keywords:
                logger.warning("LLM returned empty keyword list")
                return None

            # Post-generation validation
            total_keywords = len(result.keywords)
            target_keywords = num_broad_seeds + num_targeted_seeds

            if total_keywords < target_keywords * 0.8:
                logger.warning(
                    f"Generated {total_keywords} keywords (target: {target_keywords}) - "
                    f"below 80% threshold"
                )

            # Check for suspicious keywords
            suspicious_count = 0
            for kw in result.keywords:
                if self._is_suspicious_keyword(kw.keyword, solution_type, niche_context):
                    logger.warning(
                        f"Potentially suspicious keyword: '{kw.keyword}' - "
                        f"Rationale: {kw.rationale}"
                    )
                    suspicious_count += 1

            if suspicious_count > 5:
                logger.warning(
                    f"Found {suspicious_count} potentially suspicious keywords - "
                    f"review prompt alignment with semantic validation rules"
                )

            logger.info(
                f"[OK] Generated {total_keywords} seed keywords across "
                f"{len(result.topic_clusters)} clusters"
            )

            return result

        except Exception as e:
            logger.error(f"Seed keyword generation failed: {e}", exc_info=True)
            return None

    def _sanitize_for_prompt(self, text: Optional[str], max_length: int = 1000) -> str:
        """
        Sanitize user input for safe prompt inclusion.

        Prevents prompt injection and reduces excessive whitespace.

        Args:
            text: Input text to sanitize (can be None)
            max_length: Maximum allowed length

        Returns:
            Sanitized text (empty string if input is None)
        """
        if not text:
            return ""

        # Strip excessive whitespace and newlines
        text = " ".join(text.split())

        # Truncate to max length
        text = text[:max_length]

        return text

    def _is_suspicious_keyword(
        self,
        keyword: str,
        solution_type: str,
        niche_context: Optional["NicheContext"]
    ) -> bool:
        """
        Check if a keyword violates semantic validation rules.

        Detects nonsensical patterns like:
        - "apps for X" where X is a physical product
        - "enterprise X" where X is a B2C consumer product
        - Keywords outside industry boundaries
        - Invented brand names (e.g., "ExpatEase", "RefactorHub")

        Args:
            keyword: Keyword to validate
            solution_type: Type of solution (saas/directory/aggregator/etc)
            niche_context: Optional niche context with boundaries

        Returns:
            True if keyword appears suspicious
        """
        keyword_lower = keyword.lower()

        # Rule 1: Check for "app/apps for X" with physical products
        # Explanation: "apps for furniture" is nonsensical (furniture isn't software)
        if 'apps for' in keyword_lower or 'app for' in keyword_lower:
            # Only flag if niche involves physical products (not SaaS)
            if solution_type != 'saas' and niche_context:
                niche_desc_lower = niche_context.niche_description.lower()
                # Physical indicators: products you can touch/ship
                physical_indicators = {
                    'appliance', 'furniture', 'vehicle', 'equipment',
                    'hardware', 'device', 'product', 'goods'
                }
                if any(indicator in niche_desc_lower for indicator in physical_indicators):
                    logger.debug(f"Suspicious: '{keyword}' uses 'apps for' with physical product niche")
                    return True

        # Rule 2: Check for "enterprise X" with B2C indicators
        if 'enterprise' in keyword_lower:
            if niche_context and niche_context.market_segments:
                # Check if segments are consumer-focused (not B2B)
                segments_text = " ".join(niche_context.market_segments).lower()

                consumer_indicators = {
                    'consumer', 'homeowner', 'home', 'personal', 'family',
                    'individual', 'residential', 'first-time buyer'
                }
                b2b_indicators = {
                    'business', 'enterprise', 'company', 'team', 'organization',
                    'corporate', 'professional', 'agency'
                }

                has_consumer = any(indicator in segments_text for indicator in consumer_indicators)
                has_b2b = any(indicator in segments_text for indicator in b2b_indicators)

                # Suspicious if strong consumer focus without B2B presence
                if has_consumer and not has_b2b:
                    logger.debug(f"Suspicious: '{keyword}' uses 'enterprise' in B2C context")
                    return True

        # Rule 4: Check industry boundaries if provided
        if niche_context and niche_context.industry_boundaries:
            boundaries_lower = niche_context.industry_boundaries.lower()

            # Extract OUT OF SCOPE terms with robust parsing
            out_of_scope_pattern = re.compile(
                r'out\s+of\s+scope[:\s]+(.*?)(?:in\s+scope|$)',
                re.IGNORECASE | re.DOTALL
            )
            out_of_scope_match = out_of_scope_pattern.search(boundaries_lower)

            if out_of_scope_match:
                excluded_terms = out_of_scope_match.group(1).strip()
                # Split by common delimiters, clean whitespace
                excluded_list = [
                    term.strip()
                    for term in re.split(r'[,;.\n]', excluded_terms)
                    if term.strip() and len(term.strip()) > 3
                ]

                for excluded in excluded_list:
                    # Simple word boundary check using string containment
                    # Add spaces around keyword and term to ensure word boundaries
                    if f' {excluded} ' in f' {keyword_lower} ':
                        logger.debug(f"Suspicious: '{keyword}' matches excluded term '{excluded}'")
                        return True

        # Rule 7: Check for invented brand names in keywords
        # Heuristic detection for portmanteaus and novel compound words
        if self._appears_to_be_brand_name(keyword):
            logger.debug(f"Suspicious: '{keyword}' appears to be an invented brand name")
            return True

        return False

    @staticmethod
    def _appears_to_be_brand_name(keyword: str) -> bool:
        """
        Detect if keyword appears to be an invented brand name.

        Heuristics:
        - CamelCase or PascalCase patterns (e.g., ExpatEase, RefactorHub)
        - Contains common brand suffixes (Hub, Ease, Pro, Plus, etc.)
        - Portmanteau patterns (blended words)

        Args:
            keyword: Keyword to check

        Returns:
            True if keyword appears to be a brand name
        """
        # Whitelist common acronyms that contain mid-word capitals
        # These are industry-standard terms, NOT brand names
        COMMON_ACRONYMS = {
            'SaaS', 'PaaS', 'IaaS', 'BaaS',  # Cloud service models
            'API', 'APIs',                     # Application interfaces
            'B2B', 'B2C', 'B2B2C',             # Business models
            'AI', 'ML', 'LLM',                 # Artificial intelligence
            'IoT', 'iOS', 'macOS',             # Operating systems / tech
            'SME', 'SMB',                      # Business segments
            'MVP', 'GTM', 'KPI',               # Business terms
            'SEO', 'SEM', 'CRO',               # Marketing terms
            'OAuth', 'GraphQL', 'GitHub', 'GitLab',  # Tech platforms
            'JavaScript', 'TypeScript',        # Programming languages
            'DevOps', 'DataOps', 'MLOps',      # Operations methodologies
            'FinTech', 'EdTech', 'HealthTech', 'MarTech'  # Industry sectors
        }

        # Check if keyword contains any whitelisted acronym
        for acronym in COMMON_ACRONYMS:
            if acronym in keyword:
                # Remove acronym from keyword and check remainder
                keyword_without_acronym = keyword.replace(acronym, '')

                # If no mid-word capitals remain after removing acronym, it's safe
                if not re.search(r'[a-z][A-Z]', keyword_without_acronym):
                    logger.debug(f"Brand check: '{keyword}' contains acronym '{acronym}' - ALLOWED")
                    return False

        # Check for mid-word capitals (CamelCase/PascalCase)
        if re.search(r'[a-z][A-Z]', keyword):
            logger.debug(f"Brand heuristic: '{keyword}' has mid-word capitals")
            return True

        # Check for common brand suffixes
        brand_suffixes = {
            'ease', 'hub', 'pro', 'plus', 'signal', 'atlas', 'track',
            'buddy', 'mentor', 'iq', 'genius', 'master', 'ninja'
        }

        # Whitelist of common words that end with suffixes but aren't brands
        common_words_whitelist = {
            'ease', 'track', 'increase', 'decrease', 'release', 'database',
            'please', 'grease', 'disease'
        }

        keyword_lower = keyword.lower()

        # Skip if in whitelist
        if keyword_lower in common_words_whitelist:
            return False

        if any(keyword_lower.endswith(suffix) for suffix in brand_suffixes):
            # Additional checks: single word AND minimum length
            if ' ' not in keyword.strip() and len(keyword) > 4:
                logger.debug(f"Brand heuristic: '{keyword}' ends with brand suffix")
                return True

        return False


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

**CRITICAL: Include Thread Index**
Each validation object MUST include the thread_index to ensure proper alignment with the input threads.

Each validation object must have:
- thread_index: the index number (0, 1, 2, etc.) of the thread being validated
- is_relevant: true/false
- confidence: 0.0-1.0
- reason: "brief explanation"

Be strict - only mark as relevant if the thread clearly discusses niche-related problems or needs."""

            try:
                # Use structured output with Pydantic model for consistent parsing
                structured_llm = self.llm.with_structured_output(BatchValidationResponse)
                response = structured_llm.invoke(prompt)

                # Track which threads were validated
                validated_indices = set()

                # Match results by thread_index (not position) to prevent misalignment
                for validation_result in response.results:
                    thread_idx = validation_result.thread_index

                    # Validate thread_index is in bounds
                    if thread_idx < 0 or thread_idx >= len(batch):
                        logger.warning(
                            f"Invalid thread_index {thread_idx} (batch size: {len(batch)}) - skipping result"
                        )
                        continue

                    thread_item = batch[thread_idx]
                    is_relevant = validation_result.is_relevant
                    results.append((thread_item, is_relevant))
                    validated_indices.add(thread_idx)

                    # Log validation decision at DEBUG level
                    logger.debug(
                        f"Validation [idx={thread_idx}]: {thread_item.title[:50]}... -> "
                        f"{'RELEVANT' if is_relevant else 'FILTERED'} "
                        f"(confidence: {validation_result.confidence:.2f}, "
                        f"reason: {validation_result.reason})"
                    )

                # Verify all threads were validated (fail-open for missing)
                if len(validated_indices) < len(batch):
                    missing_count = len(batch) - len(validated_indices)
                    logger.warning(
                        f"Validation incomplete: {missing_count}/{len(batch)} threads missing results - "
                        f"keeping unvalidated threads (fail-open)"
                    )
                    # Add missing threads as relevant
                    for idx, thread_item in enumerate(batch):
                        if idx not in validated_indices:
                            results.append((thread_item, True))
                            logger.debug(
                                f"Validation [idx={idx}]: {thread_item.title[:50]}... -> RELEVANT "
                                f"(default, not in LLM response)"
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


def find_solution_by_name(
    solution_name: str,
    solution_list: List['SolutionIdea']
) -> Optional['SolutionIdea']:
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
    if not solution_list:
        return None

    # Try exact match first
    exact_match = next(
        (sol for sol in solution_list if sol.solution_name == solution_name),
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


class ContentTokenMonitor:
    """
    Token counting and cost monitoring for LLM inputs.

    Provides visibility into token usage without enforcing hard limits.
    Supports configurable soft caps and cost estimation.

    Used for: Monitoring large content inputs (Reddit/Twitter posts) to prevent
    unexpected costs and track context window usage.
    """

    # Cost per 1M input tokens (USD) - update as needed
    MODEL_COSTS = {
        "gpt-4o": 2.50,
        "gpt-4o-mini": 0.15,
        "gpt-4-turbo": 10.00,
        "gpt-4": 30.00,
        "gpt-3.5-turbo": 0.50,
    }

    def __init__(self):
        """Initialize token monitor."""
        try:
            import tiktoken
            self.tiktoken = tiktoken
            self.encoding_cache = {}
        except ImportError:
            logger.warning(
                "tiktoken not installed - token counting disabled. "
                "Install with: pip install tiktoken"
            )
            self.tiktoken = None
            self.encoding_cache = {}

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        """
        Count tokens in text for specified model.

        Args:
            text: Input text to count tokens
            model: OpenAI model name (default: gpt-4o)

        Returns:
            Token count, or 0 if tiktoken not available
        """
        if not self.tiktoken or not text:
            return 0

        try:
            # Get or create encoding for model
            if model not in self.encoding_cache:
                self.encoding_cache[model] = self.tiktoken.encoding_for_model(model)

            encoding = self.encoding_cache[model]
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed for model {model}: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4

    def estimate_cost(self, tokens: int, model: str = "gpt-4o") -> float:
        """
        Estimate API cost for token count.

        Args:
            tokens: Number of input tokens
            model: OpenAI model name

        Returns:
            Estimated cost in USD
        """
        cost_per_million = self.MODEL_COSTS.get(model, 2.50)  # Default to gpt-4o
        return (tokens / 1_000_000) * cost_per_million

    def log_content_stats(
        self,
        content: str,
        label: str,
        model: str = "gpt-4o",
        context_limit: int = 1_000_000
    ) -> int:
        """
        Log token count and cost estimate for content.

        Args:
            content: Content to analyze
            label: Descriptive label for logging (e.g., "Task 1 Reddit content")
            model: Model name for token counting
            context_limit: Model's context window size (default: 1M for extended models)

        Returns:
            Token count
        """
        if not settings.token_monitoring_enabled:
            return 0

        token_count = self.count_tokens(content, model)
        cost_estimate = self.estimate_cost(token_count, model)
        percentage = (token_count / context_limit) * 100

        logger.info(
            f"{label}: {token_count:,} tokens (~${cost_estimate:.2f}), "
            f"{percentage:.1f}% of {context_limit:,} context window"
        )

        return token_count

    def check_soft_cap(
        self,
        tokens: int,
        label: str,
        model: str = "gpt-4o"
    ) -> bool:
        """
        Check if token count exceeds soft cap and log warnings.

        Args:
            tokens: Token count to check
            label: Descriptive label for logging
            model: Model name for cost estimation

        Returns:
            True if over soft cap (when enabled), False otherwise
        """
        # Check warning threshold (always enabled)
        if tokens > settings.token_warning_threshold:
            cost = self.estimate_cost(tokens, model)
            logger.warning(
                f"{label}: Large content detected ({tokens:,} tokens, ~${cost:.2f}). "
                f"Exceeds warning threshold of {settings.token_warning_threshold:,} tokens."
            )

        # Check soft cap (if enabled)
        if settings.token_soft_cap_enabled and tokens > settings.token_soft_cap:
            cost = self.estimate_cost(tokens, model)
            logger.critical(
                f"{label}: Content exceeds soft cap! "
                f"({tokens:,} tokens > {settings.token_soft_cap:,} limit, ~${cost:.2f}). "
                f"Consider reducing collection size or increasing soft cap in settings."
            )
            return True

        return False


def _load_keyword_exceptions(filename: str) -> set:
    """
    Load keyword exception list from external file.

    Exceptions are legitimate single-word keywords that should bypass pre-filtering.
    Used by KeywordRelevanceValidator.

    Args:
        filename: Name of exception file in config directory

    Returns:
        Set of lowercase exception terms
    """
    from pathlib import Path

    file_path = Path(__file__).parent.parent / "config" / filename
    exceptions = set()

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    exceptions.add(line.lower())

        logger.info(f"[OK] Loaded {len(exceptions)} keyword exceptions from {filename}")
        return exceptions

    except FileNotFoundError:
        logger.warning(f"Exception file not found: {file_path} - using empty exception set")
        return set()
    except Exception as e:
        logger.error(f"Failed to load exception file {filename}: {e}")
        return set()


class KeywordRelevance(BaseModel):
    """Single keyword relevance validation result."""

    model_config = ConfigDict(extra='forbid')

    keyword: str = Field(..., description="The exact keyword being evaluated (must match input)")
    is_relevant: bool = Field(..., description="Whether the keyword is relevant to the niche/solution")
    relevance_score: float = Field(..., description="Relevance score 0.0-1.0 (0=irrelevant, 1=perfect match)")
    reason: str = Field(..., description="Brief explanation of the relevance decision")


class KeywordBatchValidation(BaseModel):
    """Batch keyword validation response containing multiple results."""

    model_config = ConfigDict(extra='forbid')

    results: List[KeywordRelevance] = Field(..., description="List of validation results, one per keyword")


class KeywordRelevanceValidator:
    """
    Validates keyword relevance to niche/solution using LLM validation.

    Two-stage filtering:
    1. Pre-filter: Universal rule-based filtering (single-word, too short, etc.)
    2. LLM validation: Semantic relevance scoring using configured model

    Model can be configured via KEYWORD_VALIDATION_LLM in .env
    (defaults to gpt-4o-mini for cost efficiency).

    Used in: Stage 9.5c (keyword expansion validation).
    """

    # Load exception list from external file
    SINGLE_WORD_EXCEPTIONS = _load_keyword_exceptions("keyword_exceptions.txt")

    def __init__(self):
        """Initialize keyword relevance validator."""
        # Use configured model for validation (default: gpt-4o-mini)
        self.llm = ChatOpenAI(
            model=settings.keyword_validation_llm,
            temperature=0,  # Deterministic for consistency
            api_key=settings.openai_api_key,
            timeout=120,  # 2 minute timeout to prevent indefinite hangs
        )

    def pre_filter_keywords(self, keywords: List[dict], skip_single_word_filter: bool = False) -> List[dict]:
        """
        Apply universal rule-based pre-filtering before LLM validation.

        Filters out:
        1. Single-word keywords (except those in SINGLE_WORD_EXCEPTIONS) - can be skipped for seeds
        2. Very short keywords (<4 chars, except exceptions like 'api', 'seo')
        3. Keywords with special characters (emoji, symbols)

        Args:
            keywords: List of keyword dicts with 'keyword' key
            skip_single_word_filter: If True, allow single-word keywords (for seed validation)

        Returns:
            Filtered list of keyword dicts
        """
        filtered = []
        removed_count = 0

        for kw_dict in keywords:
            keyword = kw_dict.get('keyword', '').strip()
            keyword_lower = keyword.lower()

            # Rule 1: Filter single-word keywords (except exceptions or when skip flag is set)
            # Count hyphenated parts as separate words (e.g., "micro-saas" = 2 words)
            # Filter empty strings to handle leading/trailing hyphens correctly
            word_count = len([w for w in re.split(r'[\s\-]+', keyword) if w])
            if word_count == 1 and not skip_single_word_filter and keyword_lower not in self.SINGLE_WORD_EXCEPTIONS:
                logger.debug(f"Pre-filter: Removed single-word keyword '{keyword}' (not in exceptions)")
                removed_count += 1
                continue

            # Rule 2: Filter very short keywords (except exceptions)
            if len(keyword) < 4 and keyword_lower not in self.SINGLE_WORD_EXCEPTIONS:
                logger.debug(f"Pre-filter: Removed short keyword '{keyword}' (<4 chars, not in exceptions)")
                removed_count += 1
                continue

            # Rule 3: Filter keywords with special characters/emoji
            # Allow alphanumeric, spaces, hyphens, apostrophes, ampersand (valid per DataForSEO docs)
            if not re.match(r'^[a-zA-Z0-9\s\-\'&]+$', keyword):
                logger.debug(f"Pre-filter: Removed keyword with special characters '{keyword}'")
                removed_count += 1
                continue

            # Passed all pre-filter rules
            filtered.append(kw_dict)

        logger.info(
            f"[Pre-filter] Kept {len(filtered)}/{len(keywords)} keywords "
            f"(removed {removed_count} generic/short keywords)"
        )

        return filtered

    def validate_batch(
        self,
        keywords: List[dict],
        niche_description: str,
        solution_name: str,
        solution_description: str,
        project_type: str = "saas",
        batch_size: int = 50,
        threshold: float = 0.5,
        skip_single_word_filter: bool = False,
        validation_cache: Optional[Dict[str, tuple]] = None
    ) -> List[tuple]:
        """
        Validate keyword relevance in batches using LLM.

        Returns list of (keyword_dict, is_relevant, relevance_score) tuples.

        Args:
            keywords: List of keyword dicts with 'keyword' key (and optionally volume/competition)
            niche_description: Description of the niche
            solution_name: Name of the solution
            solution_description: Description of the solution
            project_type: Solution type (saas/directory/aggregator/etc)
            batch_size: Number of keywords to validate per API call (default: 50)
            threshold: Minimum relevance score to consider relevant (default: 0.5)
            skip_single_word_filter: If True, allow single-word keywords (for seed validation)
            validation_cache: Optional dict to cache results across calls {keyword_lower: (is_relevant, score)}

        Returns:
            List of (keyword_dict, is_relevant, relevance_score) tuples
        """
        # Pre-filter first
        filtered_keywords = self.pre_filter_keywords(keywords, skip_single_word_filter=skip_single_word_filter)

        if not filtered_keywords:
            logger.warning("Pre-filter removed all keywords - returning empty result")
            return []

        results = []

        # Separate cached vs uncached keywords
        uncached_keywords = []
        if validation_cache is not None:
            for kw_dict in filtered_keywords:
                keyword_lower = kw_dict.get('keyword', '').strip().lower()
                if keyword_lower in validation_cache:
                    # Use cached result
                    is_relevant, score = validation_cache[keyword_lower]
                    results.append((kw_dict, is_relevant, score))
                    logger.debug(f"Cache hit: '{keyword_lower}' -> relevant={is_relevant}, score={score}")
                else:
                    uncached_keywords.append(kw_dict)

            if uncached_keywords:
                logger.info(f"[Validation] Cache: {len(filtered_keywords) - len(uncached_keywords)} hits, {len(uncached_keywords)} to validate")
        else:
            uncached_keywords = filtered_keywords

        if not uncached_keywords:
            logger.info("[Validation] All keywords found in cache - skipping LLM validation")
            return results

        for i in range(0, len(uncached_keywords), batch_size):
            batch = uncached_keywords[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(uncached_keywords) + batch_size - 1) // batch_size
            logger.info(f"[Validation] Processing batch {batch_num}/{total_batches} ({len(batch)} keywords)...")

            # Format batch for prompt (keyword only, with index)
            keywords_text = "\n".join([
                f"[{idx}] {kw_dict.get('keyword', 'N/A')}"
                for idx, kw_dict in enumerate(batch)
            ])

            prompt = self._build_validation_prompt(
                keywords_text=keywords_text,
                batch_size=len(batch),
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description,
                project_type=project_type
            )

            try:
                # Use structured output with Pydantic model for consistent parsing
                structured_llm = self.llm.with_structured_output(KeywordBatchValidation)
                response = structured_llm.invoke(prompt)

                # Build keyword-to-index mapping for accurate matching
                keyword_to_idx = {
                    kw_dict.get('keyword', '').strip().lower(): idx
                    for idx, kw_dict in enumerate(batch)
                }

                # Track which keywords were validated
                validated_keywords = set()

                # Match results by keyword (not position) to prevent misalignment
                for validation_result in response.results:
                    keyword_lower = validation_result.keyword.strip().lower()

                    if keyword_lower in keyword_to_idx:
                        idx = keyword_to_idx[keyword_lower]
                        kw_dict = batch[idx]

                        is_relevant = (
                            validation_result.is_relevant and
                            validation_result.relevance_score >= threshold
                        )

                        results.append((
                            kw_dict,
                            is_relevant,
                            validation_result.relevance_score
                        ))

                        validated_keywords.add(keyword_lower)

                        # Update cache with new result
                        if validation_cache is not None:
                            validation_cache[keyword_lower] = (is_relevant, validation_result.relevance_score)

                        # Log validation decision at DEBUG level
                        status = "RELEVANT" if is_relevant else "FILTERED"
                        logger.debug(
                            f"Validation: {validation_result.keyword} -> "
                            f"{status} (score: {validation_result.relevance_score:.2f}, "
                            f"reason: {validation_result.reason})"
                        )
                    else:
                        logger.warning(
                            f"LLM returned result for unknown keyword: '{validation_result.keyword}' "
                            f"(not in batch) - skipping"
                        )

                # Log missing keywords (wrapper will handle retry if used)
                if len(validated_keywords) < len(batch):
                    missing_count = len(batch) - len(validated_keywords)
                    missing_keywords_list = [
                        kw_dict.get('keyword')
                        for kw_dict in batch
                        if kw_dict.get('keyword', '').lower() not in validated_keywords
                    ]
                    logger.debug(
                        f"LLM did not validate {missing_count} keywords from batch: "
                        f"{', '.join(missing_keywords_list[:5])}"
                        f"{'...' if len(missing_keywords_list) > 5 else ''}"
                    )

            except Exception as e:
                logger.warning(
                    f"Validation batch failed: {e} - batch will be retried if wrapper is used"
                )
                # Don't add keywords on error - let wrapper handle retry
                # (If validate_batch called directly, batch will be lost)

        # Log summary
        relevant_count = sum(1 for _, is_relevant, _ in results if is_relevant)
        logger.info(
            f"[LLM Validation] {relevant_count}/{len(results)} keywords passed relevance threshold "
            f"({threshold:.1f})"
        )

        return results

    def validate_batch_with_retry(
        self,
        keywords: List[Dict[str, Any]],
        niche_description: str,
        solution_name: str,
        solution_description: str,
        project_type: str = "saas",
        batch_size: int = 50,
        threshold: float = 0.5,
        max_retries: int = 1,
        retry_batch_size: Optional[int] = None,
        fail_open_after_retry: bool = False
    ) -> List[tuple]:
        """
        Validate keyword relevance with automatic retry for missing keywords.

        This wrapper method calls validate_batch() for the initial validation attempt,
        then retries any keywords that the LLM failed to validate. This improves
        validation coverage from ~80-95% to >98%.

        Args:
            keywords: List of keyword dicts to validate
            niche_description: Description of the niche
            solution_name: Name of the solution being analyzed
            solution_description: Description of the solution
            project_type: Type of solution (saas, directory, marketplace, etc.)
            batch_size: Keywords per API call for first attempt (default: 50)
            threshold: Minimum relevance score to pass (default: 0.5)
            max_retries: Maximum retry attempts for missing keywords (default: 1)
            retry_batch_size: Keywords per API call for retry (default: same as batch_size)
            fail_open_after_retry: If True, add still-missing keywords as relevant after retry;
                                  if False, exclude them (default: False - fail-closed)

        Returns:
            List of (keyword_dict, is_relevant, relevance_score) tuples

        Example:
            >>> validator = KeywordRelevanceValidator()
            >>> results = validator.validate_batch_with_retry(
            ...     keywords=[{'keyword': 'saas tools'}, {'keyword': 'random phrase'}],
            ...     niche_description="tools for indie hackers",
            ...     solution_name="No-Code Exit Ramp",
            ...     solution_description="Exit planning for no-code founders",
            ...     batch_size=150,
            ...     max_retries=1,
            ...     retry_batch_size=50
            ... )
        """
        # Guard against empty input (prevents division by zero)
        if not keywords:
            logger.debug("[Validation] Empty keyword list - nothing to validate")
            return []

        # Filter out keywords with None/empty keyword field
        valid_keywords = [
            kw for kw in keywords
            if kw.get('keyword') and kw.get('keyword', '').strip()
        ]
        if len(valid_keywords) < len(keywords):
            logger.debug(
                f"[Validation] Filtered {len(keywords) - len(valid_keywords)} keywords with empty/None values"
            )
        keywords = valid_keywords

        if not keywords:
            logger.debug("[Validation] No valid keywords remaining after filtering")
            return []

        if retry_batch_size is None:
            retry_batch_size = batch_size

        # Build mapping for later use
        input_keywords_lower = {
            kw.get('keyword', '').strip().lower(): kw
            for kw in keywords
        }

        # ATTEMPT 1: Initial validation
        logger.info(f"[Validation] Starting initial validation of {len(keywords)} keywords (batch_size={batch_size})")

        try:
            results = self.validate_batch(
                keywords=keywords,
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description,
                project_type=project_type,
                batch_size=batch_size,
                threshold=threshold
            )
        except Exception as e:
            logger.warning(
                f"[Validation] Initial validation failed with error: {e} - "
                f"treating all {len(keywords)} keywords as missing for retry"
            )
            results = []

        # Build set of validated keywords (lowercase for matching)
        validated_keywords = {
            kw_dict.get('keyword', '').strip().lower()
            for kw_dict, _, _ in results
        }

        # Identify missing keywords (keywords passed in but not in results)
        missing_keyword_keys = set(input_keywords_lower.keys()) - validated_keywords
        missing_keywords = [input_keywords_lower[key] for key in missing_keyword_keys]

        if not missing_keywords:
            logger.info(
                f"[Validation] Initial validation complete: 100% coverage "
                f"({len(results)}/{len(keywords)} keywords)"
            )
            return results

        # RETRY LOGIC
        logger.warning(
            f"[Validation] Initial validation incomplete: {len(missing_keywords)}/{len(keywords)} keywords missing "
            f"({len(missing_keywords)/len(keywords)*100:.1f}%) - preparing retry"
        )

        retry_count = 0
        remaining_missing = missing_keywords

        while retry_count < max_retries and remaining_missing:
            retry_count += 1

            logger.info(
                f"[Validation Retry {retry_count}/{max_retries}] Attempting validation of "
                f"{len(remaining_missing)} missing keywords (batch_size={retry_batch_size})"
            )

            # Retry validation on missing keywords only
            try:
                retry_results = self.validate_batch(
                    keywords=remaining_missing,
                    niche_description=niche_description,
                    solution_name=solution_name,
                    solution_description=solution_description,
                    project_type=project_type,
                    batch_size=retry_batch_size,
                    threshold=threshold
                )
            except Exception as e:
                logger.warning(
                    f"[Validation Retry {retry_count}] Failed with error: {e} - "
                    f"continuing with {len(remaining_missing)} keywords still missing"
                )
                # Break out of retry loop on exception
                break

            # Add retry results to main results
            retry_validated = {
                kw_dict.get('keyword', '').strip().lower()
                for kw_dict, _, _ in retry_results
            }

            results.extend(retry_results)
            validated_keywords.update(retry_validated)

            # Update remaining missing keywords
            still_missing_keys = {
                kw.get('keyword', '').strip().lower()
                for kw in remaining_missing
            } - retry_validated

            remaining_missing = [
                input_keywords_lower[key]
                for key in still_missing_keys
                if key in input_keywords_lower
            ]

            logger.info(
                f"[Validation Retry {retry_count}] Validated {len(retry_validated)} keywords, "
                f"{len(remaining_missing)} still missing"
            )

        # FINAL FAIL-OPEN/FAIL-CLOSED DECISION
        if remaining_missing and fail_open_after_retry:
            logger.warning(
                f"[Validation] {len(remaining_missing)} keywords still missing after {retry_count} retry attempt(s) - "
                f"adding as relevant (fail-open strategy)"
            )

            for kw_dict in remaining_missing:
                results.append((kw_dict, True, 1.0))
                logger.debug(
                    f"Validation: {kw_dict.get('keyword')} -> RELEVANT "
                    f"(fail-open after {retry_count} retry attempt(s))"
                )
        elif remaining_missing:
            logger.warning(
                f"[Validation] {len(remaining_missing)} keywords still missing after {retry_count} retry attempt(s) - "
                f"EXCLUDING from results (fail-closed strategy)"
            )

        # SUMMARY
        relevant_count = sum(1 for _, is_relevant, _ in results if is_relevant)
        retry_recovered = len(missing_keywords) - len(remaining_missing) if remaining_missing else len(missing_keywords)

        logger.info(
            f"[Validation Complete] {relevant_count}/{len(results)} keywords passed relevance threshold. "
            f"Coverage: {len(results)}/{len(keywords)} ({len(results)/len(keywords)*100:.1f}%). "
            f"Retry recovered: {retry_recovered} keywords"
        )

        return results

    def _build_validation_prompt(
        self,
        keywords_text: str,
        batch_size: int,
        niche_description: str,
        solution_name: str,
        solution_description: str,
        project_type: str
    ) -> str:
        """
        Build LLM validation prompt for keyword batch with strict semantic relevance.

        Args:
            keywords_text: Formatted keyword list with indices
            batch_size: Number of keywords in batch
            niche_description: Niche description
            solution_name: Solution name
            solution_description: Solution description
            project_type: Solution type

        Returns:
            Formatted validation prompt
        """
        return f"""You are a strict keyword relevance classifier. Your job is to filter OUT keywords that do not LITERALLY and SEMANTICALLY match this specific niche and solution.

═══════════════════════════════════════════════════════════════════════════
TARGET CONTEXT (This is what keywords MUST match)
═══════════════════════════════════════════════════════════════════════════

NICHE: {niche_description}

SOLUTION:
- Name: {solution_name}
- Type: {project_type}
- Description: {solution_description}

═══════════════════════════════════════════════════════════════════════════
KEYWORDS TO EVALUATE
═══════════════════════════════════════════════════════════════════════════

{keywords_text}

═══════════════════════════════════════════════════════════════════════════
RELEVANCE CRITERIA (ALL must be satisfied for RELEVANT)
═══════════════════════════════════════════════════════════════════════════

A keyword is RELEVANT **ONLY IF** it passes this 3-step test:

**STEP 1: LITERAL SEMANTIC MATCH**
- Does this keyword literally describe the niche topic, industry, or solution category?
- Would a real user searching for THIS SPECIFIC solution type use this exact phrase?
- Is this keyword used in the SAME industry/domain as the niche?

**STEP 2: USER INTENT VERIFICATION**
- If someone searches this keyword, would they realistically expect to find THIS solution type?
- Does the keyword represent a problem/need that THIS solution solves?
- Is the search intent compatible with the solution's value proposition?

**STEP 3: CATEGORY BOUNDARY CHECK**
- Is the keyword in the same product/service category as the solution?
- Does the keyword belong to the same industry vertical?
- Is the keyword targeting the same user persona/market segment?

**AUTOMATIC REJECTION RULES (Mark as NOT RELEVANT immediately if ANY apply):**

**IMPORTANT EXCEPTION**: If the niche/solution is related to software, SaaS, tech tools, or developer tools, then technical/developer keywords (e.g., npm, react, terraform, docker, validation, API, SDK) ARE RELEVANT and should NOT be rejected. These are core industry terms for software niches.

1. **Wrong Industry**: Medical/health terms for tech niches (UNLESS metaphorical like "pain point"), consumer goods for B2B SaaS, academic terms for business tools (UNLESS educational SaaS)
2. **Physical Products**: Hardware, appliances, vehicles, food, clothing (unless niche explicitly targets these)
3. **Financial Products**: Credit cards, loans, banking (unless niche is fintech)
4. **Geographic Mismatches**: City/country names when solution isn't location-specific
5. **Conceptual Analogies**: Keywords that share abstract concepts but different domains (e.g., "pain" in medical vs. "pain point" in business)
6. **Keyword Collisions**: Same word, different meaning ("discover" = credit card vs. "discover" = find tools)
7. **Over-Generalization**: Generic terms that could apply to 100+ unrelated categories

═══════════════════════════════════════════════════════════════════════════
SCORING GUIDE (Be strict - default to LOW scores)
═══════════════════════════════════════════════════════════════════════════

- **1.0**: Core category term, exact solution type match (e.g., "saas directory" for SaaS directory)
- **0.8-0.9**: High-intent, niche-specific keyword (e.g., "indie hacker tools" for indie hacker SaaS)
- **0.6-0.7**: Relevant expansion, clear semantic match (e.g., "startup software" for indie hacker niche)
- **0.4-0.5**: Borderline - weak connection, consider rejecting
- **0.0-0.3**: NOT RELEVANT - wrong industry, conceptual stretch, or keyword collision

**Default to 0.0-0.3 unless you can clearly justify 0.6+**

═══════════════════════════════════════════════════════════════════════════
NEGATIVE EXAMPLES (Learn from these failures)
═══════════════════════════════════════════════════════════════════════════

**Conceptual Stretching (REJECT these):**
- ❌ "lower stomach pain" for business tools niche → Medical condition, not business pain point
- ❌ "discover america" for SaaS discovery niche → Geographic exploration, not software discovery
- ❌ "hunter boots" for ProductHunt-style directory → Fashion product, not software tools
- ❌ "scholar athlete" for research tools → Academic person, not research software

**Keyword Collisions (REJECT these):**
- ❌ "find my device" for SaaS finder → Apple device tracker, not software discovery
- ❌ "discover card" for expat relocation → Credit card brand, not relocation services
- ❌ "scholar" for business intelligence → Academic research platform, not BI tools

**Wrong Industry (REJECT these):**
- ❌ "dental labs" for indie hacker tools → Medical/healthcare, not tech
- ❌ "stomach issues" for SaaS directory → Health problem, not business problem
- ❌ "home appliances" for software directory → Physical products, not software

**Generic Terms Without Context (REJECT these):**
- ❌ "tools" alone (too generic - needs "saas tools", "dev tools", etc.)
- ❌ "finder" alone (too generic - needs "software finder", "tool finder", etc.)

═══════════════════════════════════════════════════════════════════════════
EVALUATION INSTRUCTIONS
═══════════════════════════════════════════════════════════════════════════

For EACH of the {batch_size} keywords:

1. **Chain-of-Thought Reasoning** (do this mentally):
   - "What industry/category does this keyword belong to?"
   - "What would a user searching this keyword expect to find?"
   - "Is that expectation compatible with [{solution_name}] - a [{project_type}]?"
   - "Can I confidently say this keyword LITERALLY describes the niche/solution?"

2. **Check Automatic Rejection Rules**: If ANY rule applies → relevance_score ≤ 0.3

3. **Assign Score**: Default to LOW (0.0-0.3) unless clear semantic match

4. **Write Reason**: State the industry/category match or mismatch in 1 sentence

═══════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════

**CRITICAL: Include Keyword Field**
Each result MUST include the exact keyword being evaluated to ensure proper alignment.

Return a JSON object with a 'results' array containing exactly {batch_size} validation objects:

{{
  "results": [
    {{
      "keyword": "exact keyword from input",  // MUST match input exactly
      "is_relevant": false,  // true ONLY if relevance_score >= 0.6
      "relevance_score": 0.1,  // 0.0-1.0, default to LOW unless clearly relevant
      "reason": "Medical symptom keyword, not related to SaaS/tech tools industry"
    }},
    ...
  ]
}}

**CRITICAL**: Be STRICT. It's better to reject borderline keywords than pollute the keyword set with irrelevant terms. When in doubt, mark as NOT RELEVANT."""


# ====================================================================================
# PAIN POINT FORMATTING HELPERS
# ====================================================================================

def format_pain_points_for_agents(
    pain_points: List,
    format_type: str = "detailed",
    priority_filter: Optional[str] = None,
    sort_by: str = "severity",
    limit: int = 10,
    include_quotes: bool = False
) -> str:
    """
    Unified pain point formatting helper for consistent data passing across crews.

    Eliminates duplication between UnifiedSolutionCrew and SEOStrategyCrew while
    ensuring all required fields are consistently included.

    Args:
        pain_points: List of PainPoint objects
        format_type: Output format (str). Valid values:
            - "detailed": Full context with description, metrics, quotes (UnifiedSolutionCrew)
              Example: "**1. Title**\\n- Problem: desc\\n- Severity: 8.5 | WTP: 7.2\\n- Mentions: 42"
            - "compact": Inline metrics only (SEOStrategyCrew, medium priority)
              Example: "**Title** (Severity: 8.5, WTP: 7.2)"
            - "metrics_only": Title + metrics in standardized format
              Example: "- Title (Severity: 8.5/10, WTP: 7.2/10, Mentions: 42)"
        priority_filter: Filter by opportunity_level (str or None). Valid values:
            - "high": Only high-opportunity pain points
            - "medium": Only medium-opportunity pain points
            - "low": Only low-opportunity pain points
            - None: All pain points (default if not specified)
        sort_by: Sort order (str). Valid values:
            - "severity": Sort by severity_score descending (highest first)
            - "wtp": Sort by willingness_to_pay descending
            - "mentions": Sort by mention_count descending
            - "title": Sort alphabetically by title ascending
        limit: Maximum number of pain points to include (int, default: 10)
        include_quotes: Include representative quote (bool). Only applies to "detailed" format.
            If True and format_type="detailed", adds quote line to output.

    Returns:
        Formatted string ready for crew kickoff inputs

    Example Usage:
        # UnifiedSolutionCrew - high priority with quotes
        high_priority_list = format_pain_points_for_agents(
            pain_points=pain_point_analysis.pain_points,
            format_type="detailed",
            priority_filter="high",
            sort_by="severity",
            limit=10,
            include_quotes=True
        )

        # SEOStrategyCrew - top 10 by severity
        top_pain_points = format_pain_points_for_agents(
            pain_points=pain_point_analysis.pain_points,
            format_type="metrics_only",
            sort_by="severity",
            limit=10
        )
    """
    # Validate inputs
    if not pain_points:
        return ""

    # Validate priority_filter
    if priority_filter and priority_filter not in ["high", "medium", "low"]:
        raise ValueError(
            f"Invalid priority_filter: '{priority_filter}'. "
            f"Must be one of: 'high', 'medium', 'low', or None"
        )

    # Validate sort_by
    valid_sort_options = ["severity", "wtp", "mentions", "title"]
    if sort_by not in valid_sort_options:
        raise ValueError(
            f"Invalid sort_by: '{sort_by}'. "
            f"Must be one of: {valid_sort_options}"
        )

    # Filter by priority if specified
    if priority_filter:
        filtered = [pp for pp in pain_points if pp.opportunity_level.value == priority_filter]
    else:
        filtered = pain_points

    # Sort
    if sort_by == "severity":
        filtered = sorted(filtered, key=lambda p: p.severity_score, reverse=True)
    elif sort_by == "wtp":
        filtered = sorted(filtered, key=lambda p: p.willingness_to_pay, reverse=True)
    elif sort_by == "mentions":
        filtered = sorted(filtered, key=lambda p: p.mention_count, reverse=True)
    elif sort_by == "title":
        filtered = sorted(filtered, key=lambda p: p.title)

    # Limit
    filtered = filtered[:limit]

    # Format based on type
    if format_type == "detailed":
        # UnifiedSolutionCrew format: Full context with description and metrics
        lines = []
        for i, pp in enumerate(filtered):
            parts = [
                f"**{i+1}. {pp.title}**",
                f"- Problem: {pp.description}",
                f"- Severity: {pp.severity_score:.2f} | WTP: {pp.willingness_to_pay:.2f}",
                f"- Mentions: {pp.mention_count}"
            ]
            if include_quotes and pp.representative_quotes:
                parts.append(f"- Key Quote: \"{pp.representative_quotes[0]}\"")
            lines.append("\n".join(parts))
        return "\n\n".join(lines) if lines else ""

    elif format_type == "compact":
        # Medium priority format: Inline metrics
        lines = [
            f"**{pp.title}** (Severity: {pp.severity_score:.2f}, WTP: {pp.willingness_to_pay:.2f})"
            for pp in filtered
        ]
        return "\n".join(lines) if lines else ""

    elif format_type == "metrics_only":
        # SEOStrategyCrew format: Standardized metrics with /10 scale
        lines = [
            f"- {pp.title} (Severity: {pp.severity_score:.1f}/10, WTP: {pp.willingness_to_pay:.1f}/10, Mentions: {pp.mention_count})"
            for pp in filtered
        ]
        return "\n".join(lines) if lines else ""

    else:
        raise ValueError(f"Unknown format_type: {format_type}. Must be 'detailed', 'compact', or 'metrics_only'")


def extract_pain_points_by_priority(
    pain_point_analysis: 'PainPointAnalysisResult'
) -> tuple[List['PainPoint'], List['PainPoint'], List['PainPoint']]:
    """
    Extract pain points grouped by opportunity level.

    Helper for crews that need separate high/medium/low priority lists.

    Args:
        pain_point_analysis: PainPointAnalysisResult from Stage 6

    Returns:
        Tuple of (high_priority, medium_priority, low_priority) lists

    Example Usage:
        high_priority, medium_priority, low_priority = extract_pain_points_by_priority(
            self.pain_point_analysis
        )
    """
    high_priority = [
        pp for pp in pain_point_analysis.pain_points
        if pp.opportunity_level.value == "high"
    ]
    medium_priority = [
        pp for pp in pain_point_analysis.pain_points
        if pp.opportunity_level.value == "medium"
    ]
    low_priority = [
        pp for pp in pain_point_analysis.pain_points
        if pp.opportunity_level.value == "low"
    ]

    return high_priority, medium_priority, low_priority
