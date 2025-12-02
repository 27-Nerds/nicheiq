"""
UnifiedSolutionCrew - Stages 7-8.75: Complete Solution Pipeline
Consolidates solution ideation, competitive analysis, refinement, and selection into unified multi-task flow.

Architecture (CrewAI Best Practice - Context Chaining):
- Task 1: Solution Ideation (brainstorm + evaluate + refine)
- Task 2: Competitive Analysis (parallel per solution)
- Task 3: Competitive Refinement (enhance with insights)
- Task 4: Solution Selection (score and select best)

Benefits over separate crews:
- Automatic field preservation via output_pydantic + context chaining
- No manual data formatting between stages
- Guardrails ensure no data loss
- Follows CrewAI documentation best practices
"""

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..flows.checkpoint_manager import CheckpointManager

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import BaseTool
from crewai_tools import SerperDevTool
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import NicheContext
from ..models.social_content import SocialContentCollection
from ..models.solution_idea import (
    CompetitiveEnhancements,
    IdeaGenerationResult,
)
from ..models.solution_selection import SolutionSelection
from ..utils.generation import CompetitorQueryGenerator


class CompetitorQueryTool(BaseTool):
    """
    Tool for generating context-aware competitor search queries.
    Uses CompetitorQueryGenerator with semantic validation.
    """
    name: str = "generate_competitor_queries"
    description: str = (
        "Generate strategic competitor search queries for a solution. "
        "Input format: 'solution_name|project_type|pain_points' "
        "(pain_points is comma-separated list, optional). "
        "Returns list of validated search queries with rationale."
    )

    _generator: CompetitorQueryGenerator = None
    _niche_context: NicheContext | None = None

    def __init__(self, niche_context: NicheContext | None = None, **kwargs):
        super().__init__(**kwargs)
        self._generator = CompetitorQueryGenerator()
        self._niche_context = niche_context

    def _run(self, input_str: str) -> str:
        """Generate competitor queries from input string."""
        parts = input_str.split("|")
        solution_name = parts[0].strip() if len(parts) > 0 else ""
        project_type = parts[1].strip() if len(parts) > 1 else "saas"
        pain_points = [p.strip() for p in parts[2].split(",")] if len(parts) > 2 and parts[2].strip() else None

        queries = self._generator.generate_competitor_queries(
            solution_name=solution_name,
            project_type=project_type,
            niche_context=self._niche_context,
            pain_points_addressed=pain_points,
            num_queries=8
        )

        if not queries:
            return "No queries generated. Try with different input."

        # Format output for agent consumption
        result = f"Generated {len(queries)} competitor search queries:\n\n"
        for i, q in enumerate(queries, 1):
            result += f"{i}. [{q.get('type', 'category')}] {q.get('query')}\n"
            result += f"   Rationale: {q.get('rationale', 'N/A')}\n\n"

        return result

class CachedSerperDevTool(SerperDevTool):
    """
    Wrapper around SerperDevTool that caches search results within a session.
    Reduces redundant API calls when multiple solutions have overlapping competitors.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
        self._hits = 0
        self._misses = 0

    def run(self, search_query: str, **kwargs):
        """Execute search with caching."""
        cache_key = search_query.strip().lower()

        if cache_key in self._cache:
            self._hits += 1
            logger.debug(f"Cache hit for: {search_query[:50]}... (hits: {self._hits})")
            return self._cache[cache_key]

        self._misses += 1
        logger.debug(f"Cache miss for: {search_query[:50]}... (misses: {self._misses})")
        result = super().run(search_query, **kwargs)
        self._cache[cache_key] = result

        return result

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
        checkpoint_mgr: "CheckpointManager | None" = None,
    ):
        """
        Initialize UnifiedSolutionCrew with pain points and optional context.

        Args:
            pain_point_analysis: Validated pain points from PainPointCrew
            social_content: Optional social content for competitor intelligence
            allowed_project_types: Optional constraints on project types
            niche_context: Optional structured niche context with market segments and boundaries
            checkpoint_mgr: Optional checkpoint manager for task-level saves
        """
        self.pain_point_analysis = pain_point_analysis
        self.social_content = social_content
        self.allowed_project_types = allowed_project_types
        self.niche_context = niche_context
        self.checkpoint_mgr = checkpoint_mgr

        # Initialize search tool for competitive research
        self.search_tool = CachedSerperDevTool()

        # Initialize competitor query generator tool
        self.query_tool = CompetitorQueryTool(niche_context=niche_context)

        # Initialize knowledge sources
        self.knowledge_sources = []

        # Prepare pain point knowledge source (for Task 1)
        if pain_point_analysis.pain_points:
            pain_point_content = self._prepare_pain_point_content()
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
            competitor_intel = self._prepare_competitor_intelligence(social_content)
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

        logger.info(
            f"UnifiedSolutionCrew initialized with {len(pain_point_analysis.pain_points)} pain points "
            f"and {len(self.knowledge_sources)} knowledge sources"
        )

    def _prepare_pain_point_content(self) -> str:
        """
        Format pain points with ALL quotes for knowledge source.
        Preserves all 3-5 quotes per pain point for richer context.
        """
        formatted = []
        for pp in self.pain_point_analysis.pain_points:
            formatted.append(f"""[PAIN POINT: {pp.title}]
[SEVERITY: {pp.severity_score:.2f}]
[WILLINGNESS TO PAY: {pp.willingness_to_pay:.2f}]
[OPPORTUNITY LEVEL: {pp.opportunity_level.value}]
[MENTIONS: {pp.mention_count}]
[PLATFORMS: {', '.join(pp.source_platforms if pp.source_platforms else ['N/A'])}]
[CATEGORIES: {', '.join(pp.categories if pp.categories else ['N/A'])}]

### Problem Description:
{pp.description}

### All User Evidence ({len(pp.representative_quotes)} quotes):
{chr(10).join(f'- "{quote}"' for quote in pp.representative_quotes)}
""")
        return "\n\n===\n\n".join(formatted)

    def _prepare_competitor_intelligence(self, social_content: SocialContentCollection) -> str:
        """
        Extract competitor and tool mentions from social discussions.
        Filters content for existing tools, alternatives, comparisons, pricing.
        """
        competitor_indicators = [
            # Usage patterns
            "using", "used", "tried", "currently use", "switched from", "switched to",
            # Comparisons and alternatives
            "alternative", "instead of", "compared to", "better than", "worse than",
            # Tool/product names and categories
            "tool", "platform", "service", "app", "software", "website",
            # Pricing and value
            "price", "cost", "expensive", "cheap", "affordable", "worth",
            "subscription", "free", "paid", "trial",
        ]

        # Performance optimization: Compile indicators into regex pattern
        # Reduces O(n*m*k) to O(n*m) where k=indicator count
        indicator_pattern = re.compile(
            '|'.join(re.escape(indicator) for indicator in competitor_indicators),
            re.IGNORECASE
        )

        # Filter Reddit posts for competitor mentions
        filtered_reddit = []
        for post in social_content.reddit_posts:
            # Check post title and body
            content_lower = (post.title + " " + (post.selftext or "")).lower()
            if indicator_pattern.search(content_lower):
                filtered_reddit.append(post)
            else:
                # Check comments for competitor mentions
                for comment in post.comments:
                    if indicator_pattern.search(comment.body.lower()):
                        filtered_reddit.append(post)
                        break

        # Filter Twitter threads for competitor mentions
        filtered_twitter = []
        for thread in social_content.twitter_threads:
            content_lower = thread.root_tweet.text.lower()
            if indicator_pattern.search(content_lower):
                filtered_twitter.append(thread)
            else:
                # Check replies
                for reply in thread.replies:
                    if indicator_pattern.search(reply.text.lower()):
                        filtered_twitter.append(thread)
                        break

        if not filtered_reddit and not filtered_twitter:
            logger.info("No competitor mentions found in social content")
            return ""

        # Format filtered content
        formatted = []

        # Reddit competitor intelligence
        if filtered_reddit:
            formatted.append("[REDDIT COMPETITOR INTELLIGENCE]\n")
            for post in filtered_reddit:
                formatted.append(f"""[SUBREDDIT: r/{post.subreddit}]
[SCORE: {post.score}]

### {post.title}

{post.selftext}

---
## Discussion ({len(post.comments)} comments):
{chr(10).join(f'- "{c.body}"' for c in post.comments[:10])}  # First 10 comments
""")

        # Twitter competitor intelligence
        if filtered_twitter:
            formatted.append("\n\n[TWITTER COMPETITOR INTELLIGENCE]\n")
            for thread in filtered_twitter:
                formatted.append(f"""[LIKES: {thread.root_tweet.likes}]

### Root Tweet:
{thread.root_tweet.text}

---
## Replies ({len(thread.replies)} total):
{chr(10).join(f'- "{r.text}"' for r in thread.replies[:10])}  # First 10 replies
""")

        logger.info(
            f"Filtered competitor intelligence: {len(filtered_reddit)} Reddit posts, "
            f"{len(filtered_twitter)} Twitter threads"
        )

        return "\n\n===\n\n".join(formatted)

    # ========== AGENTS ==========

    @agent
    def solution_ideator(self) -> Agent:
        """
        Agent for generating innovative solution concepts.
        Uses configurable brainstorm_llm with higher temperature for creativity.
        """
        return Agent(
            config=self.agents_config["solution_ideator"],
            llm=ChatOpenAI(
                model=settings.brainstorm_llm,
                temperature=0.7,
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @agent
    def solution_evaluator(self) -> Agent:
        """
        Agent for evaluating solution concepts.
        Uses low temperature for consistent, objective scoring.
        """
        return Agent(
            config=self.agents_config["solution_evaluator"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.2,
                api_key=settings.openai_api_key
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
        """
        return Agent(
            config=self.agents_config["competitive_researcher"],
            tools=[self.query_tool, self.search_tool],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.3,
                api_key=settings.openai_api_key
            ),
            function_calling_llm=ChatOpenAI(
                model=settings.function_calling_llm,  # gpt-4o-mini for cost-efficient tool calls
                temperature=0.1,  # Low temperature for reliable tool execution
                api_key=settings.openai_api_key
            ),
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
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @agent
    def solution_refiner(self) -> Agent:
        """
        Agent for refining solutions with competitive insights.
        Moderate temperature for structured enhancement.
        """
        return Agent(
            config=self.agents_config["solution_refiner"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,
                api_key=settings.openai_api_key
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
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.2,
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    # ========== TASKS ==========

    @task
    def solution_ideation_task(self) -> Task:
        """
        Task 1: Generate and refine solution concepts from pain points.
        Output: IdeaGenerationResult with 3-5 solutions.
        """
        return Task(
            config=self.tasks_config["solution_ideation"],
            agent=self.solution_ideator(),
            output_pydantic=IdeaGenerationResult,
        )

    @task
    def competitive_analysis_task(self) -> Task:
        """
        Task 2: Analyze competitive landscape for ALL solutions.
        Depends on: solution_ideation_task (via context)
        Output: CompetitiveAnalysisResult with per-solution landscapes.
        """
        return Task(
            config=self.tasks_config["competitive_analysis"],
            agent=self.competitive_researcher(),
            context=[self.solution_ideation_task()],
            output_pydantic=CompetitiveAnalysisResult,
        )

    @task
    def competitive_refinement_task(self) -> Task:
        """
        Task 3: Generate competitive enhancements for solutions.

        Generates ONLY enhancements based on competitive analysis:
        - new_core_features (2-4 NEW features from competitive gaps)
        - new_differentiation_factors (2-3 NEW factors)
        - value_proposition_update (if competitive analysis suggests changes)
        - pricing_strategy_update (if competitive analysis suggests changes)
        - market_fit_score_adjustment (±0.1 if justified)

        All base solution fields from Task 1 will be preserved via Python merge in execute_pipeline().

        Depends on: solution_ideation_task + competitive_analysis_task (via context)
        Output: CompetitiveEnhancements (enhancements only)
        """
        return Task(
            config=self.tasks_config["competitive_refinement"],
            agent=self.solution_refiner(),
            context=[self.solution_ideation_task(), self.competitive_analysis_task()],
            output_pydantic=CompetitiveEnhancements,
            guardrail=self._validate_enhancements_output,
        )

    def _validate_enhancements_output(self, task_output) -> tuple[bool, Any]:
        """
        Guardrail for competitive_refinement_task to ensure valid enhancement output.

        Validates:
        - Pydantic output exists
        - solution_enhancements list is populated
        - Each enhancement has required fields

        Returns:
            tuple[bool, Any]: (success, result_or_error)
        """
        try:
            result = task_output.pydantic
            if result is None:
                return (False, "Competitive refinement returned None pydantic output")

            if not isinstance(result, CompetitiveEnhancements):
                return (False, f"Invalid output type: expected CompetitiveEnhancements, got {type(result)}")

            # Validate solution_enhancements exists and has entries
            if not result.solution_enhancements:
                return (False, "solution_enhancements list cannot be empty - must have at least 1 enhancement")

            # Validate each enhancement has required solution_name
            for i, enh in enumerate(result.solution_enhancements):
                if not enh.solution_name or enh.solution_name.strip() == "":
                    return (False, f"Enhancement {i} missing solution_name")

            logger.info(f"✓ Enhancements guardrail passed: {len(result.solution_enhancements)} solution enhancements")
            return (True, result)

        except Exception as e:
            return (False, f"Enhancement validation error: {str(e)}")

    @task
    def solution_selection_task(self) -> Task:
        """
        Task 4: Select best solution based on scoring criteria.
        Depends on: competitive_refinement_task (via context)
        Output: SolutionSelection with selected solution and rationale.
        """
        return Task(
            config=self.tasks_config["solution_selection"],
            agent=self.strategic_selector(),
            context=[self.competitive_refinement_task()],
            output_pydantic=SolutionSelection,
        )

    # ========== GUARDRAILS ==========

    def _validate_no_field_loss(self, task_output) -> tuple[bool, Any]:
        """
        Guardrail for competitive_refinement_task to ensure no data loss.
        Validates solution count and required fields are preserved.

        Returns:
            tuple[bool, Any]: (success: bool, result_or_error: Any)
        """
        try:
            result = task_output.pydantic

            if not isinstance(result, IdeaGenerationResult):
                return (False, f"Invalid output type: expected IdeaGenerationResult, got {type(result)}")

            # DETECT SCHEMA OUTPUT BUG: Agent returned JSON Schema instead of populated data
            if len(result.solution_ideas) == 0:
                logger.error("⚠️ Task 3 returned empty solution_ideas list - possible schema confusion")
                logger.error(f"Output type: {type(result)}")

                # Check raw output for schema indicators
                if hasattr(task_output, 'raw') and task_output.raw:
                    raw_preview = str(task_output.raw)[:1000]
                    logger.error(f"Raw output preview: {raw_preview}")

                    # Detect schema structure patterns
                    if any(indicator in task_output.raw for indicator in [
                        '"additionalProperties"',
                        '"properties":',
                        '"type": "object"',
                        '"required": ['
                    ]):
                        return (
                            False,
                            "Agent returned JSON Schema definition instead of populated data. "
                            "Task prompt includes concrete examples - agent must extract actual values from Task 1 context "
                            "and output populated IdeaGenerationResult with real solution data."
                        )

                return (False, "Empty solution_ideas list - agent must extract solutions from Task 1 context")

            # Check solution count matches input (stored during crew execution)
            if hasattr(self, '_expected_solution_count'):
                actual_count = len(result.solution_ideas)
                if actual_count != self._expected_solution_count:
                    return (
                        False,
                        f"Solution count mismatch: expected {self._expected_solution_count}, got {actual_count}"
                    )

            # Validate required fields
            field_errors = []
            for idea in result.solution_ideas:
                missing_fields = []

                if not idea.solution_name or idea.solution_name.strip() == "":
                    missing_fields.append("solution_name")
                if not idea.description or idea.description.strip() == "":
                    missing_fields.append("description")
                if not idea.pain_points_addressed:
                    missing_fields.append("pain_points_addressed")
                if not idea.core_features:
                    missing_fields.append("core_features")
                if idea.market_fit_score is None:
                    missing_fields.append("market_fit_score")
                if idea.technical_feasibility_score is None:
                    missing_fields.append("technical_feasibility_score")

                if missing_fields:
                    field_errors.append(f"Solution '{idea.solution_name}': {', '.join(missing_fields)}")

            if field_errors:
                return (False, "Required fields missing:\n" + "\n".join(field_errors))

            logger.info(f"✓ Guardrail passed: {len(result.solution_ideas)} solutions with all fields preserved")
            return (True, result)

        except Exception as e:
            return (False, f"Guardrail validation error: {str(e)}")

    # ========== CREW ASSEMBLY ==========

    @crew
    def crew(self) -> Crew:
        """
        Assemble UnifiedSolutionCrew with 4 sequential tasks and knowledge sources.
        """
        from crewai.knowledge.knowledge import Knowledge
        from ..utils.helpers import sanitize_collection_name

        embedder_config = {
            "provider": "openai",
            "config": {"model_name": "text-embedding-3-small"}
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
            # Get niche from context for collection naming
            niche = self.niche_context.niche_input if self.niche_context else "default"
            collection_name = sanitize_collection_name(niche, "solution")
            logger.info(f"Creating solution knowledge with collection: {collection_name}")
            knowledge = Knowledge(
                sources=self.knowledge_sources,
                embedder=embedder_config,
                collection_name=collection_name,
            )
            knowledge.add_sources()
            crew_config["knowledge"] = knowledge

        return Crew(**crew_config)

    # ========== EXECUTION ==========

    def execute_pipeline(self) -> tuple[IdeaGenerationResult, CompetitiveAnalysisResult, SolutionSelection]:
        """
        Execute complete solution pipeline (4 tasks).

        Returns:
            Tuple of (refined_solutions, competitive_analysis, solution_selection)
        """
        logger.info("Starting Unified Solution Pipeline (Stages 7-8.75)...")

        if not self.pain_point_analysis.pain_points:
            logger.warning("No pain points provided - cannot generate solutions")
            return (
                IdeaGenerationResult(
                    solution_ideas=[],
                    recommended_solution=None,
                    market_insights="No pain points available"
                ),
                CompetitiveAnalysisResult(solution_landscapes=[], market_insights="Skipped - no solutions"),
                SolutionSelection(
                    selected_solution_name="",
                    selection_rationale="No solutions generated",
                    selection_criteria_scores=[],
                    runner_up_solutions=[],
                    recommended_focus=""
                )
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

            # Execute crew with unified pipeline
            logger.info("Executing Task 1: Solution Ideation...")
            crew_output = self.crew().kickoff(inputs={
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
                "user_segments": user_segments_formatted
            })

            # Extract final result (Task 4 output - SolutionSelection)
            solution_selection = crew_output.pydantic
            if solution_selection is None:
                raise ValueError(
                    "Task 4 (Solution Selection) returned None pydantic output. "
                    "Check task configuration and agent prompt."
                )

            # Access intermediate task outputs (CrewAI provides access via crew_output.tasks_outputs)
            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            if len(task_outputs) < 4:
                raise ValueError(
                    f"Expected 4 task outputs, got {len(task_outputs)}. "
                    "Pipeline may have failed mid-execution."
                )

            # Extract Task 1 (base solutions) - REQUIRED
            base_solutions = task_outputs[0].pydantic
            if base_solutions is None:
                raise ValueError(
                    "Task 1 (Solution Ideation) returned None pydantic output. "
                    "Check IdeaGenerationResult schema and agent prompt."
                )

            # Extract Task 2 (competitive analysis) - REQUIRED
            competitive_analysis = task_outputs[1].pydantic
            if competitive_analysis is None:
                raise ValueError(
                    "Task 2 (Competitive Analysis) returned None pydantic output. "
                    "Check CompetitiveAnalysisResult schema and agent prompt."
                )

            # Extract Task 3 (enhancements) - OPTIONAL (can be None if no enhancements generated)
            enhancements = task_outputs[2].pydantic  # CompetitiveEnhancements or None

            # Save task-level checkpoints for resume capability
            if self.checkpoint_mgr:
                if base_solutions:
                    self.checkpoint_mgr.save_stage("stage_7_1_ideation", base_solutions)
                    logger.debug("Checkpoint saved: stage_7_1_ideation")
                if competitive_analysis:
                    self.checkpoint_mgr.save_stage("stage_7_2_competitive", competitive_analysis)
                    logger.debug("Checkpoint saved: stage_7_2_competitive")
                if enhancements:
                    self.checkpoint_mgr.save_stage("stage_7_3_refinement", enhancements)
                    logger.debug("Checkpoint saved: stage_7_3_refinement")

            # Python merge: Apply enhancements to base solutions
            from copy import deepcopy
            refined_solutions = deepcopy(base_solutions)

            if enhancements and enhancements.solution_enhancements:
                for solution in refined_solutions.solution_ideas:
                    # Find matching enhancement
                    enhancement = next(
                        (e for e in enhancements.solution_enhancements if e.solution_name == solution.solution_name),
                        None
                    )

                    if enhancement:
                        # Merge new features (extend, don't replace)
                        if enhancement.new_core_features:
                            solution.core_features = list(set(solution.core_features + enhancement.new_core_features))

                        # Merge new differentiation factors
                        if enhancement.new_differentiation_factors:
                            solution.differentiation_factors = list(set(
                                solution.differentiation_factors + enhancement.new_differentiation_factors
                            ))

                        # Update value proposition if refined
                        if enhancement.value_proposition_update:
                            solution.value_proposition = enhancement.value_proposition_update

                        # Update pricing strategy if refined
                        if enhancement.pricing_strategy_update:
                            solution.pricing_strategy = enhancement.pricing_strategy_update

                        # Adjust market fit score if suggested
                        if enhancement.market_fit_score_adjustment:
                            solution.market_fit_score = min(10.0, max(0.0,
                                solution.market_fit_score + enhancement.market_fit_score_adjustment
                            ))

                logger.info(
                    f"[OK] Applied competitive enhancements to {len(refined_solutions.solution_ideas)} solutions"
                )

            logger.info("✓ Unified Pipeline Complete:")
            logger.info(f"  - Generated {len(refined_solutions.solution_ideas)} solutions")
            logger.info(f"  - Analyzed {len(competitive_analysis.solution_landscapes)} competitive landscapes")
            logger.info(f"  - Selected: {solution_selection.selected_solution_name}")

            return (refined_solutions, competitive_analysis, solution_selection)

        except Exception as e:
            logger.error(f"Unified pipeline failed: {e}")
            raise
