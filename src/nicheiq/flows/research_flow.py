"""
ResearchFlow - Main orchestration flow for the 10-stage market research pipeline.
Combines Flow-based orchestration with specialized Crews for complex analysis.
"""

from pathlib import Path
from typing import List, Optional
import asyncio
import json

from crewai.flow.flow import Flow, listen, start
from crewai.llm import LLM
from crewai_tools import SerperDevTool
from loguru import logger
from pydantic import ValidationError

from ..config.settings import settings
from ..crews import CompetitiveCrew, IdeaGenerationCrew, PainPointCrew
from ..models.research_state import FinalReport, ResearchState
from ..tools.dataforseo_tool import DataForSEOTool
from ..tools.reddit_tool import RedditCollectorTool
from ..tools.twitter_tool import TwitterCollectorTool
from ..utils.helpers import SearchHelper, generate_competitive_queries


class ResearchFlow(Flow[ResearchState]):
    """
    Main research flow orchestrating all 10 stages of the NicheIQ pipeline.

    Stages:
    1-4: Niche Input & Validation (Flow)
    5: Search & Discover (Flow + SerperDevTool)
    6: Pain Point Analysis (PainPointCrew)
    7: Solution Ideation (IdeaGenerationCrew)
    8: Competitive Analysis (CompetitiveCrew)
    9: Keyword Validation (Flow + DataForSEOTool)
    10: Final Report Generation (Flow)
    """

    def __init__(self, niche_description: str):
        """
        Initialize ResearchFlow with niche description.

        Args:
            niche_description: User's niche area description
        """
        super().__init__()

        # Store niche description for use in flow methods
        self.niche_description = niche_description

        # Initialize tools
        self.search_tool = SerperDevTool()
        self.reddit_tool = RedditCollectorTool()
        self.twitter_tool = TwitterCollectorTool()
        self.keyword_tool = DataForSEOTool()

        # Initialize LLM for final report synthesis
        self.llm = LLM(model="gpt-4o-mini")

        logger.info(f"ResearchFlow initialized for niche: {niche_description[:100]}...")

    @start()
    def stage_1_validate_niche(self):
        """
        Stage 1-4: Niche Input & Validation

        Validates the niche description and generates structured NicheContext using LLM.
        """
        logger.info("=" * 80)
        logger.info("STAGE 1-4: Niche Input & Validation")
        logger.info("=" * 80)

        niche = self.niche_description.strip()

        if not niche:
            raise ValueError("Niche description cannot be empty")

        if len(niche) < 10:
            logger.warning("Niche description is very short. Consider providing more detail.")

        if len(niche) > 1000:
            logger.warning("Niche description is very long. Consider condensing to key points.")

        logger.info(f"✓ Niche validated: {niche[:100]}...")
        logger.info(f"✓ Target location: {settings.target_location}")
        logger.info(f"✓ Target language: {settings.target_language}")

        # Generate structured NicheContext using LLM
        logger.info("\nGenerating structured niche context...")
        try:
            niche_context = self._generate_niche_context(niche)
            self.state.niche_context = niche_context
            logger.info("✓ Niche context generated")
            # Ensure market_segments contains strings
            segments = [str(s) for s in niche_context.market_segments[:3]] if niche_context.market_segments else []
            logger.info(f"  - Market segments: {', '.join(segments)}...")
            logger.info(f"  - Industry boundaries defined")
        except Exception as e:
            logger.error(f"Failed to generate niche context with LLM: {e}")
            logger.warning("Proceeding without structured niche context")

        self.state.current_stage = 5

    def _generate_niche_context(self, niche_input: str):
        """Generate structured NicheContext using LLM with structured output."""
        from ..models.research_state import NicheContext
        from langchain_openai import ChatOpenAI

        prompt = f"""You are a market research analyst analyzing a niche market.

**Niche Input:** {niche_input}

**Your Task:**
Generate a structured analysis of this niche with the following:

1. **niche_description**:
   - 2-3 sentence refined description of this niche
   - Clarify what this market encompasses
   - Make it specific and actionable

2. **market_segments**:
   - List 3-7 distinct market segments within this niche
   - Be specific (e.g., "Small e-commerce businesses with 10-50 employees" not just "small businesses")
   - Focus on segments that might have different needs or buying patterns

3. **industry_boundaries**:
   - 2-3 sentences defining what is IN scope vs OUT of scope for this niche
   - Clarify adjacent markets or related areas that are NOT part of this niche
   - Help focus the research on the right target market

Be specific and actionable. Provide strategic insights.

Return a valid JSON object with this structure:
{{
  "niche_description": "...",
  "market_segments": ["segment 1", "segment 2", "..."],
  "industry_boundaries": "..."
}}"""

        # Use LangChain's ChatOpenAI directly for structured outputs
        structured_llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.7,
            api_key=settings.openai_api_key
        ).with_structured_output(NicheContext)

        # Generate structured output
        context = structured_llm.invoke(prompt)

        # Add niche_input to the context
        context.niche_input = niche_input
        return context

    @listen(stage_1_validate_niche)
    async def stage_5_search_and_discover(self):
        """
        Stage 5: Search & Discover

        Uses SerperDevTool to find relevant social discussions on Reddit and Twitter.
        """
        logger.info("=" * 80)
        logger.info("STAGE 5: Search & Discover")
        logger.info("=" * 80)

        # Generate strategic search queries
        from ..utils.helpers import QueryGenerator
        query_gen = QueryGenerator()

        logger.info("Generating strategic search queries...")
        queries = query_gen.generate_queries(
            self.niche_description,
            num_queries=settings.max_search_results
        )

        # Convert to SearchQuery objects
        from ..models.research_state import SearchQuery
        self.state.search_queries = [
            SearchQuery(
                query=q["query"],
                query_type=q.get("type", "problem"),
                platform=q.get("platform", "both")
            )
            for q in queries
        ]
        logger.info(f"✓ Generated {len(self.state.search_queries)} search queries")

        # Search Reddit
        logger.info("Searching Reddit for relevant discussions...")
        reddit_urls = []
        for search_query in self.state.search_queries[:10]:  # Limit to avoid rate limits
            try:
                results = self.search_tool.run(
                    search_query=f"site:reddit.com {search_query.query}"
                )
                urls = SearchHelper.extract_urls_from_serper(results, "reddit.com")
                reddit_urls.extend(urls)
            except Exception as e:
                logger.error(f"Reddit search failed for '{search_query.query}': {e}")

        # Deduplicate URLs
        reddit_urls = list(set(reddit_urls))[:settings.max_search_results]
        logger.info(f"✓ Found {len(reddit_urls)} Reddit discussion URLs")

        # Search Twitter
        logger.info("Searching Twitter/X for relevant discussions...")
        twitter_urls = []
        for search_query in self.state.search_queries[:10]:
            try:
                results = self.search_tool.run(
                    search_query=f"(site:twitter.com OR site:x.com) {search_query.query}"
                )
                # Extract both twitter.com and x.com URLs
                twitter_urls_1 = SearchHelper.extract_urls_from_serper(results, "twitter.com")
                twitter_urls_2 = SearchHelper.extract_urls_from_serper(results, "x.com")
                twitter_urls.extend([
                    url for url in twitter_urls_1 + twitter_urls_2
                    if "twitter.com" in url or "x.com" in url
                ])
            except Exception as e:
                logger.error(f"Twitter search failed for '{search_query.query}': {e}")

        twitter_urls = list(set(twitter_urls))[:settings.max_search_results]
        logger.info(f"✓ Found {len(twitter_urls)} Twitter thread URLs")

        # Collect Reddit content
        logger.info("Collecting Reddit posts and comments...")
        reddit_posts = self.reddit_tool.collect_posts(reddit_urls)
        logger.info(f"✓ Collected {len(reddit_posts)} quality Reddit posts")

        # Collect Twitter content
        logger.info("Collecting Twitter threads...")
        # Run in thread to avoid nested event loop issues with twitter-api-client
        loop = asyncio.get_event_loop()
        twitter_threads = await loop.run_in_executor(
            None,
            lambda: asyncio.run(self.twitter_tool.collect_threads(twitter_urls))
        )
        logger.info(f"✓ Collected {len(twitter_threads)} quality Twitter threads")

        # Store in social_content collection
        from ..models.social_content import SocialContentCollection
        self.state.social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=twitter_threads
        )

        self.state.current_stage = 6

    @listen(stage_5_search_and_discover)
    def stage_6_analyze_pain_points(self):
        """
        Stage 6: Pain Point Analysis

        Uses PainPointCrew to analyze social content and extract validated pain points.
        """
        logger.info("=" * 80)
        logger.info("STAGE 6: Pain Point Analysis")
        logger.info("=" * 80)

        if not self.state.social_content or (not self.state.social_content.reddit_posts and not self.state.social_content.twitter_threads):
            logger.warning("No social content collected. Skipping pain point analysis.")
            self.state.current_stage = 7
            return

        # Initialize and run PainPointCrew
        pain_point_crew = PainPointCrew(
            reddit_posts=self.state.social_content.reddit_posts,
            twitter_threads=self.state.social_content.twitter_threads
        )

        logger.info("Running pain point analysis crew...")
        self.state.pain_point_analysis = pain_point_crew.analyze()

        logger.info(f"✓ Identified {len(self.state.pain_point_analysis.pain_points)} pain points")
        logger.info(f"✓ Total mentions: {self.state.pain_point_analysis.total_mentions}")
        # Ensure top_categories contains strings
        top_cats = [str(c) for c in self.state.pain_point_analysis.top_categories[:3]] if self.state.pain_point_analysis.top_categories else []
        logger.info(f"✓ Top categories: {', '.join(top_cats)}")

        # Log high-opportunity pain points
        high_opp = [
            pp for pp in self.state.pain_point_analysis.pain_points
            if pp.opportunity_level.value == "high"
        ]
        if high_opp:
            logger.info(f"✓ High-opportunity pain points: {len(high_opp)}")
            for pp in high_opp[:3]:
                logger.info(f"  - {pp.title} (Severity: {pp.severity_score:.2f}, WTP: {pp.willingness_to_pay:.2f})")

        self.state.current_stage =7

    @listen(stage_6_analyze_pain_points)
    def stage_7_generate_ideas(self):
        """
        Stage 7: Solution Ideation

        Uses IdeaGenerationCrew to generate and refine SaaS solution concepts.
        """
        logger.info("=" * 80)
        logger.info("STAGE 7: Solution Ideation")
        logger.info("=" * 80)

        if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
            logger.warning("No pain points available. Skipping solution ideation.")
            self.state.current_stage =8
            return

        # Initialize and run IdeaGenerationCrew
        idea_crew = IdeaGenerationCrew(
            pain_point_analysis=self.state.pain_point_analysis
        )

        logger.info("Running solution ideation crew...")
        self.state.idea_generation = idea_crew.generate_ideas()

        logger.info(f"✓ Generated {len(self.state.idea_generation.solution_ideas)} solution concepts")

        # Log solution summaries
        for i, idea in enumerate(self.state.idea_generation.solution_ideas, 1):
            logger.info(f"  {i}. {idea.solution_name}: {idea.value_proposition}")
            logger.info(f"     Target: {idea.target_personas[0] if idea.target_personas else 'N/A'}")

        self.state.current_stage =8

    @listen(stage_7_generate_ideas)
    def stage_8_analyze_competition(self):
        """
        Stage 8: Competitive Analysis

        Uses CompetitiveCrew to research competitors and identify opportunities.
        """
        logger.info("=" * 80)
        logger.info("STAGE 8: Competitive Analysis")
        logger.info("=" * 80)

        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("No solution ideas available. Skipping competitive analysis.")
            self.state.current_stage =9
            return

        # Initialize and run CompetitiveCrew
        competitive_crew = CompetitiveCrew(
            solution_ideas=self.state.idea_generation
        )

        logger.info("Running competitive analysis crew...")
        self.state.competitive_analysis = competitive_crew.analyze_competition()

        logger.info(f"✓ Analyzed {len(self.state.competitive_analysis.solution_landscapes)} competitive landscapes")
        logger.info(f"✓ Identified {len(self.state.competitive_analysis.top_opportunities)} key opportunities")

        # Log top opportunities
        if self.state.competitive_analysis.top_opportunities:
            logger.info("✓ Top differentiation opportunities:")
            for opp in self.state.competitive_analysis.top_opportunities[:3]:
                logger.info(f"  - {opp}")

        self.state.current_stage =9

    @listen(stage_8_analyze_competition)
    def stage_9_validate_keywords(self):
        """
        Stage 9: Keyword Validation

        Uses DataForSEOTool to validate market demand through keyword research.
        """
        logger.info("=" * 80)
        logger.info("STAGE 9: Keyword Validation")
        logger.info("=" * 80)

        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("No solution ideas available. Skipping keyword validation.")
            self.state.current_stage =10
            return

        # Generate seed keywords from solution concepts
        seed_keywords = []
        for idea in self.state.idea_generation.solution_ideas:
            # Extract key terms from solution name and target pain points
            seed_keywords.append(idea.solution_name.lower())
            # Add first pain point if available
            if idea.pain_points_addressed:
                seed_keywords.append(idea.pain_points_addressed[0].lower())

        # Deduplicate and clean
        seed_keywords = list(set([str(kw).lower().strip() for kw in seed_keywords if kw]))[:20]

        logger.info(f"Generated {len(seed_keywords)} seed keywords for validation")
        # Ensure all keywords are strings
        keyword_sample = [str(k) for k in seed_keywords[:5]]
        logger.info(f"Seed keywords: {', '.join(keyword_sample)}...")

        # Run keyword research with expansion
        logger.info("Running keyword research and validation...")
        keyword_models = self.keyword_tool.process_keywords(
            seed_keywords=seed_keywords,
            expand=True
        )

        # Store results in state
        from ..models.keyword_data import KeywordValidationResult, KeywordResearchReport, OpportunityLevel

        high_opp_keywords = [kw for kw in keyword_models if kw.opportunity_level == OpportunityLevel.HIGH]
        medium_opp_keywords = [kw for kw in keyword_models if kw.opportunity_level == OpportunityLevel.MEDIUM]
        low_opp_keywords = [kw for kw in keyword_models if kw.opportunity_level == OpportunityLevel.LOW]

        # Generate keyword clusters
        logger.info("Clustering keywords by themes...")
        keyword_clusters = self._generate_keyword_clusters(keyword_models)
        logger.info(f"✓ Created {len(keyword_clusters)} keyword clusters")

        # Identify long-tail opportunities
        long_tail_keywords = self._identify_long_tail_keywords(keyword_models)
        logger.info(f"✓ Identified {len(long_tail_keywords)} long-tail keyword opportunities")

        # Create a single keyword research report for the niche
        report = KeywordResearchReport(
            solution_idea=self.niche_description,
            total_keywords_analyzed=len(keyword_models),
            high_opportunity_keywords=high_opp_keywords,
            medium_opportunity_keywords=medium_opp_keywords,
            low_opportunity_keywords=low_opp_keywords,
            keyword_clusters=keyword_clusters,
            long_tail_opportunities=long_tail_keywords,
            total_addressable_searches=sum(kw.search_volume for kw in keyword_models),
            demand_validation=f"Identified {len(high_opp_keywords)} high-opportunity keywords with {sum(kw.search_volume for kw in high_opp_keywords):,} monthly searches. "
            f"{len(long_tail_keywords)} long-tail opportunities across {len(keyword_clusters)} thematic clusters."
        )

        # Create validation result
        self.state.keyword_validation = KeywordValidationResult(
            niche=self.niche_description,
            reports=[report],
            overall_market_size=sum(kw.search_volume for kw in keyword_models),
            market_assessment=f"Total market size of {sum(kw.search_volume for kw in keyword_models):,} monthly searches across {len(keyword_models)} validated keywords"
        )

        logger.info(f"✓ Validated {len(keyword_models)} keywords")
        logger.info(f"✓ High opportunity: {len(high_opp_keywords)}")
        logger.info(f"✓ Medium opportunity: {len(medium_opp_keywords)}")
        logger.info(f"✓ Total search volume: {self.state.keyword_validation.overall_market_size:,}")

        # Log top keywords
        if high_opp_keywords:
            logger.info("✓ Top high-opportunity keywords:")
            for kw in sorted(high_opp_keywords, key=lambda k: k.search_volume, reverse=True)[:5]:
                logger.info(
                    f"  - '{kw.keyword}': {kw.search_volume:,} volume, "
                    f"{kw.competition:.2f} competition"
                )

        self.state.current_stage =10

    def _generate_keyword_clusters(self, keywords):
        """Generate keyword clusters by grouping similar keywords."""
        from ..models.keyword_data import KeywordCluster
        from collections import defaultdict

        # Group keywords by common root words
        clusters_dict = defaultdict(list)

        for kw in keywords:
            # Extract primary term (first 1-2 words)
            words = kw.keyword.lower().split()
            if len(words) >= 2:
                # Use first 2 words as cluster key
                cluster_key = ' '.join(words[:2])
            elif len(words) == 1:
                cluster_key = words[0]
            else:
                continue

            clusters_dict[cluster_key].append(kw)

        # Convert to KeywordCluster objects (keep clusters with 2+ keywords)
        clusters = []
        for cluster_name, cluster_keywords in clusters_dict.items():
            if len(cluster_keywords) >= 2:
                total_volume = sum(kw.search_volume for kw in cluster_keywords)
                avg_comp = sum(kw.competition for kw in cluster_keywords) / len(cluster_keywords)

                # Assess opportunity based on volume and competition
                if total_volume > 5000 and avg_comp < 0.5:
                    assessment = "High opportunity cluster with strong search volume and low competition"
                elif total_volume > 1000:
                    assessment = "Medium opportunity cluster with moderate search demand"
                else:
                    assessment = "Lower volume cluster, suitable for niche targeting"

                clusters.append(
                    KeywordCluster(
                        cluster_name=cluster_name.title(),
                        keywords=cluster_keywords,
                        total_search_volume=total_volume,
                        avg_competition=avg_comp,
                        opportunity_assessment=assessment,
                    )
                )

        # Sort by total search volume
        clusters.sort(key=lambda c: c.total_search_volume, reverse=True)

        # Return top 10 clusters
        return clusters[:10]

    def _identify_long_tail_keywords(self, keywords):
        """Identify long-tail keyword opportunities (3+ words, lower competition)."""
        from ..models.keyword_data import OpportunityLevel

        long_tail = []
        for kw in keywords:
            word_count = len(kw.keyword.split())
            # Long-tail: 3+ words, decent volume (100+), lower competition (<0.6)
            if (
                word_count >= 3
                and kw.search_volume >= 100
                and kw.competition < 0.6
                and kw.opportunity_level in [OpportunityLevel.HIGH, OpportunityLevel.MEDIUM]
            ):
                long_tail.append(kw)

        # Sort by opportunity score (volume / competition ratio)
        long_tail.sort(
            key=lambda k: k.search_volume / max(k.competition, 0.1), reverse=True
        )

        # Return top 20 long-tail opportunities
        return long_tail[:20]

    @listen(stage_9_validate_keywords)
    def stage_10_generate_report(self):
        """
        Stage 10: Final Report Generation

        Synthesizes all research findings into a comprehensive FinalReport using LLM.
        """
        logger.info("=" * 80)
        logger.info("STAGE 10: Final Report Generation")
        logger.info("=" * 80)

        from datetime import datetime

        # Prepare synthesis context from all stages
        synthesis_context = self._prepare_synthesis_context()

        # Create synthesis prompt
        synthesis_prompt = self._create_synthesis_prompt(synthesis_context)

        # Generate FinalReport using LLM with structured output
        logger.info("Generating comprehensive final report with LLM synthesis...")
        try:
            final_report = self._generate_final_report_with_llm(synthesis_prompt)
            self.state.final_report = final_report
            logger.info("✓ Final report synthesis complete")
        except Exception as e:
            logger.error(f"Failed to generate final report with LLM: {e}")
            logger.warning("Falling back to basic report generation")
            final_report = self._generate_fallback_report()
            self.state.final_report = final_report

        # Save outputs
        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save structured final report
        report_filename = f"final_report_{timestamp}.json"
        report_filepath = output_dir / report_filename
        with open(report_filepath, "w", encoding="utf-8") as f:
            json.dump(final_report.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"✓ Final report saved to: {report_filepath}")

        # Save complete raw state for reference
        raw_filename = f"research_state_raw_{timestamp}.json"
        raw_filepath = output_dir / raw_filename
        with open(raw_filepath, "w", encoding="utf-8") as f:
            json.dump(self.state.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"✓ Raw research state saved to: {raw_filepath}")

        # Display executive summary
        self._display_executive_summary(final_report)

        # Store report paths
        self.report_path = str(report_filepath)
        self.raw_state_path = str(raw_filepath)

    def _prepare_synthesis_context(self) -> dict:
        """Extract key data from all stages for synthesis."""
        context = {
            "niche": self.niche_description,
            "pain_points": [],
            "solutions": [],
            "competitors": [],
            "keywords": {},
        }

        # Extract pain points
        if self.state.pain_point_analysis:
            context["pain_points"] = [
                {
                    "title": pp.title,
                    "description": pp.description,
                    "severity": pp.severity_score,
                    "wtp": pp.willingness_to_pay,
                    "opportunity": pp.opportunity_level.value,
                    "mention_count": pp.mention_count,
                }
                for pp in self.state.pain_point_analysis.pain_points[:10]  # Top 10
            ]
            context["pain_points_summary"] = self.state.pain_point_analysis.analysis_summary

        # Extract solutions
        if self.state.idea_generation:
            context["solutions"] = [
                {
                    "name": sol.solution_name,
                    "value_prop": sol.value_proposition,
                    "features": sol.core_features[:5],  # Top 5 features
                    "market_fit": sol.market_fit_score,
                    "feasibility": sol.technical_feasibility_score,
                    "requires_data": sol.requires_data_aggregation,
                    "data_sources": sol.data_sources if sol.data_sources else [],
                }
                for sol in self.state.idea_generation.solution_ideas[:3]  # Top 3
            ]
            context["recommended_solution"] = self.state.idea_generation.recommended_solution

        # Extract competitive insights
        if self.state.competitive_analysis:
            context["top_opportunities"] = self.state.competitive_analysis.top_opportunities
            context["strategic_recommendations"] = (
                self.state.competitive_analysis.strategic_recommendations
            )
            context["competitor_count"] = sum(
                len(landscape.competitors)
                for landscape in self.state.competitive_analysis.solution_landscapes
            )

        # Extract keyword validation
        if self.state.keyword_validation:
            context["keywords"] = {
                "total_market_size": self.state.keyword_validation.overall_market_size,
                "market_assessment": self.state.keyword_validation.market_assessment,
                "total_keywords": sum(
                    r.total_keywords_analyzed for r in self.state.keyword_validation.reports
                ),
                "high_opportunity_count": sum(
                    len(r.high_opportunity_keywords)
                    for r in self.state.keyword_validation.reports
                ),
            }

        return context

    def _create_synthesis_prompt(self, context: dict) -> str:
        """Create comprehensive synthesis prompt for final report generation."""
        return f"""You are a strategic market research analyst creating a comprehensive final report.

**Research Context:**
Niche: {context['niche']}

**Pain Points Discovered:**
{json.dumps(context.get('pain_points', []), indent=2)}

Pain Points Summary: {context.get('pain_points_summary', 'N/A')}

**Solutions Developed:**
{json.dumps(context.get('solutions', []), indent=2)}

Recommended Solution: {context.get('recommended_solution', 'N/A')}

**Competitive Intelligence:**
- Top Opportunities: {', '.join(str(o) for o in context.get('top_opportunities', [])[:5])}
- Total Competitors Analyzed: {context.get('competitor_count', 0)}
- Strategic Recommendations: {context.get('strategic_recommendations', 'N/A')}

**Keyword Validation:**
- Total Search Volume: {context.get('keywords', {}).get('total_market_size', 0):,}
- Total Keywords Analyzed: {context.get('keywords', {}).get('total_keywords', 0)}
- High Opportunity Keywords: {context.get('keywords', {}).get('high_opportunity_count', 0)}
- Market Assessment: {context.get('keywords', {}).get('market_assessment', 'N/A')}

**Your Task:**
Generate a comprehensive final report with the following sections:

1. **executive_summary**:
   - 4-6 sentences synthesizing the entire research
   - Key findings, market opportunity, recommended direction
   - Make it compelling and actionable

2. **top_pain_points**:
   - List of 5-7 most critical pain point titles (just the titles as strings)
   - Focus on high-opportunity, high-severity points

3. **recommended_solutions**:
   - List of 2-3 solution names to pursue (just names as strings)
   - Prioritize by market fit and feasibility

4. **market_validation**:
   - 3-4 sentences on overall market viability
   - Include search volume, competition analysis, demand signals
   - Clear verdict: Strong/Moderate/Weak opportunity

5. **seo_implementation_guide**:
   - 300-500 word detailed SEO strategy
   - Keyword targeting approach, content strategy, link building
   - Specific tactics based on keyword research
   - How to leverage high-opportunity keywords
   - Technical SEO considerations

6. **data_sourcing_recommendations**:
   - 200-400 word strategy for solutions requiring data aggregation
   - Identify which solutions need external data
   - Recommend specific APIs, databases, or scraping targets
   - Data quality and compliance considerations
   - Fallback strategies if primary sources unavailable

7. **next_steps**:
   - List of 5-8 concrete action items
   - Prioritized and sequenced logically
   - Include validation, MVP development, marketing tactics

Provide strategic depth and actionable insights. Be specific, not generic."""

    def _generate_final_report_with_llm(self, prompt: str) -> FinalReport:
        """Generate FinalReport using LLM with structured output."""
        response = self.llm.call(
            messages=[{"role": "user", "content": prompt}],
            response_format=FinalReport,
        )

        # Parse response to FinalReport
        if isinstance(response, FinalReport):
            return response
        elif hasattr(response, "content"):
            # Handle string response - try to parse as JSON
            try:
                report_data = json.loads(response.content)
                return FinalReport(**report_data)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Failed to parse LLM response: {e}")
                raise

        raise ValueError(f"Unexpected LLM response type: {type(response)}")

    def _generate_fallback_report(self) -> FinalReport:
        """Generate basic FinalReport without LLM if synthesis fails."""
        from datetime import datetime

        # Extract top pain points
        top_pain_points = []
        if self.state.pain_point_analysis:
            top_pain_points = [
                pp.title
                for pp in sorted(
                    self.state.pain_point_analysis.pain_points,
                    key=lambda x: (x.severity_score + x.willingness_to_pay) / 2,
                    reverse=True,
                )[:5]
            ]

        # Extract recommended solutions
        recommended_solutions = []
        if self.state.idea_generation:
            recommended_solutions = [
                sol.solution_name for sol in self.state.idea_generation.solution_ideas[:3]
            ]

        return FinalReport(
            niche=self.niche_description,
            executive_summary=f"Market research completed for {self.niche_description}. "
            f"Identified {len(top_pain_points)} high-priority pain points and "
            f"{len(recommended_solutions)} viable solution concepts.",
            top_pain_points=top_pain_points if top_pain_points else ["No pain points identified"],
            recommended_solutions=recommended_solutions
            if recommended_solutions
            else ["No solutions generated"],
            market_validation="Research data collected. Review detailed findings for market assessment.",
            seo_implementation_guide="Implement SEO strategy based on validated keywords from keyword research stage.",
            data_sourcing_recommendations="Review solution requirements and identify necessary data sources for implementation.",
            next_steps=[
                "Review detailed research findings",
                "Validate top pain points with target users",
                "Develop MVP for recommended solution",
                "Implement SEO strategy",
                "Set up data sourcing infrastructure",
            ],
            generated_at=datetime.utcnow(),
        )

    def _display_executive_summary(self, report: FinalReport):
        """Display formatted executive summary to console."""
        logger.info("\n" + "=" * 80)
        logger.info("RESEARCH COMPLETE - FINAL REPORT")
        logger.info("=" * 80)
        logger.info(f"\nNiche: {report.niche}\n")
        logger.info("EXECUTIVE SUMMARY:")
        logger.info(report.executive_summary)
        logger.info(f"\n{'=' * 80}")
        logger.info("TOP PAIN POINTS:")
        for i, pp in enumerate(report.top_pain_points, 1):
            logger.info(f"  {i}. {pp}")
        logger.info(f"\n{'=' * 80}")
        logger.info("RECOMMENDED SOLUTIONS:")
        for i, sol in enumerate(report.recommended_solutions, 1):
            logger.info(f"  {i}. {sol}")
        logger.info(f"\n{'=' * 80}")
        logger.info("MARKET VALIDATION:")
        logger.info(report.market_validation)
        logger.info(f"\n{'=' * 80}")
        logger.info("NEXT STEPS:")
        for i, step in enumerate(report.next_steps, 1):
            logger.info(f"  {i}. {step}")
        logger.info("=" * 80)

    def run_research(self) -> str:
        """
        Execute the complete research pipeline.

        Returns:
            Path to the generated report file
        """
        logger.info("Starting NicheIQ Research Pipeline...")
        logger.info(f"Niche: {self.niche_description}")

        try:
            # Kick off the flow
            self.kickoff()

            logger.info("✓ Research pipeline completed successfully")
            return self.report_path

        except Exception as e:
            logger.error(f"Research pipeline failed: {e}")
            raise
