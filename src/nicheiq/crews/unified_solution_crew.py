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

import re
from collections import Counter
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..flows.checkpoint_manager import CheckpointManager

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_crew_llm, build_llm_kwargs
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
from ..utils.crew_helpers.content_preparers import format_competitor_mentions_for_prompt
from ..utils.validation import (
    create_diversity_guardrail,
    validate_competitive_analysis,
    validate_filtered_concepts,
    validate_raw_concepts,
    validate_solution_selection,
)


_NAME_STOP_WORDS = {"the", "a", "an", "app", "tool", "pro", "hub", "io", "ai", "my"}


def _tokenize_name(name: str) -> list[str]:
    """Tokenize a concept name into normalized fragments for frequency analysis.

    Order: strip hyphens between alnum → split camelCase → split whitespace/underscores
    → lowercase → filter stop words and short tokens.
    """
    # 1. Strip hyphens between alphanumeric chars (GLP-1 → GLP1, BPC-157 → BPC157)
    result = re.sub(r"(?<=[A-Za-z0-9])-(?=[A-Za-z0-9])", "", name)
    # 2. Split camelCase boundaries (SideEffect → Side Effect, GLP1Side → GLP1 Side)
    result = re.sub(r"([a-z])([A-Z])", r"\1 \2", result)
    result = re.sub(r"([0-9])([A-Z])", r"\1 \2", result)
    # 3. Split on whitespace/underscores
    tokens = re.split(r"[\s_]+", result)
    # 4-5. Lowercase, filter stop words and tokens < 2 chars
    return [t.lower() for t in tokens if len(t) >= 2 and t.lower() not in _NAME_STOP_WORDS]


@CrewBase
class UnifiedSolutionCrew:
    """
    Unified crew consolidating solution pipeline (Stages 7, 8, 8.5, 8.75).

    Implements CrewAI best practices:
    - Output Pydantic models for structured data
    - Context chaining for automatic field preservation
    - Guardrails for validation
    - Direct context injection for pain points, competitors, and themes
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
        existing_ideas: list[dict] | None = None,
        competitor_mentions_text: str | None = None,
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
            job_id: Optional job identifier for tracking
            existing_ideas: Optional list of dicts with "name", optional "description",
                and optional "project_type" keys for previously generated ideas to
                avoid duplicating
            competitor_mentions_text: Optional pre-computed competitor mentions string
                to skip LLM extraction on regeneration
        """
        self.pain_point_analysis = pain_point_analysis
        self.social_content = social_content
        self.allowed_project_types = allowed_project_types
        self.niche_context = niche_context
        self.audience_mapping = audience_mapping
        self.checkpoint_mgr = checkpoint_mgr
        self.job_id = job_id
        self.existing_ideas = existing_ideas or []
        self.competitor_mentions_text = competitor_mentions_text
        self.existing_idea_names = {i["name"].lower() for i in self.existing_ideas if i.get("name")}

        # Initialize search tool for competitive research
        self.search_tool = CachedSerperDevTool()

        # Initialize competitor query generator tool
        self.query_tool = CompetitorQueryTool(niche_context=niche_context)

        # Create diversity guardrail with allowed project types
        self._diversity_guardrail = create_diversity_guardrail(allowed_project_types)

        logger.info(
            f"UnifiedSolutionCrew initialized with {len(pain_point_analysis.pain_points)} pain points "
            f"(direct context injection, no RAG)"
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

    # ========== COMPETITOR MENTIONS HELPER ==========

    def _format_competitor_mentions(self) -> str:
        """Format competitor mentions from social content for direct prompt injection."""
        if self.competitor_mentions_text:
            return self.competitor_mentions_text
        if not self.social_content:
            return "No competitor data available"
        known_tools = (
            self.audience_mapping.tools_currently_used
            if self.audience_mapping and self.audience_mapping.tools_currently_used
            else None
        )
        return format_competitor_mentions_for_prompt(
            self.social_content, known_tools=known_tools
        )

    # ========== BLACKLIST FORMATTING ==========

    def _format_blacklist(self, compact: bool = False) -> str:
        """Format existing ideas as a structured blacklist for prompt injection.

        Args:
            compact: If True, emit short format (names + summary only) for Task 2.
                     If False, emit full format with descriptions for Task 1.

        Returns:
            Formatted blacklist string ready for YAML template injection.
        """
        if not self.existing_ideas:
            return "None (first generation — no previously generated ideas)"

        ideas = self.existing_ideas
        n_ideas = len(ideas)

        # --- Banned name fragments ---
        all_tokens: list[str] = []
        for idea in ideas:
            all_tokens.extend(_tokenize_name(idea.get("name", "")))
        token_counts = Counter(all_tokens)
        freq_threshold = max(2, n_ideas // 3) if n_ideas < 9 else 3
        banned = [t for t, c in token_counts.most_common() if c >= freq_threshold][:15]

        # --- Adaptive description length ---
        if n_ideas <= 15:
            max_desc_len = 200
        elif n_ideas <= 30:
            max_desc_len = 150
        else:
            max_desc_len = 0  # summary one-liner only

        # --- Build per-idea lines ---
        lines: list[str] = []
        for idea in ideas:
            name = idea.get("name", "Unknown")
            desc = idea.get("description", "")
            project_type = idea.get("project_type", "")

            # Summary one-liner: first sentence, capped at 80 chars
            if desc:
                # Split on ". " or " — "
                first_sentence = re.split(r"\. | — ", desc)[0]
                summary = first_sentence[:80].rstrip(".")
            else:
                summary = "(no description available)"

            # Name with optional project type
            name_part = f"{name} ({project_type})" if project_type else name

            if compact:
                lines.append(f"- {name_part} | summary: {summary}")
            else:
                if max_desc_len > 0 and desc:
                    desc_truncated = desc[:max_desc_len] + ("..." if len(desc) > max_desc_len else "")
                    lines.append(f"- {name_part} [summary: {summary}]: {desc_truncated}")
                else:
                    lines.append(f"- {name_part} [summary: {summary}]")

        # --- Assemble output ---
        parts: list[str] = []
        if banned:
            if compact:
                parts.append(f"BANNED FRAGMENTS: {', '.join(banned)}")
            else:
                parts.append(
                    f"BANNED NAME FRAGMENTS (do not reuse in new concept names):\n"
                    f"{', '.join(banned)}"
                )

        if compact:
            parts.append(f"EXISTING IDEAS ({n_ideas} total):")
        else:
            parts.append(f"ALL PREVIOUSLY GENERATED IDEAS ({n_ideas} total):")
        parts.append("\n".join(lines))

        return "\n\n".join(parts)

    # ========== AGENTS ==========

    @agent
    def solution_ideator(self) -> Agent:
        """
        Agent for generating innovative solution concepts.
        Uses configurable brainstorm_llm with high temperature/reasoning_effort.

        GPT-5 series: reasoning_effort from settings (default: high for creative ideation)
        Older models: temperature=0.85, frequency_penalty=0.5, presence_penalty=0.3
        """
        # build_crew_llm: for reasoning models this returns a crewai.LLM that
        # actually forwards reasoning_effort to the API (a ChatOpenAI instance
        # loses it in CrewAI's create_llm conversion — the ideation pipeline
        # previously ran with ALL creativity knobs silently inert).
        return Agent(
            config=self.agents_config["solution_ideator"],
            llm=build_crew_llm(
                model=settings.brainstorm_llm,
                temperature=0.85,
                reasoning_effort=settings.brainstorm_reasoning_effort,
                frequency_penalty=0.5,
                presence_penalty=0.3,
            ),
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
        return Agent(
            config=self.agents_config["solution_evaluator"],
            llm=build_crew_llm(
                model=settings.brainstorm_llm,
                temperature=0.2,  # Used for non-reasoning models only
                reasoning_effort=settings.brainstorm_reasoning_effort,
            ),
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
    def solution_refiner(self) -> Agent:
        """
        Agent for refining solutions with competitive insights.
        Moderate temperature/reasoning_effort for structured enhancement.
        Uses brainstorm_llm for reliable structured JSON output.

        GPT-5 series: reasoning_effort from settings
        Older models: temperature=0.4
        """
        return Agent(
            config=self.agents_config["solution_refiner"],
            llm=build_crew_llm(
                model=settings.brainstorm_llm,
                temperature=0.4,  # Used for non-reasoning models only
                reasoning_effort=settings.brainstorm_reasoning_effort,
            ),
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
            raise ValueError(
                "No pain points provided - cannot generate solutions. "
                "Ensure Stage 3 (Pain Point Analysis) produced results before running Stage 5."
            )

        try:
            # Use unified formatting helpers
            from ..utils.pain_point_formatters import (
                extract_pain_points_by_priority,
                format_pain_points_for_agents,
                select_diverse_pain_points,
            )

            # Extract pain points by priority
            high_priority, medium_priority, low_priority = extract_pain_points_by_priority(
                self.pain_point_analysis
            )

            # Diversified ideation funnel (top-7 severity + top-3 evidence
            # mentions + up to 2 from unrepresented themes) — a pure
            # top-10-by-severity slice fed ideation the same flavor of pain
            # every run and discarded long-tail themes entirely.
            high_priority = select_diverse_pain_points(high_priority)

            # Format using unified helper
            high_priority_list = format_pain_points_for_agents(
                pain_points=high_priority,
                format_type="detailed",
                sort_by="severity",
                limit=12,
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

            # Format theme categories from content categorization
            theme_categories_formatted = ""
            if (self.pain_point_analysis.content_categorization and
                self.pain_point_analysis.content_categorization.theme_categories):
                themes = self.pain_point_analysis.content_categorization.theme_categories
                theme_lines = []
                for t in sorted(themes, key=lambda x: x.mention_count, reverse=True):
                    keywords = ", ".join(f'"{k}"' for k in t.anchor_keywords[:6])
                    theme_lines.append(
                        f"- **{t.category_name}** ({t.mention_count} mentions): "
                        f"keywords: [{keywords}] — {t.definition}"
                    )
                theme_categories_formatted = "\n".join(theme_lines)
                logger.info(f"Passing {len(themes)} theme categories to solution ideation")
            else:
                theme_categories_formatted = "Not available"

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

            # Format existing ideas blacklist for prompt injection
            if self.existing_ideas:
                existing_ideas_blacklist = self._format_blacklist(compact=False)
                existing_ideas_blacklist_compact = self._format_blacklist(compact=True)
                logger.info(f"Injecting {len(self.existing_ideas)} existing ideas into blacklist prompt")
            else:
                existing_ideas_blacklist = "None (first generation — no previously generated ideas)"
                existing_ideas_blacklist_compact = existing_ideas_blacklist

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
                # Existing ideas blacklist for dedup across regeneration runs
                "existing_ideas_blacklist": existing_ideas_blacklist,
                "existing_ideas_blacklist_compact": existing_ideas_blacklist_compact,
                # Direct context injection (replaces RAG)
                "competitor_mentions": self._format_competitor_mentions(),
                "theme_categories": theme_categories_formatted,
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
