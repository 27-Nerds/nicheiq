"""
LLM-based search query generator for finding niche pain points.

Generates strategic search queries using context-aware prompting.
"""

import json
import math
import re
from typing import TYPE_CHECKING

from loguru import logger

from ...config.settings import settings
from ..llm_service import LLMService
from ..parsing.json_extractor import extract_json_array_from_text
from ..prompts import get_prompt
from ..validation.niche_anchor import (
    build_anchor_matchers,
    format_anchor_block,
    text_has_anchor,
)

if TYPE_CHECKING:
    from ...models.research_state import NicheContext

class QueryGenerator:
    """LLM-based search query generator for finding niche pain points."""

    # Anchor-grounding is "active" only with enough named entities to be
    # meaningful; below this every anchor gate is a no-op (fail-open).
    MIN_ANCHORS_ACTIVE = 3
    # Entity-anchor floor DISABLED (0.0). Forcing >=50% of queries to contain a NAMED
    # entity caused PRODUCT LOCK-IN: the search pre-committed the whole research to the
    # entities Stage-1 happened to list, blinding it to unlisted compounds/vendors and
    # category-level pains. Drift is still prevented by the disambiguation_exclusions drop
    # (below) + the prompt's required niche-domain anchor. has_anchor is still tagged for
    # telemetry; the regeneration that "strengthened entity anchoring" no longer fires.
    ANCHOR_PCT_FLOOR = 0.0

    def __init__(self):
        # Per-run telemetry consumed by the flow for the Phase-4 drift caveat.
        self.anchor_telemetry: dict = {}

    def _anchors_active(self, niche_context: "NicheContext | None") -> bool:
        return bool(
            niche_context
            and len(getattr(niche_context, "anchor_entities", []) or []) >= self.MIN_ANCHORS_ACTIVE
        )

    def _apply_anchor_drift_guard(
        self, queries: list[dict], niche_context: "NicheContext | None"
    ) -> tuple[list[dict], float, int]:
        """Drop off-niche queries and tag anchored ones (code-level enforcement).

        - Drops any query whose text matches a `disambiguation_exclusions` term
          (word-boundary/stem, never naive substring).
        - Tags each surviving query with `has_anchor` (contains an anchor entity).
        Returns (kept_queries, anchor_pct_of_non_discovery, dropped_count).
        No-op (returns unchanged, anchor_pct=1.0) when anchors are inactive.
        """
        if not self._anchors_active(niche_context):
            return queries, 1.0, 0

        entity_matchers = build_anchor_matchers(niche_context.anchor_entities)
        exclusion_matchers = build_anchor_matchers(niche_context.disambiguation_exclusions)

        kept: list[dict] = []
        dropped = 0
        for q in queries:
            text = q.get("query", "")
            if exclusion_matchers and text_has_anchor(text, exclusion_matchers):
                logger.warning(f"[DRIFT] Dropped off-niche query (exclusion term): {text}")
                dropped += 1
                continue
            q["has_anchor"] = text_has_anchor(text, entity_matchers)
            kept.append(q)

        # Entity-anchor quota applies to NON-discovery queries (discovery is
        # intentionally open-ended and exempt).
        non_discovery = [q for q in kept if q.get("type") != "discovery"]
        if non_discovery:
            anchor_pct = sum(1 for q in non_discovery if q.get("has_anchor")) / len(non_discovery)
        else:
            anchor_pct = 1.0
        return kept, anchor_pct, dropped

    # Product-name shape: a capitalized token carrying a digit (BPC-157, MK-677, TB-500, IGF-1).
    _PRODUCT_RE = re.compile(r"\b[A-Z][A-Za-z]*[- ]?\d[\dA-Za-z-]*\b")

    def _cap_named_entities(
        self, queries: list[dict], niche_context: "NicheContext | None", niche_description: str
    ) -> list[dict]:
        """Enforce the product-lock-in ceiling (settings.query_named_entity_cap).

        A query is "product-named" when it names a specific entity BEYOND the niche's own identity:
        a product-shaped token (caps+digit) or a Stage-1 `anchor_entity`, EXCLUDING any term that
        appears in the niche text itself (so naming the niche's game/market — e.g. "Dota 2", "CS2"
        — is never penalized; only true product lock-in like peptide compounds is). Drops the excess
        named queries so the search isn't pre-committed to the products Stage-1 happened to list.
        """
        cap = settings.query_named_entity_cap
        if not queries or cap >= 1.0:
            return queries
        niche_lc = (niche_description or "").lower() + " " + (
            getattr(niche_context, "niche_description", "") or "").lower()
        anchors_lc = [a.lower() for a in (getattr(niche_context, "anchor_entities", None) or [])
                      if a.lower() not in niche_lc]

        def is_product(q: dict) -> bool:
            text = q.get("query", "")
            if any(m.lower() not in niche_lc for m in self._PRODUCT_RE.findall(text)):
                return True
            tl = text.lower()
            return any(a in tl for a in anchors_lc)

        prod_idx = [i for i, q in enumerate(queries) if is_product(q)]
        n, p = len(queries), len(prod_idx)
        if p <= math.floor(cap * n):
            return queries
        # Closed form: drop d named queries so (p-d)/(n-d) <= cap (denominator-shrink aware).
        d = math.ceil((p - cap * n) / (1.0 - cap))
        drop = set(prod_idx[-d:])  # drop the later named queries; keep the earlier, more-diverse ones
        kept = [q for i, q in enumerate(queries) if i not in drop]
        logger.info(f"[LOCK-IN] named-entity queries {p}/{n} over cap {cap:.0%} — dropped {d}")
        return kept

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

    def _audience_focus_block(self, target_audience: str, allotment: int) -> str:
        """Part C: a SOFT, ADDITIVE audience block appended to the query-gen context.

        Returns an instruction reserving exactly `allotment` of the requested queries
        for the audience while keeping the broad set unchanged. Empty string if no
        audience. The audience text is sanitized for prompt safety.
        """
        if not target_audience:
            return ""
        safe = self._sanitize_for_prompt(target_audience, max_length=200)
        return (
            "\n\n**ADDITIONAL AUDIENCE QUERIES (additive — the broad set above is "
            "unchanged):**\n\n"
            f'The user is building for "{safe}". Reserve EXACTLY {allotment} of the '
            "requested queries for this audience — phrased the way they actually talk "
            "(their communities, jargon, experience level) — and keep ALL the others "
            "broad across the niche above. Each audience query MUST still reference the "
            "niche (an anchor or niche term) so it stays on-topic. Do NOT reduce or "
            "replace the broad queries."
        )

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
        target_audience: str | None = None,
        _is_retry: bool = False,
    ) -> list[dict]:
        """
        Generate strategic search queries for a niche using LLM.

        Args:
            niche_description: Description of the niche to generate queries for
            niche_context: Optional structured context with market segments and boundaries
            num_queries: Number of queries to generate
            enabled_platforms: List of enabled platforms (e.g. ["reddit", "twitter"]).
                None means all platforms enabled (backward compatible).
            target_audience: Part C optional soft bias. When set, `audience_query_allotment`
                extra audience-flavored queries are added ON TOP of `num_queries` (additive,
                broad set preserved). None = fully broad (default).

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
{format_anchor_block(niche_context)}"""
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

        # On a regeneration retry, prepend a stronger entity-anchoring directive.
        if _is_retry and self._anchors_active(niche_context):
            context_section = (
                "**RETRY — STRENGTHEN NICHE ANCHORING:** the previous attempt was "
                "insufficiently anchored. At least 50% of non-discovery queries MUST "
                "contain one of the ANCHOR ENTITIES verbatim, and NONE may reference "
                "the OUT-OF-SCOPE topics.\n" + context_section
            )

        # Part C: soft, ADDITIVE audience bias. Bump the requested count by the
        # allotment so audience queries are added ON TOP of the broad set (never
        # displace it), and append the audience block to the context.
        effective_num_queries = num_queries
        if target_audience:
            allotment = settings.audience_query_allotment
            effective_num_queries = num_queries + allotment
            context_section = context_section + self._audience_focus_block(target_audience, allotment)

        prompt = get_prompt(
            "query_generation",
            context_section=context_section,
            num_queries=effective_num_queries,
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
                        # Balanced-discovery intents (v2 prompt)
                        'neutral', 'problem', 'satisfaction', 'solved', 'past', 'discovery',
                        # Current archetypes (legacy short universal prompt)
                        'pain', 'help', 'role', 'progress',
                        # Legacy archetypes (for backwards compatibility)
                        'workflow_friction', 'decision_paralysis', 'gap_limitation',
                        'comparative_frustration', 'temporal_threshold',
                        'segment', 'question', 'tool', 'struggle'
                    ]
                    if q.get('type') not in valid_types:
                        q['type'] = 'neutral'  # Default to NEUTRAL (not 'pain' — avoids re-biasing unknown types)
                    q.setdefault('type', 'neutral')
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

                    # Solution-seeking is INTENTIONAL for the 'solved' disconfirming intent
                    # (it reveals the pain may already be met). Only flag it for other types.
                    solution_patterns = [
                        'best ', 'recommended', 'top ', 'how to solve',
                        'tool for', 'app for', 'software for', 'alternative to'
                    ]
                    if q.get('type') != 'solved' and any(pat in query_text for pat in solution_patterns):
                        logger.warning(f"[WARN] Solution-seeking query (should find problems, not solutions): {q.get('query')}")
                        suspicious_count += 1

                if suspicious_count > 0:
                    logger.warning(f"[WARN] Found {suspicious_count} suspicious queries - review rationales above")
                if low_specificity_count > len(queries) * 0.2:  # More than 20% low specificity
                    logger.warning(f"[WARN] {low_specificity_count}/{len(queries)} queries have low specificity (<3/5)")

                # Code-level anchor drift guard: drop off-niche queries, tag anchored
                # ones, and record telemetry for the Phase-4 caveat.
                queries, anchor_pct, dropped = self._apply_anchor_drift_guard(queries, niche_context)
                if self._anchors_active(niche_context):
                    self.anchor_telemetry = {
                        "query_anchor_pct": round(anchor_pct, 3),
                        "dropped_offniche_queries": dropped,
                    }
                    logger.info(
                        f"[DRIFT] {anchor_pct:.0%} of non-discovery queries anchored; "
                        f"dropped {dropped} off-niche"
                    )

                    # Single regeneration when anchoring is too weak (real drift risk).
                    if anchor_pct < self.ANCHOR_PCT_FLOOR and not _is_retry:
                        logger.warning(
                            f"[DRIFT] anchor_pct={anchor_pct:.0%} below "
                            f"{self.ANCHOR_PCT_FLOOR:.0%} — regenerating once with "
                            f"strengthened entity anchoring"
                        )
                        retry = self.generate_queries(
                            niche_description, niche_context, num_queries,
                            enabled_platforms, target_audience=target_audience,
                            _is_retry=True,
                        )
                        # Merge: keep all anchored queries from both attempts, then
                        # top up with non-anchored ones, deduped by query text.
                        merged: dict[str, dict] = {}
                        for q in sorted(queries + retry,
                                        key=lambda x: x.get("has_anchor", False), reverse=True):
                            merged.setdefault(q.get("query", "").strip().lower(), q)
                        queries = list(merged.values())[:effective_num_queries]

                # Product-lock-in ceiling: keep the search from pre-committing to Stage-1's
                # named entities (the majority must stay category-level for honest discovery).
                queries = self._cap_named_entities(queries, niche_context, niche_description)

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
        target_audience: str | None = None,
    ) -> list[dict]:
        """Generate queries for all enabled platforms in parallel.

        Each platform gets a focused prompt optimized for its search backend:
        - Reddit: existing pain-expression prompt (proven, unchanged)
        - HN: keyword-focused for Algolia (neutral, 2-4 words)
        - YouTube: tutorial/how-to for Google (conversational, 3-6 words)
        - Twitter: shares Reddit queries

        target_audience (Part C): when set, each platform additionally gets a soft,
        additive audience bias — the broad set is preserved (never narrowed).

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
                target_audience=target_audience,
            )

        # HN: new focused generator
        if "hackernews" in platforms:
            tasks["hackernews"] = lambda: self._generate_platform_queries(
                "hn_query_generation", niche_description, niche_context,
                num_queries=8, platform="hackernews",
                target_audience=target_audience,
            )

        # YouTube: new focused generator
        if "youtube" in platforms:
            tasks["youtube"] = lambda: self._generate_platform_queries(
                "yt_query_generation", niche_description, niche_context,
                num_queries=8, platform="youtube",
                target_audience=target_audience,
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
        target_audience: str | None = None,
    ) -> list[dict]:
        """Generate queries using a platform-specific prompt.

        Thin wrapper: loads YAML prompt, calls LLM, parses JSON.
        No specificity scoring (Reddit-centric, irrelevant for HN/YouTube).

        target_audience (Part C): when set, adds `audience_query_allotment` extra
        audience-flavored slots on top of `num_queries` (additive, broad set kept).
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
{format_anchor_block(niche_context)}"""
        else:
            sanitized_niche = self._sanitize_for_prompt(niche_description)
            context_section = f"""
**NICHE CONTEXT:**

Niche Description: {sanitized_niche}
"""

        # Part C: soft, ADDITIVE audience bias (same contract as the Reddit path).
        effective_num_queries = num_queries
        if target_audience:
            allotment = settings.audience_query_allotment
            effective_num_queries = num_queries + allotment
            context_section = context_section + self._audience_focus_block(target_audience, allotment)

        prompt = get_prompt(
            prompt_name,
            context_section=context_section,
            num_queries=effective_num_queries,
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

        # Anchor drift guard (drop off-niche queries; tag anchored). No regen here.
        valid, _pct, dropped = self._apply_anchor_drift_guard(valid, niche_context)
        if dropped:
            logger.info(f"[QueryGen] {platform}: dropped {dropped} off-niche queries")

        logger.info(f"[QueryGen] {platform}: {len(valid)} valid queries")
        return valid
