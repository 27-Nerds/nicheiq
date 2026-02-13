"""
UnifiedSolutionCrew - Stages 7-8.75: Complete Solution Pipeline
Implements 6-task divergent-convergent architecture for solution ideation.

Architecture:
1. Divergent Exploration - Generate 8-12 raw concepts with forced ideation
2. Diversity Filtering - Filter to 5-7 unique concepts
3. Solution Refinement - Expand to 3-5 full specifications
4. Competitive Analysis - Analyze competitive landscape
5. Competitive Refinement - Enhance with competitive insights
6. Solution Selection - Select best solution

Benefits:
- Forced ideation techniques prevent obvious/similar ideas
- Explicit diversity filtering catches duplicates
- Novelty scoring ensures innovation
- Solo-dev feasibility weighted in scoring
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..flows.checkpoint_manager import CheckpointManager

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_llm_kwargs
from ..models.competitor import CompetitiveAnalysisResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import AudienceMappingResult, NicheContext
from ..models.social_content import SocialContentCollection
from ..models.solution_idea import (
    FilteredConceptList,
    IdeaGenerationResult,
    RawConceptList,
)
from ..models.solution_selection import SolutionSelection
from ..tools import CachedSerperDevTool, CompetitorQueryTool
from ..utils.crew_helpers import (
    prepare_competitor_intelligence,
    prepare_pain_point_content,
)
from ..utils.validation import (
    create_diversity_guardrail,
    validate_competitive_analysis,
    validate_filtered_concepts,
    validate_raw_concepts,
    validate_solution_selection,
)


@CrewBase
class UnifiedSolutionCrew:
    """
    Unified crew consolidating solution pipeline (Stages 7, 8, 8.5, 8.75).

    Implements CrewAI best practices:
    - Output Pydantic models for structured data
    - Context chaining for automatic field preservation
    - Guardrails for validation
    - Knowledge Sources for large datasets
    """

    agents_config = "config/unified_solution_agents.yaml"
    tasks_config = "config/unified_solution_tasks.yaml"

    def __init__(
        self,
        pain_point_analysis: PainPointAnalysisResult,
        social_content: SocialContentCollection | None = None,
        allowed_project_types: list[str] | None = None,
        niche_context: NicheContext | None = None,
        audience_mapping: AudienceMappingResult | None = None,
        checkpoint_mgr: "CheckpointManager | None" = None,
        job_id: str | None = None,
    ):
        """
        Initialize UnifiedSolutionCrew with pain points and optional context.

        Args:
            pain_point_analysis: Validated pain points from PainPointCrew
            social_content: Optional social content for competitor intelligence
            allowed_project_types: Optional constraints on project types
            niche_context: Optional structured niche context with market segments and boundaries
            audience_mapping: Optional audience intelligence from AudienceMappingCrew
            checkpoint_mgr: Optional checkpoint manager for task-level saves
            job_id: Optional job identifier for per-job ChromaDB collection isolation
        """
        self.pain_point_analysis = pain_point_analysis
        self.social_content = social_content
        self.allowed_project_types = allowed_project_types
        self.niche_context = niche_context
        self.audience_mapping = audience_mapping
        self.checkpoint_mgr = checkpoint_mgr
        self.job_id = job_id

        # Initialize search tool for competitive research
        self.search_tool = CachedSerperDevTool()

        # Initialize competitor query generator tool
        self.query_tool = CompetitorQueryTool(niche_context=niche_context)

        # Initialize knowledge sources
        self.knowledge_sources = []

        # Prepare pain point knowledge source (for Task 1)
        if pain_point_analysis.pain_points:
            pain_point_content = prepare_pain_point_content(pain_point_analysis)
            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.pain_point_knowledge = StringKnowledgeSource(
                content=pain_point_content,
                chunk_size=1500,
                chunk_overlap=250
            )
            self.knowledge_sources.append(self.pain_point_knowledge)
            logger.info(
                f"Pain point knowledge source created ({len(pain_point_content)} chars) "
                f"for {len(pain_point_analysis.pain_points)} pain points"
            )

        # Prepare competitor intelligence knowledge source (for Task 2)
        if social_content and (social_content.reddit_posts or social_content.twitter_threads):
            competitor_intel = prepare_competitor_intelligence(social_content)
            if competitor_intel:
                from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

                self.competitor_knowledge = StringKnowledgeSource(
                    content=competitor_intel,
                    chunk_size=1000,
                    chunk_overlap=150
                )
                self.knowledge_sources.append(self.competitor_knowledge)
                logger.info(
                    f"Competitor intelligence knowledge source created ({len(competitor_intel)} chars)"
                )

        # Create diversity guardrail with allowed project types
        self._diversity_guardrail = create_diversity_guardrail(allowed_project_types)

        logger.info(
            f"UnifiedSolutionCrew initialized with {len(pain_point_analysis.pain_points)} pain points "
            f"and {len(self.knowledge_sources)} knowledge sources"
        )

    # ========== AUDIENCE CONTEXT HELPER ==========

    def _format_audience_context(self) -> dict[str, str]:
        """Format audience mapping for task inputs."""
        if not self.audience_mapping:
            return {
                "primary_target_segment": "Not available",
                "audience_segments_summary": "Not available",
                "common_vocabulary": "Not available",
                "frustrations_with_existing": "Not available",
                "tools_currently_used": "Not available",
            }

        # Format audience segments
        segments = "\n".join(
            f"- {s.segment_name}: {', '.join(s.pain_point_alignment)} ({s.expertise_level})"
            for s in self.audience_mapping.audience_segments[:5]
        ) if self.audience_mapping.audience_segments else "Not available"

        return {
            "primary_target_segment": self.audience_mapping.primary_target_segment or "Not available",
            "audience_segments_summary": segments,
            "common_vocabulary": ", ".join(self.audience_mapping.common_vocabulary[:12]) if self.audience_mapping.common_vocabulary else "Not available",
            "frustrations_with_existing": "\n".join(
                f"- {f}" for f in self.audience_mapping.frustrations_with_existing[:5]
            ) if self.audience_mapping.frustrations_with_existing else "Not available",
            "tools_currently_used": ", ".join(self.audience_mapping.tools_currently_used[:8]) if self.audience_mapping.tools_currently_used else "Not available",
        }

    # ========== AGENTS ==========

    @agent
    def solution_ideator(self) -> Agent:
        """
        Agent for generating innovative solution concepts.
        Uses configurable brainstorm_llm with high temperature/reasoning_effort.

        GPT-5 series: reasoning_effort from settings (default: high for creative ideation)
        Older models: temperature=0.85, frequency_penalty=0.5, presence_penalty=0.3
        """
        # Use build_llm_kwargs for automatic reasoning model detection
        # For reasoning models: temperature/frequency_penalty/presence_penalty are ignored
        # For older models: uses the specified sampling parameters
        llm_kwargs = build_llm_kwargs(
            model=settings.brainstorm_llm,
            temperature=0.85,
            frequency_penalty=0.5,
            presence_penalty=0.3,
        )
        if settings.brainstorm_reasoning_effort:
            llm_kwargs["reasoning_effort"] = settings.brainstorm_reasoning_effort

        return Agent(
            config=self.agents_config["solution_ideator"],
            llm=ChatOpenAI(**llm_kwargs),
            verbose=True,
        )

    @agent
    def solution_evaluator(self) -> Agent:
        """
        Agent for evaluating solution concepts.
        Uses low temperature/reasoning_effort for consistent, objective scoring.
        Uses brainstorm_llm for reliable structured JSON output.

        GPT-5 series: reasoning_effort from settings
        Older models: temperature=0.2
        """
        # Use build_llm_kwargs for automatic reasoning model detection
        llm_kwargs = build_llm_kwargs(
            model=settings.brainstorm_llm,
            temperature=0.2,  # Ignored for reasoning models
        )
        if settings.brainstorm_reasoning_effort:
            llm_kwargs["reasoning_effort"] = settings.brainstorm_reasoning_effort

        return Agent(
            config=self.agents_config["solution_evaluator"],
            llm=ChatOpenAI(**llm_kwargs),
            verbose=True,
        )

    @agent
    def competitive_researcher(self) -> Agent:
        """
        Agent for competitive research and competitor profiling.
        Uses CompetitorQueryTool for context-aware query generation.
        Uses SerperDevTool for market intelligence.
        Uses function_calling_llm for cost-efficient tool calls.
        Uses max_tokens=30000 to prevent truncation of large CompetitiveAnalysisResult.
        """
        return Agent(
            config=self.agents_config["competitive_researcher"],
            tools=[self.query_tool, self.search_tool],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.3,
                # max_completion_tokens=30000,  # Disabled: CrewAI doesn't forward this properly for reasoning models
            )),
            function_calling_llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.function_calling_llm,
                temperature=0.1,
            )),
            verbose=True,
        )

    @agent
    def market_analyst(self) -> Agent:
        """
        Agent for market gap analysis and positioning strategy.
        Moderate temperature for analytical insights.
        """
        return Agent(
            config=self.agents_config["market_analyst"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.4,
            )),
            verbose=True,
        )

    @agent
    def solution_refiner(self) -> Agent:
        """
        Agent for refining solutions with competitive insights.
        Moderate temperature/reasoning_effort for structured enhancement.
        Uses brainstorm_llm for reliable structured JSON output.

        GPT-5 series: reasoning_effort from settings
        Older models: temperature=0.4
        """
        # Use build_llm_kwargs for automatic reasoning model detection
        llm_kwargs = build_llm_kwargs(
            model=settings.brainstorm_llm,
            temperature=0.4,  # Ignored for reasoning models
        )
        if settings.brainstorm_reasoning_effort:
            llm_kwargs["reasoning_effort"] = settings.brainstorm_reasoning_effort

        return Agent(
            config=self.agents_config["solution_refiner"],
            llm=ChatOpenAI(**llm_kwargs),
            verbose=True,
        )

    @agent
    def strategic_selector(self) -> Agent:
        """
        Agent for strategic solution selection.
        Low temperature for objective decision-making.
        """
        return Agent(
            config=self.agents_config["strategic_selector"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.2,
            )),
            verbose=True,
        )

    # ========== TASKS (New 3-Task Divergent-Convergent Architecture) ==========

    @task
    def divergent_exploration_task(self) -> Task:
        """
        NEW Task 1: Generate 8-12 raw concepts using forced ideation techniques.

        Divergent phase - prioritize quantity and variety over polish.
        Uses high temperature (0.85) for creative diversity.
        Output: RawConceptList with 8-12 lightweight concepts.
        Guardrail: Validates 6+ concepts with name, one_liner, target_keywords.
        """
        return Task(
            config=self.tasks_config["divergent_exploration"],
            agent=self.solution_ideator(),  # High temp (0.85) for creativity
            output_pydantic=RawConceptList,
            guardrail=validate_raw_concepts,
            guardrail_max_retries=2,
        )

    @task
    def diversity_filtering_task(self) -> Task:
        """
        NEW Task 2: Filter raw concepts to ensure diversity.

        Convergent phase - apply strict diversity criteria.
        Clusters similar concepts, enforces architectural variety.
        Output: FilteredConceptList with 5-7 unique concepts.
        Guardrail: Validates 3+ filtered concepts with diversity_summary.
        """
        return Task(
            config=self.tasks_config["diversity_filtering"],
            agent=self.solution_evaluator(),  # Low temp (0.2) for objective filtering
            context=[self.divergent_exploration_task()],
            output_pydantic=FilteredConceptList,
            guardrail=validate_filtered_concepts,
            guardrail_max_retries=2,
        )

    @task
    def solution_refinement_task(self) -> Task:
        """
        Task 3: Expand filtered concepts into full specifications.

        Scores each on market fit, novelty, solo-dev feasibility, SEO.
        Selects top 3-5 for detailed specification.
        Includes diversity guardrail to catch similar solutions.
        Output: IdeaGenerationResult with 3-5 complete solutions.
        """
        return Task(
            config=self.tasks_config["solution_refinement"],
            agent=self.solution_refiner(),  # Moderate temp (0.4) for structured creativity
            context=[self.diversity_filtering_task()],
            output_pydantic=IdeaGenerationResult,
            guardrail=self._diversity_guardrail,  # Enforce diversity in final output
        )

    # ========== COMPETITIVE TASKS ==========

    @task
    def competitive_analysis_task(self) -> Task:
        """
        Task 4: Analyze competitive landscape for solutions.
        Depends on: solution_refinement_task (via context)
        Output: CompetitiveAnalysisResult with per-solution landscapes.

        Guardrail validates JSON completeness to catch truncation from large outputs.
        """
        return Task(
            config=self.tasks_config["competitive_analysis"],
            agent=self.competitive_researcher(),
            context=[self.solution_refinement_task()],
            output_pydantic=CompetitiveAnalysisResult,
            guardrail=validate_competitive_analysis,
            guardrail_max_retries=2,  # Allow 2 retries on truncation
        )

    # competitive_refinement_task removed — competitive analysis is now on-demand per-solution

    @task
    def solution_selection_task(self) -> Task:
        """
        Task 4: Select best solution based on scoring criteria.
        Depends on: solution_refinement_task (full specs)
        Output: SolutionSelection with selected solution and rationale.

        NOTE: Must include solution_refinement_task in context to provide complete solution
        specs with numeric scores (market_fit_score, technical_feasibility_score, etc.).
        """
        return Task(
            config=self.tasks_config["solution_selection"],
            agent=self.strategic_selector(),
            context=[self.solution_refinement_task()],
            output_pydantic=SolutionSelection,
            guardrail=validate_solution_selection,
            guardrail_max_retries=2,
        )


    # ========== CREW ASSEMBLY ==========

    @crew
    def crew(self) -> Crew:
        """
        Assemble UnifiedSolutionCrew with 4-task divergent-convergent pipeline.

        Tasks:
        1. divergent_exploration - Generate 8-12 raw concepts (high creativity)
        2. diversity_filtering - Filter to 5-7 unique concepts
        3. solution_refinement - Expand to full specifications (3-5 solutions)
        4. solution_selection - Select best solution

        Competitive analysis is run on-demand per-solution (not in pipeline).

        Benefits:
        - Forced ideation techniques prevent obvious/similar ideas
        - Explicit diversity filtering catches duplicates
        - Novelty scoring ensures innovation
        - Solo-dev feasibility weighted in scoring
        """
        from ..utils.crew_helpers import create_knowledge
        from ..utils.helpers import sanitize_collection_name

        embedder_config = {
            "provider": "openai",
            "config": {"model_name": "text-embedding-3-small"}
        }

        # 4-task divergent-convergent pipeline
        pipeline_tasks = [
            self.divergent_exploration_task(),   # Task 1: Generate 8-12 raw concepts
            self.diversity_filtering_task(),     # Task 2: Filter to 5-7 unique
            self.solution_refinement_task(),     # Task 3: Expand to full specs
            self.solution_selection_task(),      # Task 4: Select best
        ]

        crew_config = {
            "agents": self.agents,
            "tasks": pipeline_tasks,
            "verbose": True,
            "process_type": "sequential",
            "embedder": embedder_config,
        }

        # Create Knowledge with niche-specific collection name for isolation
        self._crew_knowledge = None
        if self.knowledge_sources:
            niche = self.niche_context.niche_input if self.niche_context else "default"
            collection_name = sanitize_collection_name(niche, "solution", self.job_id)
            logger.info(f"Creating solution knowledge with collection: {collection_name}")
            knowledge = create_knowledge(
                sources=self.knowledge_sources,
                embedder_config=embedder_config,
                collection_name=collection_name,
            )
            if knowledge:
                crew_config["knowledge"] = knowledge
                self._crew_knowledge = knowledge

        return Crew(**crew_config)

    # ========== EXECUTION ==========

    def execute_pipeline(self, skip_selection: bool = False) -> tuple[
        IdeaGenerationResult,
        SolutionSelection | None,
    ]:
        """
        Execute complete solution pipeline using divergent-convergent architecture.

        Architecture:
        1. Divergent Exploration - Generate 8-12 raw concepts with forced ideation
        2. Diversity Filtering - Filter to 5-7 unique concepts
        3. Solution Refinement - Expand to 3-5 full specifications
        4. Solution Selection - Select best solution (skipped when skip_selection=True)

        Competitive analysis is run on-demand per-solution (not in pipeline).

        Args:
            skip_selection: If True, skip Task 4 (LLM selection/scoring).
                Used in interactive mode where the user selects solutions
                and scores are computed from Task 3 fields.

        Returns:
            Tuple of (refined_solutions, solution_selection).
            solution_selection is None when skip_selection=True.
        """
        logger.info("Starting Unified Solution Pipeline (Divergent-Convergent Architecture)...")

        if not self.pain_point_analysis.pain_points:
            logger.warning("No pain points provided - cannot generate solutions")
            return (
                IdeaGenerationResult(
                    solution_ideas=[],
                    recommended_solution=None,
                ),
                SolutionSelection(
                    selected_solution_name="",
                    selection_rationale="No solutions generated",
                    selection_criteria_scores=[],
                    runner_up_solutions=[],
                    recommended_focus=""
                ) if not skip_selection else None,
            )

        try:
            # Use unified formatting helpers
            from ..utils.pain_point_formatters import (
                extract_pain_points_by_priority,
                format_pain_points_for_agents,
            )

            # Extract pain points by priority
            high_priority, medium_priority, low_priority = extract_pain_points_by_priority(
                self.pain_point_analysis
            )

            # Format using unified helper
            high_priority_list = format_pain_points_for_agents(
                pain_points=high_priority,
                format_type="detailed",
                sort_by="severity",
                limit=10,
                include_quotes=True
            )

            medium_priority_list = format_pain_points_for_agents(
                pain_points=medium_priority,
                format_type="compact",
                sort_by="severity",
                limit=10
            )

            # Format niche context for task inputs
            if self.niche_context:
                market_segments_formatted = "\n".join([f"- {seg}" for seg in self.niche_context.market_segments])
                niche_description = self.niche_context.niche_description
                industry_boundaries = self.niche_context.industry_boundaries
            else:
                market_segments_formatted = "Not provided"
                niche_description = "Not provided"
                industry_boundaries = "Not provided"

            # Extract and format user segments from pain point analysis
            user_segments_formatted = ""
            if (self.pain_point_analysis.content_categorization and
                self.pain_point_analysis.content_categorization.user_segments):
                user_segments_formatted = "\n".join([
                    f"**{seg.segment_name}** ({seg.mention_frequency} frequency)\n"
                    f"  Primary concerns: {', '.join(seg.primary_concerns)}"
                    for seg in self.pain_point_analysis.content_categorization.user_segments
                ])
                logger.info(f"Passing {len(self.pain_point_analysis.content_categorization.user_segments)} validated user segments to solution ideation")
            else:
                user_segments_formatted = "Not available"
                logger.warning("No user segments available from pain point analysis")

            # Format audience context for task inputs
            audience_context = self._format_audience_context()
            if self.audience_mapping:
                logger.info(f"Passing audience intelligence: {len(self.audience_mapping.common_vocabulary or [])} vocabulary terms, {len(self.audience_mapping.audience_segments or [])} segments")

            # Execute crew with divergent-convergent pipeline
            task_count = "3-task" if skip_selection else "4-task"
            logger.info(f"Executing Pipeline: Divergent Exploration → Diversity Filtering → Solution Refinement{'' if skip_selection else ' → Selection'} ({task_count} flow)...")
            self._last_crew = self.crew()  # Store for usage_metrics access

            # When skipping selection, trim to first 3 tasks (remove Task 4)
            if skip_selection:
                self._last_crew.tasks = self._last_crew.tasks[:3]

            crew_output = self._last_crew.kickoff(inputs={
                "analysis_summary": self.pain_point_analysis.analysis_summary,
                "high_priority_count": len(high_priority),
                "medium_priority_count": len(medium_priority),
                "high_priority_list": high_priority_list,
                "medium_priority_list": medium_priority_list,
                "top_categories": ', '.join(str(c) for c in (self.pain_point_analysis.top_categories or [])),
                "total_pain_points": len(self.pain_point_analysis.pain_points),
                "total_mentions": self.pain_point_analysis.total_mentions,
                "allowed_project_types": ', '.join(self.allowed_project_types) if self.allowed_project_types else "All types allowed",
                "niche_description": niche_description,
                "market_segments": market_segments_formatted,
                "industry_boundaries": industry_boundaries,
                "user_segments": user_segments_formatted,
                # Audience intelligence from Stage 6.5
                **audience_context,
            })

            # Access intermediate task outputs (CrewAI provides access via crew_output.tasks_outputs)
            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            min_expected = 3 if skip_selection else 4
            if len(task_outputs) < min_expected:
                raise ValueError(
                    f"Expected {min_expected} task outputs, got {len(task_outputs)}. "
                    "Pipeline may have failed mid-execution."
                )

            # Log intermediate outputs for debugging
            raw_concepts = task_outputs[0].pydantic  # RawConceptList
            filtered_concepts = task_outputs[1].pydantic  # FilteredConceptList
            if raw_concepts:
                logger.info(f"  Task 1 (Divergent): Generated {len(raw_concepts.concepts)} raw concepts")
            if filtered_concepts:
                logger.info(f"  Task 2 (Filter): Filtered to {len(filtered_concepts.concepts)} unique concepts")
                if filtered_concepts.removed_concepts:
                    logger.info(f"  Removed {len(filtered_concepts.removed_concepts)} similar concepts")

            # Extract Task 3 (refined solutions) - REQUIRED
            base_solutions = task_outputs[2].pydantic
            if base_solutions is None:
                raise ValueError(
                    "Task 3 (Solution Refinement) returned None pydantic output. "
                    "Check IdeaGenerationResult schema and agent prompt."
                )

            # Post-process: cap novelty_score when text fields are weak
            for solution in base_solutions.solution_ideas:
                if solution.novelty_score and solution.novelty_score > 0.45:
                    ca = (solution.conventional_approach or "").strip()
                    ia = (solution.innovation_angle or "").strip()
                    wiw = (solution.why_it_works or "").strip()
                    if len(ca) < 30 or len(ia) < 30 or len(wiw) < 30:
                        logger.info(
                            f"Capping novelty_score for '{solution.solution_name}' "
                            f"from {solution.novelty_score} to 0.45 (weak text fields)"
                        )
                        solution.novelty_score = 0.45

            # Extract Task 4 (selection) if not skipped
            solution_selection = None
            if not skip_selection:
                solution_selection = crew_output.pydantic
                if solution_selection is None:
                    raise ValueError(
                        "Task 4 (Solution Selection) returned None pydantic output. "
                        "Check task configuration and agent prompt."
                    )

            # Save task-level checkpoints for resume capability
            if self.checkpoint_mgr:
                if raw_concepts:
                    self.checkpoint_mgr.save_stage("stage_5_1_divergent", raw_concepts)
                    logger.debug("Checkpoint saved: stage_7_1_divergent")
                if filtered_concepts:
                    self.checkpoint_mgr.save_stage("stage_5_2_filtered", filtered_concepts)
                    logger.debug("Checkpoint saved: stage_7_2_filtered")
                if base_solutions:
                    self.checkpoint_mgr.save_stage("stage_5_3_refinement", base_solutions)
                    logger.debug("Checkpoint saved: stage_7_3_refinement")
                if solution_selection:
                    self.checkpoint_mgr.save_stage("stage_5_6_selection", solution_selection)
                    logger.debug("Checkpoint saved: stage_7_6_selection")

            # Use base solutions directly (no enhancement merging)
            from copy import deepcopy
            refined_solutions = deepcopy(base_solutions)

            # Log pipeline summary
            removed_count = len(filtered_concepts.removed_concepts) if filtered_concepts else 0

            logger.info("✓ Unified Pipeline Complete:")
            logger.info(f"  - Raw concepts: {len(raw_concepts.concepts) if raw_concepts else 0}")
            logger.info(f"  - Filtered concepts: {len(filtered_concepts.concepts) if filtered_concepts else 0}")
            logger.info(f"  - Removed concepts: {removed_count}")
            logger.info(f"  - Final solutions: {len(refined_solutions.solution_ideas)}")
            if solution_selection:
                logger.info(f"  - Selected: {solution_selection.selected_solution_name}")
            else:
                logger.info("  - Selection: skipped (interactive mode)")

            return (refined_solutions, solution_selection)

        except Exception as e:
            error_msg = str(e)
            # Check if this is a guardrail validation failure
            if "guardrail validation" in error_msg.lower():
                logger.warning(
                    f"Unified solution pipeline failed guardrail validation: {error_msg[:200]}. "
                    "Returning empty results for quality gate evaluation."
                )
                return (
                    IdeaGenerationResult(
                        solution_ideas=[],
                        recommended_solution=None,
                    ),
                    SolutionSelection(
                        selected_solution_name="",
                        selection_rationale="Guardrail validation failed",
                        selection_criteria_scores=[],
                        runner_up_solutions=[],
                        recommended_focus=""
                    ) if not skip_selection else None,
                )
            logger.error(f"Unified pipeline failed: {e}")
            raise

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get usage metrics from the last crew execution.

        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens or None if not available
        """
        if hasattr(self, '_last_crew') and self._last_crew:
            return self._last_crew.usage_metrics
        return None
