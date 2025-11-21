"""
Seed generation utilities for Stage 8.8 keyword research.

Contains strategies for generating seed keywords for DataForSEO expansion.
"""

from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..tools.dataforseo_tool import DataForSEOBaseClient
from .keyword_filtering import filter_single_word_keywords
from .prompts import load_prompt

if TYPE_CHECKING:
    from ..models.pain_point import PainPointAnalysisResult
    from ..models.research_state import NicheContext, ResearchState
    from ..models.solution_idea import SolutionIdea

# Pydantic model for structured LLM output
from pydantic import BaseModel, Field


class KeywordSeedResult(BaseModel):
    """Structured output model for LLM seed generation."""
    seeds: list[str] = Field(description="List of seed keywords")

SEED_GENERATION_PROMPT = load_prompt("seed_generation")

class SeedGenerator:
    """
    Generates seed keywords for DataForSEO expansion using multiple strategies.

    Encapsulates all seed generation logic from Stage 8.8 of the research flow.
    """

    def __init__(
        self,
        state: "ResearchState",
        niche_context: "NicheContext | None" = None,
        pain_point_analysis: "PainPointAnalysisResult | None" = None
    ):
        """
        Initialize SeedGenerator with research state context.

        Args:
            state: ResearchState object with flow state
            niche_context: Optional NicheContext (extracted from state if not provided)
            pain_point_analysis: Optional PainPointAnalysisResult (extracted from state if not provided)
        """
        self.state = state
        self.niche_context = niche_context or getattr(state, 'niche_context', None)
        self.pain_point_analysis = pain_point_analysis or getattr(state, 'pain_point_analysis', None)

    def generate_hybrid_seeds(
        self,
        solution: "SolutionIdea",
        count: int = 20
    ) -> list[str]:
        """
        Generate hybrid keyword seeds combining KeywordSeedGenerator + LLM creativity.

        Strategy:
        - 10 seeds from KeywordSeedGenerator (context-aware, semantic validation)
        - 10 seeds from LLM creative generation (diverse patterns)
        - Combine and deduplicate

        Args:
            solution: SolutionIdea object with description, features, pain points
            count: Target number of seeds (default: 20)

        Returns:
            List of unique seed keywords (up to count)
        """
        from .generation import KeywordSeedGenerator

        all_seeds = []

        # Method 1: KeywordSeedGenerator (context-aware with semantic validation)
        try:
            logger.info(f"[Stage 8.8] Generating KeywordSeedGenerator seeds for {solution.solution_name}")
            generator = KeywordSeedGenerator()

            # Try to get competitive analysis for this specific solution
            competitive_analysis = None
            if hasattr(solution, 'competitive_landscape') and solution.competitive_landscape:
                from ..models.competitor import CompetitiveAnalysisResult
                competitive_analysis = CompetitiveAnalysisResult(
                    solution_landscapes=[solution.competitive_landscape]
                )

            # Generate 10 seeds (6 broad + 4 targeted)
            result = generator.generate_seeds(
                solution=solution,
                niche_context=self.niche_context,
                pain_points=self.pain_point_analysis,
                competitive_analysis=competitive_analysis,
                num_broad_seeds=6,
                num_targeted_seeds=4
            )

            if result and result.keywords:
                generator_seeds = [kw.keyword for kw in result.keywords[:10]]
                all_seeds.extend(generator_seeds)
                logger.info(
                    f"[Stage 8.8] KeywordSeedGenerator produced {len(generator_seeds)} seeds: "
                    f"{generator_seeds[:3]}..."
                )
            else:
                logger.warning("[Stage 8.8] KeywordSeedGenerator returned no results - will rely on LLM seeds")

        except Exception as e:
            logger.warning(
                f"[Stage 8.8] KeywordSeedGenerator failed: {str(e)} - "
                f"falling back to LLM-only seeds"
            )

        # Method 2: LLM Creative Generation (diverse patterns)
        try:
            logger.info(f"[Stage 8.8] Generating LLM creative seeds for {solution.solution_name}")
            llm_seeds = self.generate_llm_seeds(solution, count=10)

            if llm_seeds:
                all_seeds.extend(llm_seeds)
                logger.info(
                    f"[Stage 8.8] LLM creative generation produced {len(llm_seeds)} seeds: "
                    f"{llm_seeds[:3]}..."
                )
            else:
                logger.warning("[Stage 8.8] LLM seed generation returned no results")

        except Exception as e:
            logger.error(f"[Stage 8.8] LLM seed generation failed: {str(e)}")

        # Combine and deduplicate
        unique_seeds = list(dict.fromkeys(all_seeds))

        # Handle fallback scenarios
        if not unique_seeds:
            logger.error(
                f"[Stage 8.8] Both seed generation methods failed for {solution.solution_name} - "
                f"using minimal fallback"
            )
            fallback = [
                solution.solution_name.lower(),
                f"{solution.project_type or 'platform'} for {solution.solution_name.lower()}",
            ]
            unique_seeds = fallback

        # Truncate or pad to target count
        if len(unique_seeds) > count:
            unique_seeds = unique_seeds[:count]
            logger.info(f"[Stage 8.8] Truncated to {count} unique seeds")
        elif len(unique_seeds) < count:
            logger.info(
                f"[Stage 8.8] Generated {len(unique_seeds)} unique seeds "
                f"(target: {count}) - proceeding with available seeds"
            )

        logger.info(
            f"[Stage 8.8] Hybrid seed generation complete: {len(unique_seeds)} unique seeds "
            f"from {len(all_seeds)} total (including duplicates)"
        )

        return unique_seeds

    def generate_seeds_with_strategy(
        self,
        solution: "SolutionIdea",
        attempt: int,
        count: int = 20
    ) -> list[str]:
        """
        Generate seed keywords using different strategies based on attempt number.

        Implements adaptive pivot strategies:
        - Attempt 1: Hybrid (KeywordSeedGenerator + LLM)
        - Attempt 2: Competitor alternative keywords
        - Attempt 3: Pain point problem phrases
        - Attempt 4: Broader category + market segments

        Args:
            solution: SolutionIdea object
            attempt: Attempt number (1-4)
            count: Target number of seeds (default: 20)

        Returns:
            List of seed keywords
        """
        logger.info(f"[Stage 8.8] Generating seeds with strategy #{attempt}...")

        if attempt == 1:
            logger.debug("[Stage 8.8] Strategy: Hybrid (KeywordSeedGenerator + LLM)")
            return self.generate_hybrid_seeds(solution, count)

        elif attempt == 2:
            logger.debug("[Stage 8.8] Strategy: Competitor alternatives")
            return self.generate_competitor_alternative_seeds(solution, count)

        elif attempt == 3:
            logger.debug("[Stage 8.8] Strategy: Pain point problem queries")
            return self.generate_pain_point_seeds(solution, count)

        elif attempt == 4:
            logger.debug("[Stage 8.8] Strategy: Broader category combinations")
            return self.generate_category_broadening_seeds(solution, count)

        else:
            logger.warning(f"[Stage 8.8] Unknown attempt {attempt}, defaulting to hybrid")
            return self.generate_hybrid_seeds(solution, count)

    def generate_competitor_alternative_seeds(
        self,
        solution: "SolutionIdea",
        count: int = 20
    ) -> list[str]:
        """
        Generate competitor-focused seeds using actual competitor names.

        Strategy: Use actual competitor names + alternative/comparison modifiers.

        Args:
            solution: SolutionIdea object
            count: Target number of seeds

        Returns:
            List of competitor-focused seed keywords
        """
        seeds = []

        try:
            # Get competitors from solution's competitive landscape
            competitors = []
            if hasattr(solution, 'competitive_landscape') and solution.competitive_landscape:
                if (hasattr(solution.competitive_landscape, 'competitors') and
                    solution.competitive_landscape.competitors is not None):
                    competitors = [
                        c.name for c in solution.competitive_landscape.competitors[:10]
                        if c is not None and hasattr(c, 'name')
                    ]

            if not competitors:
                logger.warning("[Strategy 2] No competitors found, using fallback")
                category = solution.project_type or "platform"
                seeds = [
                    f"{category} alternatives",
                    f"best {category}",
                    f"top {category}",
                    f"{category} comparison",
                    f"compare {category}",
                ]
            else:
                # Pattern 1: Competitor alternatives (10-12 seeds)
                alternative_modifiers = ["alternative", "vs", "compared to", "better than", "alternative to"]
                for i, competitor in enumerate(competitors[:5]):
                    modifier = alternative_modifiers[i % len(alternative_modifiers)]
                    if modifier == "vs":
                        seeds.append(f"vs {competitor}")
                    else:
                        seeds.append(f"{competitor} {modifier}")

                # Pattern 2: Generic comparison keywords (5-8 seeds)
                category = solution.project_type or "platform"
                seeds.extend([
                    f"{category} comparison",
                    f"best {category} alternatives",
                    f"top {category} compared",
                    f"{competitors[0]} competitors",
                ])

            # Add solution category keywords for diversity
            if solution.core_features:
                for feature in solution.core_features[:5]:
                    seeds.append(f"{feature} alternatives")

            logger.debug(f"[Strategy 2] Generated {len(seeds)} competitor-alternative seeds")

        except Exception as e:
            logger.warning(f"[Strategy 2] Failed: {e}")
            category = solution.project_type or "platform"
            seeds = [f"{category} alternatives", f"best {category}", f"compare {category}"]

        unique_seeds = list(dict.fromkeys(seeds))
        return unique_seeds[:count]

    def generate_pain_point_seeds(
        self,
        solution: "SolutionIdea",
        count: int = 20
    ) -> list[str]:
        """
        Generate problem-based seeds from pain points.

        Strategy: Convert top pain points into search queries using problem language.

        Args:
            solution: SolutionIdea object
            count: Target number of seeds

        Returns:
            List of pain point-based seed keywords
        """
        seeds = []

        try:
            pain_points = None
            if self.pain_point_analysis:
                if hasattr(self.pain_point_analysis, 'pain_points'):
                    pain_points = self.pain_point_analysis.pain_points

            if not pain_points:
                logger.warning("[Strategy 3] No pain points found, using solution pain_points_addressed")
                if solution.pain_points_addressed:
                    pain_points_text = solution.pain_points_addressed[:10]
                else:
                    pain_points_text = []
            else:
                pain_points_sorted = sorted(
                    [p for p in pain_points if p is not None],
                    key=lambda p: getattr(p, 'severity_score', 0),
                    reverse=True
                )[:10]
                pain_points_text = [
                    p.title for p in pain_points_sorted
                    if p is not None and hasattr(p, 'title') and p.title is not None
                ]

            query_patterns = [
                "how to {}",
                "best way to {}",
                "solve {}",
                "{} solution",
                "fix {}",
                "{} help",
                "deal with {}",
            ]

            for pain_point in pain_points_text:
                clean_text = pain_point.lower().strip()
                clean_text = clean_text.replace("problem:", "").replace("issue:", "").strip()

                for pattern in query_patterns[:3]:
                    if "{}" in pattern:
                        seeds.append(pattern.format(clean_text))
                    else:
                        seeds.append(f"{pattern} {clean_text}")

            category = solution.project_type or "service"
            seeds.extend([
                f"problems with {category}",
                f"{category} challenges",
                f"{category} frustrations",
            ])

            logger.debug(f"[Strategy 3] Generated {len(seeds)} pain-point seeds")

        except Exception as e:
            logger.warning(f"[Strategy 3] Failed: {e}")
            category = solution.project_type or "service"
            seeds = [
                f"how to find {category}",
                f"best {category}",
                f"{category} help",
            ]

        unique_seeds = list(dict.fromkeys(seeds))
        return unique_seeds[:count]

    def generate_category_broadening_seeds(
        self,
        solution: "SolutionIdea",
        count: int = 20
    ) -> list[str]:
        """
        Generate broader category seeds using market segments.

        Strategy: Move up abstraction ladder to broader industry/category terms.

        Args:
            solution: SolutionIdea object
            count: Target number of seeds

        Returns:
            List of broader category seed keywords
        """
        seeds = []

        try:
            project_type = solution.project_type or "platform"

            category_hierarchy = {
                "saas": ["software", "tool", "platform", "system", "application"],
                "directory": ["directory", "list", "database", "catalog", "guide"],
                "aggregator": ["aggregator", "comparison", "search", "finder", "discovery"],
                "marketplace": ["marketplace", "platform", "exchange", "network"],
                "comparison-tool": ["comparison", "review", "ranking", "evaluation"],
            }

            broader_categories = category_hierarchy.get(project_type, ["platform", "service", "tool"])

            # Pattern 1: Broader category terms (5-8 seeds)
            for broad_cat in broader_categories[:5]:
                seeds.append(broad_cat)
                seeds.append(f"best {broad_cat}")

            # Pattern 2: Market segment combinations (8-12 seeds)
            if self.niche_context and hasattr(self.niche_context, 'market_segments'):
                for segment in self.niche_context.market_segments[:4]:
                    segment_words = segment.lower().split()[:3]
                    segment_phrase = " ".join(segment_words)

                    for broad_cat in broader_categories[:3]:
                        seeds.append(f"{segment_phrase} {broad_cat}")

            # Pattern 3: Industry vertical keywords (3-5 seeds)
            if solution.target_personas:
                for persona in solution.target_personas[:3]:
                    persona_clean = persona.lower().split()[0]
                    seeds.append(f"{persona_clean} {broader_categories[0]}")

            logger.debug(f"[Strategy 4] Generated {len(seeds)} category-broadening seeds")

        except Exception as e:
            logger.warning(f"[Strategy 4] Failed: {e}")
            seeds = [
                "software tool",
                "platform",
                "service",
                "best tool",
                "find tool",
            ]

        unique_seeds = list(dict.fromkeys(seeds))
        return unique_seeds[:count]

    def generate_llm_seeds(self, solution: "SolutionIdea", count: int = 10) -> list[str]:
        """
        Generate seed keywords using LLM with structured output.

        Args:
            solution: SolutionIdea object
            count: Number of seeds to generate (default: 10)

        Returns:
            List of seed keywords
        """
        try:
            structured_llm = ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.7,
                api_key=settings.openai_api_key
            ).with_structured_output(KeywordSeedResult)

            prompt_context = {
                "solution_name": solution.solution_name,
                "solution_description": solution.description,
                "core_features": ", ".join(solution.core_features[:5]) if solution.core_features else "Not specified",
                "target_personas": ", ".join(solution.target_personas[:3]) if solution.target_personas else "General users",
                "pain_points": "; ".join([
                    f"{pp.title} (Severity: {pp.severity_score}/10)"
                    for pp in self.pain_point_analysis.pain_points[:5]
                ]) if self.pain_point_analysis and self.pain_point_analysis.pain_points else "Not specified",
                "project_type": solution.project_type or "saas",
                "competitors": "None identified"
            }

            if hasattr(solution, 'competitive_landscape') and solution.competitive_landscape:
                if hasattr(solution.competitive_landscape, 'competitors') and solution.competitive_landscape.competitors:
                    prompt_context["competitors"] = ", ".join([
                        comp.name for comp in solution.competitive_landscape.competitors[:3]
                    ])

            seed_prompt = SEED_GENERATION_PROMPT.format(**prompt_context)

            result = structured_llm.invoke(seed_prompt)
            seed_keywords = result.seeds

            logger.info(f"[Stage 8.8] LLM generated {len(seed_keywords)} seeds for {solution.solution_name}")
            return seed_keywords

        except Exception as e:
            logger.error(f"[Stage 8.8] LLM seed generation failed: {str(e)}")
            return []

    def expand_seeds_quick(
        self,
        seeds: list[str],
        target_size: int = 50
    ) -> list[dict]:
        """
        Quick expansion of seeds for relevance testing.

        Expands top 5 diverse seeds to 50-100 keywords for fast relevance checking.

        Args:
            seeds: List of seed keywords
            target_size: Target number of expanded keywords (default: 50)

        Returns:
            List of keyword dicts from DataForSEO with search_volume, competition, etc.
        """
        if not seeds:
            logger.warning("[Quick Expansion] No seeds provided")
            return []

        try:
            dataforseo_tool = DataForSEOBaseClient()

            step = max(1, len(seeds) // 5)
            diverse_seeds = [seeds[i] for i in range(0, min(len(seeds), 20), step)][:5]

            logger.debug(
                f"[Quick Expansion] Selected {len(diverse_seeds)} diverse seeds from {len(seeds)} total"
            )
            logger.debug(f"[Quick Expansion] Seeds: {diverse_seeds}")

            expanded_keywords = dataforseo_tool.expand_keywords(
                seed_keywords=diverse_seeds,
                location_code=settings.target_location,
                max_results_per_batch=min(target_size // len(diverse_seeds), 100) if diverse_seeds else 50
            )

            logger.info(
                f"[Quick Expansion] Expanded {len(diverse_seeds)} seeds -> "
                f"{len(expanded_keywords)} keywords"
            )

            if len(expanded_keywords) > target_size:
                expanded_keywords = sorted(
                    expanded_keywords,
                    key=lambda x: x.get('search_volume', 0),
                    reverse=True
                )[:target_size]
                logger.debug(f"[Quick Expansion] Trimmed to top {target_size} by volume")

            return expanded_keywords

        except Exception as e:
            logger.warning(f"[Quick Expansion] Failed: {e}")
            return []

    def validate_seeds_with_dataforseo(self, seeds: list[str], solution_name: str) -> dict:
        """
        Validate seed keywords using DataForSEO keyword data.

        Args:
            seeds: List of seed keywords to validate
            solution_name: Name of the solution (for logging)

        Returns:
            dict with validation results including validated_count, total_volume, etc.
        """
        try:
            dataforseo_tool = DataForSEOBaseClient()

            keyword_data = dataforseo_tool.get_search_volume(
                keywords=seeds,
                location_code=settings.target_location
            )

            min_volume = getattr(settings, 'keyword_min_search_volume', 50)
            valid_keywords = [
                kw for kw in keyword_data
                if kw.get("search_volume", 0) >= min_volume
            ]

            valid_keywords = filter_single_word_keywords(valid_keywords, solution_name)

            total_volume = sum(kw.get("search_volume", 0) for kw in valid_keywords)
            keyword_count = len(valid_keywords)
            avg_competition = (
                sum(kw.get("competition_index", 0) for kw in valid_keywords) / max(keyword_count, 1)
            )

            top_keywords = sorted(
                valid_keywords,
                key=lambda x: x.get("search_volume", 0),
                reverse=True
            )[:5]

            geo_keywords = []
            geo_terms = ['spain', 'portugal', 'france', 'germany', 'uk', 'usa', 'canada', 'australia']
            for kw in valid_keywords:
                keyword_lower = kw.get('keyword', '').lower()
                if any(geo in keyword_lower for geo in geo_terms):
                    geo_keywords.append(kw)

            top_geo_keywords = sorted(
                geo_keywords,
                key=lambda x: x.get("search_volume", 0),
                reverse=True
            )[:3]

            volume_score = keyword_count / len(seeds) if seeds else 0

            opportunity_scores = []
            for kw in valid_keywords:
                volume = kw.get("search_volume", 0)
                competition = kw.get("competition_index", 0)

                volume_factor = min(volume / 1000, 1.0)
                competition_factor = 1 - (competition / 100)
                saturation_check = 1.0 if competition <= 60 else 0.7

                opp_score = volume_factor * competition_factor * saturation_check
                opportunity_scores.append(opp_score)

            avg_opportunity = sum(opportunity_scores) / max(len(opportunity_scores), 1)
            keyword_demand_score = (0.60 * volume_score) + (0.40 * avg_opportunity)

            if total_volume > 5000:
                demand_signal = "strong"
            elif total_volume > 2000:
                demand_signal = "moderate"
            else:
                demand_signal = "weak"

            validation_signals = {
                "has_search_demand": total_volume > 1000,
                "keyword_diversity": keyword_count >= 5,
                "high_volume_presence": any(kw.get("search_volume", 0) > 500 for kw in valid_keywords),
                "average_volume_per_keyword": total_volume / max(keyword_count, 1)
            }

            logger.info(
                f"[Stage 8.8] {solution_name} validation: "
                f"{total_volume:,} total volume, {keyword_count}/{len(seeds)} valid keywords, "
                f"demand score: {keyword_demand_score:.2f}"
            )

            return {
                "solution_name": solution_name,
                "validated_count": keyword_count,
                "total_volume": total_volume,
                "avg_competition": avg_competition,
                "keyword_demand_score": keyword_demand_score,
                "top_keywords": [
                    {
                        "keyword": kw.get("keyword", ""),
                        "volume": kw.get("search_volume", 0),
                        "competition": kw.get("competition_index", 0)
                    }
                    for kw in top_keywords
                ],
                "top_geographic_keywords": [kw.get("keyword", "") for kw in top_geo_keywords],
                "demand_signal": demand_signal,
                "validation_signals": validation_signals
            }

        except Exception as e:
            logger.error(f"[Stage 8.8] Validation error for {solution_name}: {str(e)}")
            return {
                "solution_name": solution_name,
                "validated_count": 0,
                "total_volume": 0,
                "avg_competition": 0.0,
                "keyword_demand_score": 0.0,
                "top_keywords": [],
                "top_geographic_keywords": [],
                "demand_signal": "weak",
                "validation_signals": {
                    "has_search_demand": False,
                    "keyword_diversity": False,
                    "high_volume_presence": False,
                    "average_volume_per_keyword": 0.0
                }
            }
