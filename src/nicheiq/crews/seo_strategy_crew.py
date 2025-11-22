"""
SEOStrategyCrew - Stage 9: Integrated Keyword Research + SEO Strategy
Multi-agent crew that performs keyword expansion and develops comprehensive SEO strategy.
"""

from typing import TYPE_CHECKING, Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.seo_strategy import (
    ContentStrategyResult,
    ExpandedKeywordList,
    FinalSynthesis,
    ImplementationGuide,
    ImplementationPlanResult,
    KeywordAnalysisResult,
    SEOStrategyReport,
)
from ..tools.dataforseo_tool import DataForSEOExpandTool, DataForSEOSearchVolumeTool
from ..utils.generation import KeywordSeedGenerator

if TYPE_CHECKING:
    from ..models.competitor import CompetitiveLandscape
    from ..models.research_state import NicheContext
    from ..models.solution_idea import SolutionIdea


@CrewBase
class SEOStrategyCrew:
    """
    Specialized crew for integrated keyword research and SEO strategy development.
    Performs keyword expansion using DataForSEO and creates actionable SEO implementation plan.

    Architecture:
    - 3 agents working in pipeline
    - Keyword Strategist expands seed keywords and creates tiered opportunity structure
    - Content Strategist develops content and cluster plan
    - SEO Specialist creates technical roadmap and implementation plan
    """

    agents_config = "config/seo_strategy_agents.yaml"
    tasks_config = "config/seo_strategy_tasks.yaml"

    def __init__(
        self,
        niche: str,
        selected_solution: "SolutionIdea",
        selection_rationale: str,
        competitive_analysis: CompetitiveAnalysisResult,
        pain_points: PainPointAnalysisResult | None = None,
        niche_context: "NicheContext | None" = None,
    ):
        """
        Initialize SEOStrategyCrew with SELECTED solution focus.

        The keyword_strategist agent will:
        1. Generate seed keywords specifically for the selected solution
        2. Expand seeds using DataForSEO tool
        3. Analyze and create tiered strategy focused on this solution

        Args:
            niche: The niche/market area being researched
            selected_solution: THE SINGLE SOLUTION to focus SEO strategy on (from Stage 8.5)
            selection_rationale: Why this solution was selected over alternatives
            competitive_analysis: Competitive landscape from Stage 8
            pain_points: Optional pain point analysis from Stage 6
            niche_context: Optional niche context with market_segments and industry_boundaries
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.niche = niche
        self.selected_solution = selected_solution
        self.selection_rationale = selection_rationale
        self.competitive_analysis = competitive_analysis
        self.pain_points = pain_points
        self.niche_context = niche_context

        # Initialize DataForSEO tools for keyword expansion and search volume
        self.dataforseo_expand_tool = DataForSEOExpandTool()
        self.dataforseo_volume_tool = DataForSEOSearchVolumeTool()

        # Initialize knowledge sources for keyword research
        self.knowledge_sources = []

        # Add pain point knowledge source if available (for user language)
        if pain_points and pain_points.pain_points:
            pain_point_content = self._prepare_pain_point_keywords_content()

            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.pain_point_knowledge = StringKnowledgeSource(
                content=pain_point_content,
                chunk_size=1000,  # Smaller chunks for focused keyword extraction
                chunk_overlap=150,  # Moderate overlap
            )
            self.knowledge_sources.append(self.pain_point_knowledge)
            logger.info(
                f"Pain point keyword knowledge source created ({len(pain_point_content)} chars) "
                f"for user language extraction"
            )

        # Add competitive intelligence if available (for alternative keywords)
        competitive_landscape = self._find_solution_landscape()
        if competitive_landscape and competitive_landscape.competitors:
            comp_content = self._prepare_competitive_keywords_content(competitive_landscape)

            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.competitive_knowledge = StringKnowledgeSource(
                content=comp_content,
                chunk_size=800,  # Tight chunks for specific competitor data
                chunk_overlap=100,
            )
            self.knowledge_sources.append(self.competitive_knowledge)
            logger.info(
                f"Competitive keyword knowledge source created ({len(comp_content)} chars) "
                f"with {len(competitive_landscape.competitors)} competitors"
            )

        logger.info(
            f"SEOStrategyCrew initialized for selected solution: {selected_solution.solution_name}"
            f"{' with ' + str(len(self.knowledge_sources)) + ' knowledge source(s)' if self.knowledge_sources else ''}"
        )

    def _find_solution_landscape(self) -> "CompetitiveLandscape | None":
        """
        Find competitive landscape for the selected solution.

        Returns:
            CompetitiveLandscape for selected solution, or None if not found
        """
        for landscape in self.competitive_analysis.solution_landscapes:
            if landscape.solution_name == self.selected_solution.solution_name:
                return landscape
        return None

    def _prepare_pain_point_keywords_content(self) -> str:
        """
        Format pain points for keyword research with focus on user language.

        Extracts actual user phrasing from pain point quotes to identify
        natural search language patterns for keyword generation.

        Returns:
            Formatted string with pain point user language for keyword mining
        """
        formatted = []

        for pp in self.pain_points.pain_points:
            # Extract user language patterns for keywords
            formatted.append(
                f"""[PAIN POINT LANGUAGE FOR KEYWORDS]
[PROBLEM: {pp.title}]

**User Problem Description:**
{pp.description}

**Actual User Phrasing (All Quotes for Keyword Mining):**
{chr(10).join(f'- {quote}' for quote in pp.representative_quotes)}

**Keyword Signals:**
- Severity: {pp.severity_score:.2f} ({"high" if pp.severity_score >= 0.7 else "medium" if pp.severity_score >= 0.4 else "low"})
- User intent: {pp.willingness_to_pay:.2f} WTP indicates {"commercial intent" if pp.willingness_to_pay >= 0.6 else "informational intent"}
- Categories: {', '.join(pp.categories if pp.categories else ['N/A'])}
- Platforms: {', '.join(pp.source_platforms if pp.source_platforms else ['N/A'])}
"""
            )

        return "\n\n---\n\n".join(formatted)

    def _prepare_competitive_keywords_content(self, landscape: "CompetitiveLandscape") -> str:
        """
        Format competitive data for alternative keyword generation.

        Args:
            landscape: Competitive landscape for selected solution

        Returns:
            Formatted string with competitor data for keyword alternatives
        """
        formatted = [
            f"""[COMPETITIVE KEYWORDS FOR: {landscape.solution_name}]

**Direct Competitors ({len(landscape.competitors)}):**
{chr(10).join(f'- {c.name}: {c.description}' for c in landscape.competitors)}

**Market Gaps (Alternative Positioning Keywords):**
{chr(10).join(f'- {gap}' for gap in landscape.market_gaps)}

**Differentiation Opportunities (Unique Keyword Angles):**
{chr(10).join(f'- {opp}' for opp in landscape.differentiation_opportunities)}

**Recommended Positioning:**
{landscape.recommended_positioning}
"""
        ]

        return "\n".join(formatted)

    @agent
    def keyword_strategist(self) -> Agent:
        """
        Agent responsible for analyzing pre-enriched keywords from CSV input and creating tiered opportunity structure.

        NOTE: Receives complete keyword data via CSV input (enriched in Phase 9.5b with DataForSEO).
        Agent analyzes existing data to identify quick wins (Tier 1) vs long-term plays (Tier 4).
        Does NOT call external APIs - all keyword data is pre-validated and provided in task context.

        Uses zero temperature for data-driven keyword analysis (no creativity needed).
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["keyword_strategist"],
            tools=[],  # No tools needed - analyzes CSV data provided in task context
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.0,  # Zero temperature for precise data extraction (no creativity needed)
                api_key=settings.openai_api_key,
            ),
            verbose=True,
        )

    @agent
    def content_strategist(self) -> Agent:
        """
        Agent responsible for content strategy and topic clustering.
        Creates content recommendations aligned with keyword opportunities.

        Uses moderate temperature (0.5) for balanced creative strategy with structure.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["content_strategist"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.5,  # Moderate temperature for creative content ideas with structured output
                api_key=settings.openai_api_key,
            ),
            verbose=True,
        )

    @agent
    def seo_specialist(self) -> Agent:
        """
        Agent responsible for technical SEO and implementation roadmap.
        Provides URL structure, schema markup, and phased implementation plan.

        Uses moderate temperature (0.4) to balance technical precision with creative customization.
        Slightly higher than 0.3 to encourage solution-specific examples while maintaining accuracy.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["seo_specialist"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,  # Moderate temperature for technical precision with customization flexibility
                timeout=180,  # Increased timeout to 180 seconds for complex implementation tasks
                api_key=settings.openai_api_key,
            ),
            verbose=True,
        )

    @task
    def expand_keywords_conceptually_task(self) -> Task:
        """
        Task: Phase 9.5a - Hybrid seed keyword generation (70% broad seeds + 30% targeted keywords).

        Output: ExpandedKeywordList with 40-50 total keywords organized by 5-8 topic clusters.
        """
        return Task(
            config=self.tasks_config["expand_keywords_conceptually"],
            agent=self.content_strategist(),  # Use content strategist for strategic thinking
            output_pydantic=ExpandedKeywordList,
        )

    # ========================================
    # MULTI-TASK SEO STRATEGY (4-TASK FLOW)
    # ========================================

    @task
    def analyze_keywords_and_tier_task(self) -> Task:
        """
        Task 1: Keyword Analysis & Tiering.

        Analyzes pre-enriched keywords and creates tiered opportunity structure.

        Output: KeywordAnalysisResult with tier structure, competitive positioning, key findings.
        """
        return Task(
            config=self.tasks_config["analyze_keywords_and_tier"],
            agent=self.keyword_strategist(),
            output_pydantic=KeywordAnalysisResult,
        )

    @task
    def develop_content_technical_strategy_task(self) -> Task:
        """
        Task 2: Content & Technical Strategy.

        Develops content strategy, topic clusters, and technical SEO recommendations
        based on keyword analysis from Task 1.

        Depends on: analyze_keywords_and_tier_task
        Output: ContentStrategyResult with content plan and technical recommendations.
        """
        return Task(
            config=self.tasks_config["develop_content_technical_strategy"],
            agent=self.content_strategist(),
            context=[self.analyze_keywords_and_tier_task()],  # Depends on Task 1
            output_pydantic=ContentStrategyResult,
        )

    @task
    def create_implementation_plan_task(self) -> Task:
        """
        Task 3: Implementation Planning.

        Creates phased implementation roadmap with metrics, timeline, budget, and risks
        based on keyword analysis and content strategy.

        Depends on: analyze_keywords_and_tier_task, develop_content_technical_strategy_task
        Output: ImplementationPlanResult with roadmap, metrics, timeline.
        """
        return Task(
            config=self.tasks_config["create_implementation_plan"],
            agent=self.seo_specialist(),
            context=[
                self.analyze_keywords_and_tier_task(),  # Task 1
                self.develop_content_technical_strategy_task(),  # Task 2
            ],
            output_pydantic=ImplementationPlanResult,
        )

    def _validate_seo_synthesis(self, task_output) -> tuple[bool, Any]:
        """
        Guardrail to ensure Task 4 preserves all fields from Tasks 1-3.

        Validates that all critical fields are populated in the SEOStrategyReport
        to prevent field loss during synthesis. Automatically retries if validation fails.

        Returns:
            tuple[bool, Any]: (True, result) if valid, (False, error_message) if validation fails
        """
        try:
            result = task_output.pydantic

            # Check critical fields are populated
            required_fields = {
                "tier_1_keywords": list,
                "tier_1_quick_win_strategy": str,
                "content_strategy": str,
                "technical_seo_recommendations": str,
                "implementation_roadmap": str,
                "key_metrics_to_track": list,
                "long_term_strategy": str,
                "conclusion_bottom_line": str,
                "competitive_advantages": list,
                "critical_success_factors": list,
                "expected_timeline": str,
                "next_steps_checklist": list,
            }

            for field, expected_type in required_fields.items():
                value = getattr(result, field, None)
                if value is None:
                    return (False, f"Missing required field: {field}")
                if expected_type is list and len(value) == 0:
                    return (False, f"Empty required list field: {field}")
                if expected_type is str and len(value.strip()) == 0:
                    return (False, f"Empty required string field: {field}")

            logger.info(
                f"[OK] SEO synthesis validation passed: "
                f"all {len(required_fields)} critical fields populated"
            )
            return (True, result)

        except Exception as e:
            logger.error(f"SEO synthesis validation error: {e}")
            return (False, f"Validation error: {str(e)}")

    @task
    def synthesize_final_seo_strategy_task(self) -> Task:
        """
        Task 4: Final Strategy Synthesis.

        Generates ONLY 4 new strategic synthesis fields:
        - long_term_strategy (Year 1/2/3 strategic milestones)
        - conclusion_bottom_line (Executive summary paragraph)
        - competitive_advantages (2-4 key advantages)
        - critical_success_factors (3-4 success factors)

        All 21 fields from Tasks 1-3 will be preserved via Python merge in create_strategy_multitask().

        Depends on: All previous tasks (1, 2, 3)
        Output: FinalSynthesis (4 fields only)
        """
        return Task(
            config=self.tasks_config["synthesize_final_seo_strategy"],
            agent=self.seo_specialist(),
            context=[
                self.analyze_keywords_and_tier_task(),  # Task 1 (reference)
                self.develop_content_technical_strategy_task(),  # Task 2 (reference)
                self.create_implementation_plan_task(),  # Task 3 (reference)
            ],
            output_pydantic=FinalSynthesis,
        )

    @task
    def create_implementation_guide_task(self) -> Task:
        """
        Task 5: Create SEO Implementation Guide.

        Generates ONLY 3 new implementation fields:
        - universal_seo_elements (title tags, meta descriptions, canonical, OG tags, robots)
        - page_type_implementations (4-6 page type templates with examples)
        - schema_markup_strategy (JSON-LD code examples, priority types, testing)

        All 26 fields from Task 4 will be preserved via Python merge in create_strategy_multitask().

        Depends on: All previous tasks (1, 2, 3, 4)
        Output: ImplementationGuide (3 fields only)
        """
        return Task(
            config=self.tasks_config["create_implementation_guide"],
            agent=self.seo_specialist(),
            context=[
                self.analyze_keywords_and_tier_task(),  # Task 1 (for keyword reference)
                self.develop_content_technical_strategy_task(),  # Task 2 (for page types)
                self.create_implementation_plan_task(),  # Task 3 (for roadmap)
                self.synthesize_final_seo_strategy_task(),  # Task 4 (reference only)
            ],
            output_pydantic=ImplementationGuide,
            guardrail=self._validate_implementation_guide,  # Automated validation
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the SEOStrategyCrew with all agents, tasks, and optional knowledge sources.

        If knowledge sources are available (pain points and/or competitive data),
        they are attached at crew level for keyword research and content strategy.

        Returns:
            Configured Crew instance with optional knowledge sources
        """
        from crewai.knowledge.knowledge import Knowledge

        from ..utils.helpers import sanitize_collection_name

        embedder_config = {
            "provider": "openai",
            "config": {"model_name": "text-embedding-3-small"},  # Cost-effective embeddings
        }

        crew_config = {
            "agents": self.agents,
            "tasks": self.tasks,
            "verbose": True,
            "process_type": "sequential",
            "embedder": embedder_config,
        }

        # Create Knowledge with niche-specific collection name for isolation
        if self.knowledge_sources:
            collection_name = sanitize_collection_name(self.niche, "seo")
            logger.info(f"Creating SEO knowledge with collection: {collection_name}")
            knowledge = Knowledge(
                sources=self.knowledge_sources,
                embedder=embedder_config,
                collection_name=collection_name,
            )
            knowledge.add_sources()
            crew_config["knowledge"] = knowledge

        return Crew(**crew_config)

    def expand_keywords_phase_1(self) -> ExpandedKeywordList:
        """
        Execute Phase 9.5a: Hybrid Seed Keyword Generation using KeywordSeedGenerator.

        Generates a strategic mix using 70-30 approach:
        - 70% Broad Seeds (28-35 keywords, 1-2 words): For DataForSEO expansion into thousands of variations
        - 30% Targeted Keywords (12-15 keywords, 3-5 words): Strategic high-value queries for direct validation

        Returns 40-50 total keywords organized by 5-8 topic clusters.

        Returns:
            ExpandedKeywordList with hybrid seed keywords for Phase 9.5b bulk validation and expansion
        """
        logger.info(
            f"Starting Phase 9.5a: Context-aware seed keyword generation for: {self.selected_solution.solution_name}"
        )

        try:
            # Initialize KeywordSeedGenerator
            generator = KeywordSeedGenerator()

            # Generate seeds with full context
            result = generator.generate_seeds(
                solution=self.selected_solution,
                niche_context=self.niche_context,
                pain_points=self.pain_points,
                competitive_analysis=self.competitive_analysis,
                num_broad_seeds=30,
                num_targeted_seeds=15,
            )

            if not result:
                logger.error(
                    "KeywordSeedGenerator returned None - falling back to minimal keywords"
                )
                # Fallback: return minimal keyword list
                from ..models.seo_strategy import ConceptualKeyword, ConceptualTopicCluster

                fallback_keywords = [
                    ConceptualKeyword(
                        keyword=self.selected_solution.solution_name.lower(),
                        cluster="Core Product",
                        priority=1,
                        rationale="Fallback keyword - generator failed",
                    )
                ]
                fallback_clusters = [
                    ConceptualTopicCluster(
                        name="Core Product",
                        description="Primary solution keywords",
                        strategic_importance=1,
                    )
                ]
                result = ExpandedKeywordList(
                    keywords=fallback_keywords,
                    topic_clusters=fallback_clusters,
                    expansion_rationale="Fallback mode - generator failed",
                )

            logger.info(
                f"Phase 9.5a complete: {len(result.keywords)} seed keywords generated, "
                f"{len(result.topic_clusters)} topic clusters identified"
            )
            return result

        except Exception as e:
            logger.error(f"Phase 9.5a keyword generation failed: {e}", exc_info=True)
            raise

    def _extract_page_types_from_task2(self, task2_output) -> str:
        """
        Extract keyword_based_page_types from Task 2 content strategy output.

        Args:
            task2_output: TaskOutput object from Task 2 (ContentStrategyResult)

        Returns:
            Formatted string with page types for Task 5 reference
        """
        try:
            if hasattr(task2_output, "pydantic"):
                content_strategy = task2_output.pydantic
                if (
                    hasattr(content_strategy, "keyword_based_page_types")
                    and content_strategy.keyword_based_page_types
                ):
                    page_types = content_strategy.keyword_based_page_types
                    formatted = "\n".join([f"- {pt}" for pt in page_types])
                    logger.debug(f"Extracted {len(page_types)} page types from Task 2")
                    return formatted

            logger.warning("No keyword_based_page_types found in Task 2 output")
            return "No page types found in Task 2 output - generate based on project_type standards"

        except Exception as e:
            logger.warning(f"Failed to extract page types from Task 2: {e}")
            return "Unable to extract page types from Task 2 - generate based on project_type standards"

    def _validate_implementation_guide(self, task_output) -> tuple[bool, Any]:
        """
        Guardrail function to validate Task 5 implementation guide output structure.

        Validates:
        - Pydantic output exists
        - Minimum 4 page type implementations

        Args:
            task_output: TaskOutput from Task 5 (create_implementation_guide)

        Returns:
            tuple[bool, Any]: (success, validated_result_or_error_message)
        """
        try:
            # Check if Pydantic output exists
            if not task_output.pydantic:
                return (
                    False,
                    "Return ONLY the ImplementationGuide Pydantic model",
                )

            result = task_output.pydantic  # Should be ImplementationGuide

            # Validation: Check page template count
            if (
                not hasattr(result, "page_type_implementations")
                or not result.page_type_implementations
            ):
                return (False, "Need at least 4 page type implementations - found 0")

            page_templates = result.page_type_implementations
            if len(page_templates) < 4:
                return (
                    False,
                    f"Need at least 4 page type implementations - found {len(page_templates)}",
                )

            logger.info(
                f"✓ Implementation guide validation passed: {len(page_templates)} page types"
            )
            return (True, result)

        except Exception as e:
            logger.error(f"Guardrail validation exception: {str(e)}")
            return (False, f"Validation error: {str(e)}")

    def _format_keywords_as_csv(self, enriched_keywords: list) -> str:
        """
        Format keywords as CSV for direct context injection.

        CSV is 2x more token-efficient than JSON for tabular data and provides
        complete keyword visibility to agents without requiring RAG queries.

        Returns:
            CSV string with header and keyword data
        """
        # CSV header
        lines = [
            "keyword,search_volume,competition_index,competition_level,cpc,opportunity_score,tier"
        ]

        for k in enriched_keywords:
            keyword_text = k.get("keyword", "")
            search_volume = k.get("search_volume", 0)
            competition_index = k.get("competition_index", 0)
            cpc = float(k.get("cpc") or 0)

            # Calculate opportunity score
            opp_score = search_volume / max(competition_index, 1)

            # Format competition label
            if competition_index < 30:
                comp_label = "LOW" if competition_index >= 15 else "VERY_LOW"
            elif competition_index < 60:
                comp_label = "MEDIUM"
            elif competition_index < 80:
                comp_label = "HIGH"
            else:
                comp_label = "VERY_HIGH"

            # Assign tier based on opportunity score
            if opp_score > 200:
                tier = "TIER_0_PREMIUM"
            elif opp_score > 100:
                tier = "TIER_1_QUICK_WIN"
            elif opp_score > 50:
                tier = "TIER_2_STRATEGIC"
            elif opp_score > 20:
                tier = "TIER_3_MEDIUM"
            else:
                tier = "TIER_4_LONG_TAIL"

            # Add CSV row (escape commas in keyword text if present)
            keyword_escaped = keyword_text.replace(",", " ")
            lines.append(
                f"{keyword_escaped},{search_volume},{competition_index},"
                f"{comp_label},{cpc:.2f},{opp_score:.1f},{tier}"
            )

        return "\n".join(lines)

    def create_strategy_multitask(
        self, enriched_keywords: list, expanded_keywords: ExpandedKeywordList | None = None
    ) -> SEOStrategyReport:
        """
        Execute 5-Task SEO Strategy Flow with Direct CSV Input.

        Creates comprehensive SEO strategy using sequential 5-task flow:
        1. Keyword Analysis & Tiering
        2. Content & Technical Strategy
        3. Implementation Planning
        4. Final Synthesis
        5. Implementation Guide (NEW - Universal SEO, Page Templates, Schema)

        Uses direct CSV input for keyword data (industry best practice for structured data).
        CSV format is 2x more token-efficient than JSON and provides complete visibility.

        Args:
            enriched_keywords: List of dicts from DataForSEO with volumes/competition
            expanded_keywords: Optional ExpandedKeywordList from Phase 9.5a (contains ConceptualKeyword objects and ConceptualTopicCluster metadata)

        Returns:
            Complete SEOStrategyReport with implementation details (29 fields total)
        """
        logger.info(
            f"Starting 5-Task SEO Strategy Flow for: {self.selected_solution.solution_name}"
        )
        logger.info(
            f"Processing {len(enriched_keywords)} enriched keywords"
            + (
                f" with {len(expanded_keywords.keywords)} seed keywords"
                if expanded_keywords
                else ""
            )
        )

        try:
            # Format keywords as CSV for direct context injection
            keywords_csv = self._format_keywords_as_csv(enriched_keywords)
            csv_line_count = keywords_csv.count("\n") + 1
            csv_token_estimate = len(keywords_csv) // 4  # Rough estimate: 4 chars per token
            logger.info(
                f"Created keyword CSV: {csv_line_count} lines, ~{csv_token_estimate:,} tokens"
            )

            # Format topic clusters summary (with None handling)
            if expanded_keywords and expanded_keywords.topic_clusters:
                topic_clusters_summary = "\n".join(
                    [
                        f"- **{c.name}** (Priority {c.strategic_importance}/5): {c.description}"
                        for c in expanded_keywords.topic_clusters
                    ]
                )
            else:
                topic_clusters_summary = "No topic clusters identified"

            # Create 5-task crew WITHOUT Knowledge Sources
            strategy_crew = Crew(
                agents=[
                    self.keyword_strategist(),
                    self.content_strategist(),
                    self.seo_specialist(),
                ],
                tasks=[
                    self.analyze_keywords_and_tier_task(),  # Task 1
                    self.develop_content_technical_strategy_task(),  # Task 2 (context: Task 1)
                    self.create_implementation_plan_task(),  # Task 3 (context: Tasks 1+2)
                    self.synthesize_final_seo_strategy_task(),  # Task 4 (context: Tasks 1+2+3)
                    self.create_implementation_guide_task(),  # Task 5 (context: ALL previous tasks)
                ],
                # NO knowledge_sources - using direct CSV input
                # NO embedder - no RAG needed
                verbose=True,
                process_type="sequential",
            )

            # Execute with CSV directly in inputs
            # Format solution architecture for task context
            core_features_formatted = (
                "\n".join([f"- {feat}" for feat in self.selected_solution.core_features])
                if self.selected_solution.core_features
                else "Not specified"
            )
            technical_approach_formatted = (
                self.selected_solution.technical_approach or "Not specified"
            )

            # Format competitor names for keyword contextualization
            competitive_landscape = self._find_solution_landscape()
            if competitive_landscape and competitive_landscape.competitors:
                competitor_names_formatted = "\n".join(
                    [f"- {c.name}" for c in competitive_landscape.competitors]
                )
            else:
                competitor_names_formatted = "No direct competitors identified"

            # Format pain point metrics for keyword contextualization using unified helper
            from ..utils.pain_point_formatters import format_pain_points_for_agents

            if self.pain_points and self.pain_points.pain_points:
                pain_points_formatted = format_pain_points_for_agents(
                    pain_points=self.pain_points.pain_points,
                    format_type="metrics_only",
                    sort_by="severity",
                    limit=10,
                )
            else:
                pain_points_formatted = "No pain points available"

            # Format additional solution context for Task 5 implementation guide
            value_proposition = self.selected_solution.value_proposition or "Not specified"
            target_personas_formatted = (
                "\n".join([f"- {persona}" for persona in self.selected_solution.target_personas])
                if self.selected_solution.target_personas
                else "Not specified"
            )
            pricing_strategy = self.selected_solution.pricing_strategy or "Not specified"

            logger.info("Executing Task 1: Keyword Analysis & Tiering (keywords via CSV)...")
            logger.info(f"All {len(enriched_keywords)} keywords visible in context")
            crew_output = strategy_crew.kickoff(
                inputs={
                    "niche": self.niche,
                    "selected_solution_name": self.selected_solution.solution_name,
                    "selected_solution_description": self.selected_solution.description,
                    "value_proposition": value_proposition,
                    "target_personas": target_personas_formatted,
                    "pricing_strategy": pricing_strategy,
                    "core_features": core_features_formatted,
                    "technical_approach": technical_approach_formatted,
                    "competitor_names": competitor_names_formatted,
                    "top_pain_points": pain_points_formatted,
                    "enriched_keywords_count": len(enriched_keywords),
                    "enriched_keywords_csv": keywords_csv,  # ← Direct CSV input
                    "topic_clusters_summary": topic_clusters_summary,
                }
            )

            # Extract all task outputs (Tasks 1-5)
            task_outputs = crew_output.tasks_output if hasattr(crew_output, "tasks_output") else []
            if len(task_outputs) < 5:
                logger.error(f"Expected 5 task outputs, got {len(task_outputs)}")
                raise ValueError("Incomplete task execution in SEO strategy crew")

            task_1_output = task_outputs[0].pydantic  # KeywordAnalysisResult (10 fields)
            task_2_output = task_outputs[1].pydantic  # ContentStrategyResult (5 fields)
            task_3_output = task_outputs[2].pydantic  # ImplementationPlanResult (6 fields)
            task_4_output = task_outputs[3].pydantic  # FinalSynthesis (4 fields)
            task_5_output = task_outputs[4].pydantic  # ImplementationGuide (3 fields)

            # Prepare seed keywords from conceptual expansion (if available)
            seed_keywords = (
                [k.keyword for k in expanded_keywords.keywords] if expanded_keywords else None
            )

            # Python merge: Combine all task outputs into complete SEOStrategyReport
            result = SEOStrategyReport(
                # Metadata (from inputs)
                seed_keywords_generated=seed_keywords,
                # Task 1 fields (10 fields)
                **task_1_output.model_dump(),
                # Task 2 fields (5 fields)
                **task_2_output.model_dump(),
                # Task 3 fields (6 fields)
                **task_3_output.model_dump(),
                # Task 4 fields (4 fields)
                long_term_strategy=task_4_output.long_term_strategy,
                conclusion_bottom_line=task_4_output.conclusion_bottom_line,
                competitive_advantages=task_4_output.competitive_advantages,
                critical_success_factors=task_4_output.critical_success_factors,
                # Task 5 fields (3 fields)
                universal_seo_elements=task_5_output.universal_seo_elements,
                page_type_implementations=task_5_output.page_type_implementations,
                schema_markup_strategy=task_5_output.schema_markup_strategy,
            )

            logger.info(
                f"[OK] 5-Task SEO Strategy Flow complete (Tasks 1-5 merged via Python):\n"
                f"  - Tier 1 keywords: {len(result.tier_1_keywords) if result.tier_1_keywords else 0}\n"
                f"  - Topic clusters: {len(result.topic_clusters) if result.topic_clusters else 0}\n"
                f"  - Total monthly volume: {result.total_monthly_volume if result.total_monthly_volume is not None else 0}\n"
                f"  - Page type implementations: {len(result.page_type_implementations) if result.page_type_implementations else 0}\n"
                f"  - Implementation guide: {'✓ Included' if result.universal_seo_elements else '✗ Not generated'}\n"
                f"  - Implementation roadmap: {'✓' if result.implementation_roadmap else '✗'}\n"
                f"  - Long-term strategy: {'✓' if result.long_term_strategy else '✗'}"
            )
            return result

        except Exception as e:
            logger.error(f"4-Task SEO Strategy Flow failed: {e}")
            raise
