"""
LLM-based search query generator for finding niche pain points.

Generates strategic search queries using context-aware prompting.
"""

import json
from typing import TYPE_CHECKING

from loguru import logger

from ...config.settings import settings
from ..llm_service import LLMService
from ..parsing.json_extractor import extract_json_array_from_text
from ..prompts import get_prompt

if TYPE_CHECKING:
    from ...models.research_state import NicheContext

class QueryGenerator:
    """LLM-based search query generator for finding niche pain points."""

    def __init__(self):
        pass  # No longer need to initialize LLM instance

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

    def _calculate_specificity_score(self, query: str) -> int:
        """
        Calculate specificity score for a query (0-5 scale).

        Universal scoring that rewards:
        1. Pain expressions (frustrated, stuck, overwhelmed)
        2. Role identifiers (beginner, career changer, etc.)
        3. Help-seeking patterns (anyone else, how do you)
        4. Discovery probes (biggest challenge, hardest part, etc.)
        5. Short length (3-6 words is optimal)

        Does NOT reward specific tool/tech names to avoid bias.

        Args:
            query: The search query text

        Returns:
            Score from 0-5 based on marker presence
        """
        query_lower = query.lower()
        word_count = len(query.split())
        score = 0

        # A. Pain Expressions — split into domain-anchored vs universal emotional
        # Domain-anchored pain: implies a specific process/task failure
        anchored_pain_markers = [
            'frustrated', 'stuck', 'struggling', 'confused',
            'hate', 'annoying', 'tired of', 'can\'t',
            'difficult', 'hard', 'impossible', 'nightmare', 'painful',
            'giving up', 'quit', 'takes forever', 'too expensive'
        ]
        # Universal emotional: these match ANY life situation without a domain anchor
        universal_emotional_markers = [
            'burnout', 'stress', 'anxiety', 'exhausted', 'overwhelmed',
            'mental health', 'depressed', 'lonely'
        ]
        if any(marker in query_lower for marker in anchored_pain_markers):
            score += 1
        elif any(marker in query_lower for marker in universal_emotional_markers):
            # Universal emotional terms only count if query has enough words
            # for a domain anchor (>=4 words gives room for niche context)
            if word_count >= 4:
                score += 1

        # B. Role Identifiers (universal across niches)
        role_markers = [
            'beginner', 'newbie', 'starter', 'first-time', 'new to',
            'career change', 'adult learner', 'working professional',
            'busy parent', 'freelancer', 'entrepreneur', 'student',
            'self-taught', 'hobbyist', 'aspiring'
        ]
        if any(marker in query_lower for marker in role_markers):
            score += 1

        # C. Help-Seeking Patterns (community engagement)
        help_patterns = [
            'anyone else', 'how do you', 'how to', 'is it worth',
            'should i', 'advice', 'help', 'tips', 'recommend',
            'what do you', 'does anyone', 'am i the only'
        ]
        if any(pattern in query_lower for pattern in help_patterns):
            score += 1

        # D. Discovery Probes (open-ended pain discovery)
        discovery_markers = [
            'biggest challenge', 'hardest part', 'what went wrong',
            'complaints about', 'most annoying', 'worst part',
            'regret', 'mistake', 'problem with', 'wish i knew'
        ]
        if any(marker in query_lower for marker in discovery_markers):
            score += 1

        # E. Optimal Length (3-6 words = good for search)
        if 3 <= word_count <= 6:
            score += 1

        return score

    def generate_queries(
        self,
        niche_description: str,
        niche_context: "NicheContext | None" = None,
        num_queries: int = 20,
        enabled_platforms: list[str] | None = None,
    ) -> list[dict]:
        """
        Generate strategic search queries for a niche using LLM.

        Args:
            niche_description: Description of the niche to generate queries for
            niche_context: Optional structured context with market segments and boundaries
            num_queries: Number of queries to generate
            enabled_platforms: List of enabled platforms (e.g. ["reddit", "twitter"]).
                None means all platforms enabled (backward compatible).

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

        # Build dynamic platform instructions based on enabled platforms
        platforms = enabled_platforms if enabled_platforms else ["reddit", "twitter"]
        has_reddit = "reddit" in platforms
        has_twitter = "twitter" in platforms

        if has_reddit and has_twitter:
            platform_instructions = (
                '**Reddit (60%)**: Discussion, advice-seeking\n'
                '- "anyone else", "how do you", "advice needed"\n\n'
                '**Twitter (30%)**: Venting, real-time frustration\n'
                '- "just spent", "every time", "why is"\n\n'
                '**Both (10%)**: Universal topics only'
            )
        elif has_reddit and not has_twitter:
            platform_instructions = (
                'All queries target **Reddit only**. Set platform to "reddit" for every query.\n\n'
                'Reddit-style language hints: "anyone else", "how do you", "advice needed", '
                '"is it worth", "should I", "does anyone"'
            )
        elif has_twitter and not has_reddit:
            platform_instructions = (
                'All queries target **Twitter/X only**. Set platform to "twitter" for every query.\n\n'
                'Twitter-style language hints: "just spent", "every time", "why is", '
                '"tired of", "can\'t believe", "so frustrated"'
            )
        else:
            # Neither enabled — fallback to both
            platform_instructions = (
                'Set platform to "both" for every query.\n'
                'Use general search language suitable for any platform.'
            )

        prompt = get_prompt(
            "query_generation",
            context_section=context_section,
            num_queries=num_queries,
            platform_instructions=platform_instructions,
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

            # Use centralized LLM service for plain text invocation
            content, _usage = LLMService.invoke_plain(
                prompt=prompt,
                temperature=0.7,
                timeout=120,
                model_name=settings.openai_model_name
            )

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
                    # Support current and legacy type names for backwards compatibility
                    valid_types = [
                        # Current archetypes (short universal prompt)
                        'pain', 'help', 'role', 'progress', 'discovery',
                        # Legacy archetypes (for backwards compatibility)
                        'workflow_friction', 'decision_paralysis', 'gap_limitation',
                        'comparative_frustration', 'temporal_threshold',
                        'problem', 'segment', 'question', 'tool', 'struggle'
                    ]
                    if q.get('type') not in valid_types:
                        q['type'] = 'pain'  # Default to pain expression type
                    q.setdefault('type', 'pain')
                    q.setdefault('platform', 'reddit')  # 60% target
                    q.setdefault('rationale', '')

                    # Calculate specificity score for debugging
                    q['specificity_score'] = self._calculate_specificity_score(q.get('query', ''))

                    valid_queries.append(q)

                if len(valid_queries) < len(queries):
                    logger.warning(f"Filtered out {len(queries) - len(valid_queries)} invalid queries")

                queries = valid_queries

                # Post-generation safety-net: filter queries targeting disabled platforms
                if enabled_platforms:
                    allowed = set(enabled_platforms) | {"both"}
                    before_count = len(queries)
                    queries = [q for q in queries if q.get("platform", "both") in allowed]
                    removed = before_count - len(queries)
                    if removed:
                        logger.warning(
                            f"Safety-net removed {removed} queries targeting disabled platforms "
                            f"(allowed: {sorted(allowed)})"
                        )

                logger.info(f"[OK] Generated {len(queries)} valid search queries")

                # Log each query at DEBUG level with rationale and specificity score
                logger.debug("Generated queries with rationale and specificity:")
                high_specificity_count = 0
                for i, q in enumerate(queries, 1):
                    score = q.get('specificity_score', 0)
                    if score >= 3:
                        high_specificity_count += 1
                    score_indicator = "✓" if score >= 3 else "⚠"
                    logger.debug(
                        f"  {i}. [{q.get('type', 'unknown')}|{q.get('platform', 'reddit')}] "
                        f"(spec:{score}/5 {score_indicator}) {q.get('query', 'N/A')}\n"
                        f"     Rationale: {q.get('rationale', 'N/A')}"
                    )

                # Log specificity distribution
                specificity_pct = (high_specificity_count / len(queries) * 100) if queries else 0
                logger.info(f"  Specificity: {high_specificity_count}/{len(queries)} queries scored 3+/5 ({specificity_pct:.0f}%)")

                # Validate queries semantically (log warnings for suspicious patterns)
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
                    generic_terms = ['problems', 'struggles', 'challenges', 'issues', 'difficulties']
                    if any(term in query_text for term in generic_terms):
                        if spec_score < 2:  # Only warn if combined with low specificity
                            logger.warning(f"[WARN] Generic term with low specificity: {q.get('query')}")
                            suspicious_count += 1

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

                    # Check for solution-seeking patterns (should find problems, not solutions)
                    solution_patterns = [
                        'best ', 'recommended', 'top ', 'how to solve',
                        'tool for', 'app for', 'software for', 'alternative to'
                    ]
                    if any(pat in query_text for pat in solution_patterns):
                        logger.warning(f"[WARN] Solution-seeking query (should find problems, not solutions): {q.get('query')}")
                        suspicious_count += 1

                if suspicious_count > 0:
                    logger.warning(f"[WARN] Found {suspicious_count} suspicious queries - review rationales above")
                if low_specificity_count > len(queries) * 0.2:  # More than 20% low specificity
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
            logger.error(f"Unexpected error in query generation: {e}", exc_info=True)
            return []

    def generate_all_platform_queries(
        self,
        niche_description: str,
        niche_context: "NicheContext | None" = None,
        enabled_platforms: list[str] | None = None,
    ) -> list[dict]:
        """Generate queries for all enabled platforms in parallel.

        Each platform gets a focused prompt optimized for its search backend:
        - Reddit: existing pain-expression prompt (proven, unchanged)
        - HN: keyword-focused for Algolia (neutral, 2-4 words)
        - YouTube: tutorial/how-to for Google (conversational, 3-6 words)
        - Twitter: shares Reddit queries

        Returns combined list with 'platform' field set on each query.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        platforms = set(enabled_platforms or ["reddit"])
        tasks: dict[str, callable] = {}

        # Reddit: existing generator
        reddit_platforms = []
        if "reddit" in platforms:
            reddit_platforms.append("reddit")
        if "twitter" in platforms:
            reddit_platforms.append("twitter")
        if reddit_platforms:
            tasks["reddit"] = lambda: self.generate_queries(
                niche_description, niche_context,
                num_queries=settings.num_search_queries,
                enabled_platforms=reddit_platforms,
            )

        # HN: new focused generator
        if "hackernews" in platforms:
            tasks["hackernews"] = lambda: self._generate_platform_queries(
                "hn_query_generation", niche_description, niche_context,
                num_queries=8, platform="hackernews",
            )

        # YouTube: new focused generator
        if "youtube" in platforms:
            tasks["youtube"] = lambda: self._generate_platform_queries(
                "yt_query_generation", niche_description, niche_context,
                num_queries=8, platform="youtube",
            )

        # Run in parallel (3 LLM calls, wall time ≈ 1 call)
        all_queries: list[dict] = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                platform_name = futures[future]
                try:
                    queries = future.result()
                    for q in queries:
                        if platform_name != "reddit":
                            q["platform"] = platform_name
                    all_queries.extend(queries)
                    logger.info(f"[QueryGen] {platform_name}: generated {len(queries)} queries")
                except Exception as exc:
                    logger.warning(f"[QueryGen] {platform_name} generation failed (non-fatal): {exc}")

        logger.info(f"[QueryGen] Total: {len(all_queries)} queries across {len(tasks)} platforms")
        return all_queries

    def _generate_platform_queries(
        self,
        prompt_name: str,
        niche_description: str,
        niche_context: "NicheContext | None" = None,
        num_queries: int = 8,
        platform: str = "hackernews",
    ) -> list[dict]:
        """Generate queries using a platform-specific prompt.

        Thin wrapper: loads YAML prompt, calls LLM, parses JSON.
        No specificity scoring (Reddit-centric, irrelevant for HN/YouTube).
        """
        # Build context section (same as Reddit generator)
        if niche_context:
            sanitized_description = self._sanitize_for_prompt(niche_context.niche_description)
            sanitized_segments = [self._sanitize_for_prompt(seg, max_length=500) for seg in niche_context.market_segments]
            segments_formatted = "\n".join([f"{i+1}. {seg}" for i, seg in enumerate(sanitized_segments)])
            context_section = f"""
**NICHE CONTEXT:**

Niche Description: {sanitized_description}

Market Segments:
{segments_formatted}
"""
        else:
            sanitized_niche = self._sanitize_for_prompt(niche_description)
            context_section = f"""
**NICHE CONTEXT:**

Niche Description: {sanitized_niche}
"""

        prompt = get_prompt(
            prompt_name,
            context_section=context_section,
            num_queries=num_queries,
        )

        logger.info(f"[QueryGen] Generating {num_queries} {platform} queries...")
        logger.debug(f"[QueryGen] {platform} prompt:\n{prompt[:300]}...")

        content, _usage = LLMService.invoke_plain(
            prompt=prompt,
            temperature=0.7,
            timeout=60,
            model_name=settings.openai_model_name,
        )

        queries = self._extract_json_array(content)
        if not queries:
            logger.warning(f"[QueryGen] {platform}: no valid JSON from LLM response")
            return []

        # Minimal validation (no specificity scoring for HN/YouTube)
        valid = []
        for q in queries:
            if not isinstance(q, dict) or "query" not in q:
                continue
            q.setdefault("type", "topic")
            q["platform"] = platform
            valid.append(q)

        logger.info(f"[QueryGen] {platform}: {len(valid)} valid queries")
        return valid
