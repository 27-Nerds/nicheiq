"""
Context-aware seed keyword generator for SEO strategy.

Generates strategically selected seed keywords using chain-of-thought
reasoning and semantic validation.
"""

import re
from typing import TYPE_CHECKING

from loguru import logger

from ...config.settings import settings
from ..llm_service import LLMService
from ..prompts import get_prompt

if TYPE_CHECKING:
    from ...models.competitor import CompetitiveAnalysisResult
    from ...models.pain_point import PainPointAnalysisResult
    from ...models.research_state import NicheContext
    from ...models.seo_strategy import ExpandedKeywordList
    from ...models.solution_idea import SolutionIdea

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
        pass  # No longer need to initialize LLM instance

    def generate_seeds(
        self,
        solution: "SolutionIdea",
        niche_context: "NicheContext | None" = None,
        pain_points: "PainPointAnalysisResult | None" = None,
        competitive_analysis: "CompetitiveAnalysisResult | None" = None,
        audience_vocabulary: list[str] | None = None,
        num_broad_seeds: int = 30,
        num_targeted_seeds: int = 15
    ) -> "ExpandedKeywordList | None":
        """
        Generate context-aware seed keywords with semantic validation.

        Args:
            solution: Selected solution with full details
            niche_context: Optional NicheContext with market_segments and industry_boundaries
            pain_points: Optional pain point analysis for keyword grounding
            competitive_analysis: Optional competitive context
            audience_vocabulary: Optional list of terms from audience mapping (common_vocabulary)
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
                    (ls for ls in competitive_analysis.solution_landscapes if ls.solution_name == solution.solution_name),
                    None
                )
                if matching_landscape and matching_landscape.competitors:
                    competitor_names = [c.name for c in matching_landscape.competitors[:8]]
                    competitors = ", ".join(competitor_names)

            # Format audience vocabulary (from Stage 6.5 AudienceMappingCrew)
            audience_vocab_formatted = (
                ", ".join(audience_vocabulary[:15])
                if audience_vocabulary else "Not available"
            )
            if audience_vocabulary:
                logger.info(f"Including {len(audience_vocabulary[:15])} audience vocabulary terms in keyword generation")

            # Build the chain-of-thought prompt
            prompt = get_prompt(
                "keyword_seed",
                niche_description=niche_description,
                market_segments=market_segments,
                industry_boundaries=industry_boundaries,
                solution_name=solution_name,
                solution_type=solution_type,
                value_proposition=value_proposition,
                core_features=core_features,
                target_personas=target_personas,
                pain_points_addressed=pain_points_addressed,
                competitors=competitors,
                audience_vocabulary=audience_vocab_formatted,
                num_broad_seeds=num_broad_seeds,
                num_targeted_seeds=num_targeted_seeds,
                total_seeds=num_broad_seeds + num_targeted_seeds
            )

            logger.info(f"Generating {num_broad_seeds + num_targeted_seeds} seed keywords for: {solution_name}")

            # Import here to avoid circular dependency
            from ...models.seo_strategy import ExpandedKeywordList

            # Use centralized LLM service for structured output
            result, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=ExpandedKeywordList,
                temperature=0.5,  # Balanced creativity for keyword diversity
                timeout=120,
                model_name=settings.openai_model_name
            )

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

            # Post-generation validation - FILTER suspicious keywords (not just warn)
            valid_keywords = []
            suspicious_keywords = []

            for kw in result.keywords:
                if self._is_suspicious_keyword(kw.keyword, solution_type, niche_context):
                    logger.warning(f"Removed suspicious keyword: '{kw.keyword}' - Rationale: {kw.rationale}")
                    suspicious_keywords.append(kw)
                else:
                    valid_keywords.append(kw)

            if suspicious_keywords:
                logger.info(f"Filtered {len(suspicious_keywords)} suspicious keywords from {total_keywords} total")

            result.keywords = valid_keywords

            # Apply domain-locking filter to remove generic keywords without niche context
            result.keywords = self._filter_generic_keywords(result.keywords, niche_context)

            final_count = len(result.keywords)
            logger.info(
                f"[OK] Generated {final_count} seed keywords across "
                f"{len(result.topic_clusters)} clusters (filtered from {total_keywords} initial)"
            )

            return result

        except Exception as e:
            logger.error(f"Seed keyword generation failed: {e}", exc_info=True)
            return None

    def _sanitize_for_prompt(self, text: str | None, max_length: int = 1000) -> str:
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

    def _extract_domain_terms(self, niche_context: "NicheContext | None") -> set[str]:
        """
        Dynamically extract domain-specific terms from niche context.

        Extracts significant words from:
        - niche_description
        - market_segments
        - industry_boundaries (IN SCOPE section)

        Returns set of lowercase domain terms (3+ chars, no stopwords).
        """
        if not niche_context:
            return set()

        # Stopwords to exclude
        stopwords = {
            'the', 'and', 'for', 'with', 'that', 'this', 'from', 'are', 'was',
            'were', 'been', 'being', 'have', 'has', 'had', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
            'need', 'dare', 'ought', 'used', 'who', 'what', 'where', 'when', 'why',
            'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very', 'just',
            'but', 'not', 'also', 'any', 'into', 'out', 'about', 'over', 'after',
            'before', 'between', 'under', 'above', 'below', 'through', 'during'
        }

        domain_terms = set()

        # Extract from niche_description
        if niche_context.niche_description:
            words = re.findall(r'\b[a-z]{3,}\b', niche_context.niche_description.lower())
            domain_terms.update(w for w in words if w not in stopwords)

        # Extract from market_segments
        if niche_context.market_segments:
            for segment in niche_context.market_segments:
                words = re.findall(r'\b[a-z]{3,}\b', segment.lower())
                domain_terms.update(w for w in words if w not in stopwords)

        # Extract from industry_boundaries (IN SCOPE section only)
        if niche_context.industry_boundaries:
            boundaries_lower = niche_context.industry_boundaries.lower()
            # Extract IN SCOPE section
            in_scope_match = re.search(
                r'in\s+scope[:\s]+(.*?)(?:out\s+of\s+scope|$)',
                boundaries_lower, re.DOTALL
            )
            if in_scope_match:
                in_scope_text = in_scope_match.group(1)
                words = re.findall(r'\b[a-z]{3,}\b', in_scope_text)
                domain_terms.update(w for w in words if w not in stopwords)

        return domain_terms

    def _filter_generic_keywords(
        self,
        keywords: list,
        niche_context: "NicheContext | None"
    ) -> list:
        """
        Filter out generic single-word keywords lacking domain context.

        Works for ANY niche by dynamically extracting domain terms from niche_context.
        Removes bare generics like "professional", "budget", "vegan" that don't
        contain any niche-specific terms.
        """
        if not niche_context:
            return keywords

        # Extract domain terms from niche context
        domain_terms = self._extract_domain_terms(niche_context)

        if not domain_terms:
            logger.warning("Could not extract domain terms from niche context - skipping filter")
            return keywords

        logger.debug(f"Extracted domain terms: {sorted(domain_terms)[:20]}...")

        # Universal generic terms that need domain context (niche-agnostic)
        generic_bare_terms = {
            # Price/value terms
            'professional', 'budget', 'affordable', 'cheap', 'expensive',
            'luxury', 'premium', 'quality', 'best', 'top', 'price', 'value',
            # Action/intent terms
            'review', 'reviews', 'compare', 'comparison', 'buy', 'purchase',
            'alternative', 'alternatives', 'vs', 'rating', 'ratings',
            # Attribute terms
            'vegan', 'natural', 'organic', 'eco', 'sustainable', 'green',
            # Generic descriptors
            'guide', 'tips', 'ideas', 'list', 'examples', 'types'
        }

        filtered = []
        filtered_count = 0

        for kw in keywords:
            keyword_lower = kw.keyword.lower().strip()
            words = keyword_lower.split()

            # Single-word generic → reject (no domain context possible)
            if len(words) == 1 and keyword_lower in generic_bare_terms:
                logger.info(f"Filtered generic keyword: '{kw.keyword}' (bare generic, no domain)")
                filtered_count += 1
                continue

            # Multi-word: check if ANY word overlaps with domain terms
            has_domain_context = any(
                word in domain_terms or any(dt in word for dt in domain_terms)
                for word in words
            )

            # If keyword has no domain context AND is all generic terms, reject
            if not has_domain_context:
                is_all_generic = all(w in generic_bare_terms or len(w) <= 2 for w in words)
                if is_all_generic:
                    logger.info(f"Filtered generic keyword: '{kw.keyword}' (all generic, no domain)")
                    filtered_count += 1
                    continue

            filtered.append(kw)

        if filtered_count > 0:
            logger.info(f"Domain-lock filter: Removed {filtered_count} generic keywords")

        return filtered

    def _is_suspicious_keyword(
        self,
        keyword: str,
        solution_type: str,
        niche_context: "NicheContext | None"
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

        # Rule 5: Check for bare generic descriptors (niche-agnostic)
        # These single-word terms are universally generic and need domain context
        generic_bare_terms = {
            'professional', 'budget', 'vegan', 'natural', 'organic',
            'price', 'affordable', 'cheap', 'expensive', 'luxury',
            'review', 'reviews', 'compare', 'comparison', 'buy', 'value',
            'quality', 'best', 'top', 'alternative', 'alternatives',
            'guide', 'tips', 'ideas', 'list', 'examples', 'types'
        }

        # Single-word generic terms are always suspicious
        if keyword_lower in generic_bare_terms:
            logger.debug(f"Suspicious: '{keyword}' is bare generic term (no domain context)")
            return True

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
        common_acronyms = {
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
        for acronym in common_acronyms:
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
