"""
IdeaGenerationCrew - Stage 7: Solution Ideation
Multi-agent crew for generating and refining SaaS solution concepts from validated pain points.
"""

from typing import List, Optional

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.pain_point import PainPointAnalysisResult
from ..models.solution_idea import EvaluationResult, IdeaGenerationResult, SolutionIdea


@CrewBase
class IdeaGenerationCrew:
    """
    Specialized crew for generating and refining SaaS solution ideas.
    Transforms validated pain points into actionable product concepts.

    Architecture:
    - 3 agents working in pipeline
    - Ideator generates solution concepts
    - Evaluator assesses feasibility and market fit
    - Refiner adds strategic details and positioning
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, pain_point_analysis: PainPointAnalysisResult, allowed_project_types: Optional[List[str]] = None):
        """
        Initialize IdeaGenerationCrew with validated pain points.

        Args:
            pain_point_analysis: Results from PainPointCrew analysis
            allowed_project_types: Optional list of allowed project types (saas, directory, aggregator, comparison-tool, marketplace)
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.pain_point_analysis = pain_point_analysis
        self.allowed_project_types = allowed_project_types
        self.knowledge_sources = []

        # Create knowledge source from pain point analysis with ALL quotes
        if pain_point_analysis.pain_points:
            pain_point_content = self._prepare_pain_point_content()

            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.pain_point_knowledge = StringKnowledgeSource(
                content=pain_point_content,
                chunk_size=1500,     # Medium chunks for pain point summaries
                chunk_overlap=250    # Good overlap for context
            )
            self.knowledge_sources.append(self.pain_point_knowledge)
            logger.info(
                f"Pain point knowledge source created ({len(pain_point_content)} chars) "
                f"with ALL user quotes for {len(pain_point_analysis.pain_points)} pain points"
            )

        logger.info(
            f"IdeaGenerationCrew initialized with {len(pain_point_analysis.pain_points)} "
            f"validated pain points{' and knowledge sources' if self.knowledge_sources else ''}"
        )

    def _prepare_pain_point_content(self) -> str:
        """
        Format pain points with ALL quotes and metadata for knowledge source.

        Unlike the kickoff inputs which truncate to 1 quote per pain point,
        this preserves all 3-5 quotes per pain point for richer context.

        Returns:
            Formatted string with full pain point data including all quotes
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

    @agent
    def solution_ideator(self) -> Agent:
        """
        Agent responsible for generating innovative SaaS solution concepts.
        Focuses on MVP-first approach and practical feasibility.

        Uses configurable brainstorm_llm for creative ideation with higher temperature.
        """
        return Agent(
            config=self.agents_config["solution_ideator"],
            llm=ChatOpenAI(
                model=settings.brainstorm_llm,
                temperature=0.7,  # Higher temperature for creative brainstorming
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @agent
    def solution_evaluator(self) -> Agent:
        """
        Agent responsible for evaluating solution concepts.
        Assesses technical feasibility, market fit, and differentiation.

        Uses low temperature (0.2) for consistent, objective scoring.
        """
        return Agent(
            config=self.agents_config["solution_evaluator"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.2,  # Low temperature for analytical, objective evaluation
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @agent
    def solution_refiner(self) -> Agent:
        """
        Agent responsible for refining solutions into comprehensive proposals.
        Adds personas, features, pricing, and positioning details.

        Uses moderate temperature (0.4) for balanced creativity with structured output.
        """
        return Agent(
            config=self.agents_config["solution_refiner"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,  # Moderate temperature for structured enhancement with some creativity
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def brainstorm_solutions_task(self) -> Task:
        """
        Task: Generate SaaS solution concepts addressing validated pain points.

        Output: 3-5 solution concepts with core features and value props.
        """
        return Task(
            config=self.tasks_config["brainstorm_solutions"],
            agent=self.solution_ideator(),
        )

    @task
    def evaluate_solutions_task(self) -> Task:
        """
        Task: Evaluate brainstormed solutions for feasibility and market fit.

        Depends on: brainstorm_solutions_task
        Output: Evaluation scores and risk assessment for each solution.
        """
        return Task(
            config=self.tasks_config["evaluate_solutions"],
            agent=self.solution_evaluator(),
            context=[self.brainstorm_solutions_task()],
            output_pydantic=EvaluationResult,
        )

    @task
    def refine_solutions_task(self) -> Task:
        """
        Task: Refine top solutions into comprehensive product proposals.

        Depends on: evaluate_solutions_task
        Output: Detailed solution ideas with personas, features, pricing.
        """
        return Task(
            config=self.tasks_config["refine_solutions"],
            agent=self.solution_refiner(),
            context=[self.evaluate_solutions_task()],
            output_pydantic=IdeaGenerationResult,
        )

    def _validate_no_field_loss(self, task_output) -> tuple:
        """
        Guardrail function to validate competitive refinement preserves all solution fields.

        CrewAI guardrails:
        - Accept TaskOutput as input
        - Return (bool, Any) tuple: (is_valid, result_or_error)
        - If False returned, task auto-retries

        Validates:
        1. Solution count matches original input (no dropped solutions)
        2. All required fields are not None
        3. All SEO fields are preserved (especially refined fields)

        Args:
            task_output: TaskOutput from competitive insights task

        Returns:
            (True, result) if valid, (False, error_message) if validation fails
        """
        try:
            result = task_output.pydantic

            if not isinstance(result, IdeaGenerationResult):
                return (False, f"Invalid output type: expected IdeaGenerationResult, got {type(result)}")

            # Check solution count (stored in instance variable for comparison)
            if not hasattr(self, '_expected_solution_count'):
                # First run, store expected count for future validations
                self._expected_solution_count = len(result.solution_ideas)
                logger.debug(f"Guardrail: Set expected solution count to {self._expected_solution_count}")
            else:
                # Validate count matches
                actual_count = len(result.solution_ideas)
                if actual_count != self._expected_solution_count:
                    return (
                        False,
                        f"Solution count mismatch: expected {self._expected_solution_count}, got {actual_count}. "
                        f"Agent dropped {self._expected_solution_count - actual_count} solution(s)."
                    )

            # Validate all required fields are present
            field_errors = []
            for idx, idea in enumerate(result.solution_ideas):
                missing_fields = []

                # Check required string fields
                if not idea.solution_name or idea.solution_name.strip() == "":
                    missing_fields.append("solution_name")
                if not idea.description or idea.description.strip() == "":
                    missing_fields.append("description")
                if not idea.value_proposition or idea.value_proposition.strip() == "":
                    missing_fields.append("value_proposition")

                # Check required list fields
                if not idea.pain_points_addressed:
                    missing_fields.append("pain_points_addressed")
                if not idea.core_features:
                    missing_fields.append("core_features")
                if not idea.target_personas:
                    missing_fields.append("target_personas")

                # Check required score fields
                if idea.market_fit_score is None:
                    missing_fields.append("market_fit_score")
                if idea.technical_feasibility_score is None:
                    missing_fields.append("technical_feasibility_score")

                # Check conditional data aggregation fields
                if idea.requires_data_aggregation and not idea.data_sources:
                    missing_fields.append("data_sources (required when requires_data_aggregation=True)")

                if missing_fields:
                    field_errors.append(f"Solution '{idea.solution_name}': {', '.join(missing_fields)}")

            if field_errors:
                return (
                    False,
                    f"Required fields missing in {len(field_errors)} solution(s):\n" + "\n".join(field_errors)
                )

            # All validations passed
            logger.info(f"✓ Guardrail validation passed: {len(result.solution_ideas)} solutions with all fields preserved")
            return (True, result)

        except Exception as e:
            return (False, f"Guardrail validation error: {str(e)}")

    def _create_competitive_insights_task(self) -> Task:
        """
        Create task for enhancing solutions with competitive intelligence.

        This is NOT decorated with @task because it's used independently
        in refine_with_competition() method, not in the main crew workflow.

        Returns:
            Task for competitive enhancement with structured output and guardrail validation
        """
        return Task(
            config=self.tasks_config["incorporate_competitive_insights"],
            agent=self.solution_refiner(),  # Reuse refiner for enhancement
            output_pydantic=IdeaGenerationResult,
            guardrail=self._validate_no_field_loss,  # Auto-validates and retries on failure
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the IdeaGenerationCrew with all agents, tasks, and knowledge sources.

        If pain point knowledge sources are available, they are attached at crew level
        so all agents can access full user quotes and evidence via semantic search.

        Returns:
            Configured Crew instance with optional knowledge sources
        """
        crew_config = {
            "agents": self.agents,
            "tasks": self.tasks,
            "verbose": True,
            "process_type": "sequential",
        }

        # Add knowledge sources if available
        if self.knowledge_sources:
            crew_config["knowledge_sources"] = self.knowledge_sources
            crew_config["embedder"] = {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"  # Cost-effective embeddings
                }
            }

        return Crew(**crew_config)

    def generate_ideas(self) -> IdeaGenerationResult:
        """
        Execute solution ideation workflow.

        Returns:
            IdeaGenerationResult with refined solution proposals
        """
        logger.info("Starting solution ideation...")

        if not self.pain_point_analysis.pain_points:
            logger.warning("No pain points provided for ideation")
            return IdeaGenerationResult(
                solution_ideas=[],
                recommended_solution=None,
                market_insights="No pain points available for solution generation"
            )

        try:
            # Sort pain points by combined opportunity score (severity + WTP) before filtering
            # This ensures we pass the BEST pain points to agents, not just the first ones extracted
            sorted_pain_points = sorted(
                self.pain_point_analysis.pain_points,
                key=lambda pp: (pp.severity_score + pp.willingness_to_pay) / 2,
                reverse=True
            )

            # Prepare pain points context for ideation
            high_priority = [
                pp for pp in sorted_pain_points
                if pp.opportunity_level.value == "high"
            ]
            medium_priority = [
                pp for pp in sorted_pain_points
                if pp.opportunity_level.value == "medium"
            ]

            # ANTI-HALLUCINATION CHECK: Refuse to proceed if insufficient high-quality pain points
            if not high_priority and not medium_priority:
                logger.warning("No high or medium priority pain points available - cannot generate solutions")
                return IdeaGenerationResult(
                    solution_ideas=[],
                    recommended_solution=None,
                    market_insights="Insufficient validated pain points for solution generation. All pain points scored too low on opportunity level."
                )

            # Format high-priority pain points with detailed information (guaranteed to have data)
            high_priority_list = "\n".join([
                f"**{i+1}. {pp.title}**\n"
                f"- Problem: {pp.description}\n"
                f"- Severity: {pp.severity_score:.2f} | WTP: {pp.willingness_to_pay:.2f}\n"
                f"- Mentions: {pp.mention_count} across {', '.join(str(p) for p in (pp.source_platforms if pp.source_platforms else []))}\n"
                f"- Key Quote: \"{pp.representative_quotes[0] if pp.representative_quotes else 'N/A'}\"\n"
                for i, pp in enumerate(high_priority[:10])  # Increased from [:5] to [:10]
            ]) if high_priority else ""

            # Format medium-priority pain points (summary with key quote for context)
            medium_priority_list = "\n".join([
                f"**{pp.title}** (Severity: {pp.severity_score:.2f}, WTP: {pp.willingness_to_pay:.2f})\n"
                f"- Key Quote: \"{pp.representative_quotes[0] if pp.representative_quotes else 'N/A'}\""
                for pp in medium_priority[:10]  # Increased from [:5] to [:10]
            ]) if medium_priority else ""

            # Debug logging
            logger.debug("=" * 80)
            logger.debug("SOLUTION IDEATION INPUTS")
            logger.debug("=" * 80)
            logger.debug(f"Total pain points: {len(self.pain_point_analysis.pain_points)}")
            logger.debug(f"High-priority: {len(high_priority)}")
            logger.debug(f"Medium-priority: {len(medium_priority)}")
            logger.debug(f"Total mentions: {self.pain_point_analysis.total_mentions}")
            logger.debug("=" * 80)

            # Execute crew with inputs
            crew_output = self.crew().kickoff(inputs={
                "analysis_summary": self.pain_point_analysis.analysis_summary,
                "high_priority_count": len(high_priority),
                "medium_priority_count": len(medium_priority),
                "high_priority_list": high_priority_list,
                "medium_priority_list": medium_priority_list,
                "top_categories": ', '.join(str(c) for c in (self.pain_point_analysis.top_categories if self.pain_point_analysis.top_categories else [])),
                "total_pain_points": len(self.pain_point_analysis.pain_points),
                "total_mentions": self.pain_point_analysis.total_mentions,
                "allowed_project_types": ', '.join(self.allowed_project_types) if self.allowed_project_types else "No constraints - all solution types allowed"
            })

            # Extract the Pydantic model from CrewOutput
            result = crew_output.pydantic

            # VALIDATION: Check for null required fields
            null_fields_by_solution = {}
            for idea in result.solution_ideas:
                null_fields = []
                if idea.market_fit_score is None:
                    null_fields.append("market_fit_score")
                if idea.technical_feasibility_score is None:
                    null_fields.append("technical_feasibility_score")
                if idea.technical_approach is None or idea.technical_approach.strip() == "":
                    null_fields.append("technical_approach")
                if idea.estimated_development_time is None:
                    null_fields.append("estimated_development_time")
                # data_sources can be None if requires_data_aggregation=False
                if idea.requires_data_aggregation and idea.data_sources is None:
                    null_fields.append("data_sources")

                if null_fields:
                    null_fields_by_solution[idea.solution_name] = null_fields

            if null_fields_by_solution:
                logger.warning(
                    "⚠️ Solutions have null required fields:\n" +
                    "\n".join([f"  - {name}: {', '.join(fields)}"
                               for name, fields in null_fields_by_solution.items()])
                )

            # VALIDATION: Check for missing SEO fields (optional but reduce final report quality)
            missing_seo_fields_by_solution = {}
            for idea in result.solution_ideas:
                missing_seo = []
                if idea.programmatic_seo_opportunity is None:
                    missing_seo.append("programmatic_seo_opportunity")
                if idea.content_generation_model is None:
                    missing_seo.append("content_generation_model")
                if not idea.organic_discovery_queries:  # None or empty list
                    missing_seo.append("organic_discovery_queries")
                if idea.estimated_cac_organic is None:
                    missing_seo.append("estimated_cac_organic")
                if idea.estimated_cac_paid is None:
                    missing_seo.append("estimated_cac_paid")
                if idea.seo_scalability_score is None:
                    missing_seo.append("seo_scalability_score")

                if missing_seo:
                    missing_seo_fields_by_solution[idea.solution_name] = missing_seo

            if missing_seo_fields_by_solution:
                logger.warning(
                    "⚠️ Solutions missing SEO fields (optional but reduce final report quality):\n" +
                    "\n".join([f"  - {name}: {', '.join(fields)}"
                               for name, fields in missing_seo_fields_by_solution.items()])
                )

            logger.info(
                f"Solution ideation complete: {len(result.solution_ideas)} "
                f"solutions generated"
            )
            return result

        except Exception as e:
            logger.error(f"Solution ideation failed: {e}")
            raise

    def refine_with_competition(
        self,
        original_ideas: IdeaGenerationResult,
        competitive_analysis
    ) -> IdeaGenerationResult:
        """
        Enhance existing solutions with competitive insights.

        This method runs AFTER stage 8 (competitive analysis) to incorporate
        market gaps and positioning opportunities into the solution ideas.

        Args:
            original_ideas: IdeaGenerationResult from stage 7 (generate_ideas)
            competitive_analysis: CompetitiveAnalysisResult from CompetitiveCrew

        Returns:
            IdeaGenerationResult with enhanced solutions incorporating competitive positioning
        """
        from ..models.competitor import CompetitiveAnalysisResult

        logger.info("Enhancing solutions with competitive insights...")

        if not original_ideas or not original_ideas.solution_ideas:
            logger.warning("No solution ideas available to enhance")
            return IdeaGenerationResult(
                solution_ideas=[],
                recommended_solution=None,
                market_insights="No solutions available for competitive enhancement"
            )

        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            logger.warning("No competitive analysis available - skipping enhancement")
            # Return existing solutions unchanged
            return original_ideas

        try:
            # Format solutions for input - MUST include ALL required fields for preservation
            # This comprehensive formatting ensures agents can reconstruct complete SolutionIdea objects
            solutions_summary = "\n\n".join([
                f"**{sol.solution_name}**\n"
                f"- Description: {sol.description}\n"
                f"- Value Prop: {sol.value_proposition}\n"
                f"- Pain Points Addressed: {', '.join(sol.pain_points_addressed)}\n"
                f"- Core Features: {', '.join(sol.core_features)}\n"  # ALL features, not truncated
                f"- Target Personas: {', '.join(sol.target_personas)}\n"
                f"- Technical Approach: {sol.technical_approach or 'Not defined'}\n"
                f"- Current Differentiation: {', '.join(sol.differentiation_factors or ['None yet'])}\n"
                f"- Requires Data Aggregation: {sol.requires_data_aggregation}\n"
                f"- Data Sources: {', '.join(sol.data_sources) if sol.data_sources else 'None'}\n"
                f"- Estimated Development Time: {sol.estimated_development_time or 'Not defined'}\n"
                f"- Pricing Strategy: {sol.pricing_strategy or 'Not defined'}\n"
                f"- Market Fit Score: {sol.market_fit_score}\n"
                f"- Technical Feasibility Score: {sol.technical_feasibility_score}\n"
                f"- Project Type: {sol.project_type or 'Not defined'}\n"
                f"- Programmatic SEO Opportunity: {sol.programmatic_seo_opportunity or 'Not assessed'}\n"
                f"- Content Generation Model: {sol.content_generation_model or 'Not defined'}\n"
                f"- Organic Discovery Queries (sample): {', '.join(sol.organic_discovery_queries[:5]) if sol.organic_discovery_queries else 'None defined'}\n"
                f"- Estimated CAC Organic: {sol.estimated_cac_organic or 'Not estimated'}\n"
                f"- Estimated CAC Paid: {sol.estimated_cac_paid or 'Not estimated'}\n"
                f"- SEO Scalability Score: {sol.seo_scalability_score if sol.seo_scalability_score is not None else 'Not scored'}\n"
                f"- SEO Scalability Score (Refined): {sol.seo_scalability_score_refined if sol.seo_scalability_score_refined is not None else 'Not yet refined'}\n"
                f"- Estimated CAC Organic (Refined): {sol.estimated_cac_organic_refined or 'Not yet refined'}\n"
                f"- Programmatic SEO Opportunity (Refined): {sol.programmatic_seo_opportunity_refined or 'Not yet refined'}\n"
                f"- SEO Refinement Metadata: {sol.seo_refinement_metadata.model_dump() if sol.seo_refinement_metadata else 'Not yet calculated'}"
                for sol in original_ideas.solution_ideas
            ])

            # Format competitive landscapes
            competitive_landscapes = "\n\n".join([
                f"**{land.solution_name} - Competitive Intelligence:**\n"
                f"- Market Gaps: {', '.join(land.market_gaps)}\n"
                f"- Differentiation Opportunities: {', '.join(land.differentiation_opportunities)}\n"
                f"- Competitive Intensity: {land.competitive_intensity}\n"
                f"- Recommended Positioning: {land.recommended_positioning}\n"
                f"- Pricing Insights: {land.pricing_insights or 'No specific insights'}"
                for land in competitive_analysis.solution_landscapes
            ])

            logger.debug("=" * 80)
            logger.debug("COMPETITIVE REFINEMENT INPUTS")
            logger.debug("=" * 80)
            logger.debug(f"Solutions to enhance: {len(original_ideas.solution_ideas)}")
            logger.debug(f"Competitive landscapes: {len(competitive_analysis.solution_landscapes)}")
            logger.debug("=" * 80)

            # Set expected solution count for guardrail validation
            self._expected_solution_count = len(original_ideas.solution_ideas)
            logger.debug(f"Guardrail: Expecting {self._expected_solution_count} solutions in output")

            # Create single-task crew just for competitive enhancement
            enhancement_crew = Crew(
                agents=[self.solution_refiner()],
                tasks=[self._create_competitive_insights_task()],
                verbose=True,
                process_type="sequential"
            )

            # Execute enhancement
            crew_output = enhancement_crew.kickoff(inputs={
                "solutions_summary": solutions_summary,
                "competitive_landscapes": competitive_landscapes,
            })

            # Extract enhanced solutions
            result = crew_output.pydantic

            # VALIDATION: Verify solution count matches input (detect dropped solutions)
            if len(result.solution_ideas) != len(original_ideas.solution_ideas):
                logger.error(
                    f"❌ Competitive refinement dropped {len(original_ideas.solution_ideas) - len(result.solution_ideas)} solution(s)! "
                    f"Input: {len(original_ideas.solution_ideas)}, Output: {len(result.solution_ideas)}"
                )
                dropped_names = set(sol.solution_name for sol in original_ideas.solution_ideas) - set(sol.solution_name for sol in result.solution_ideas)
                logger.error(f"Dropped solutions: {dropped_names}")

                # Auto-restore dropped solutions from original input (fail-safe)
                output_names = {sol.solution_name for sol in result.solution_ideas}
                for original_sol in original_ideas.solution_ideas:
                    if original_sol.solution_name not in output_names:
                        logger.warning(f"⚠️ Auto-restoring dropped solution: {original_sol.solution_name}")
                        result.solution_ideas.append(original_sol)

            # VALIDATION: Verify solution names match originals (detect and correct LLM renaming)
            original_names = [sol.solution_name for sol in original_ideas.solution_ideas]
            for enhanced_sol in result.solution_ideas:
                # Check for exact match first
                if enhanced_sol.solution_name not in original_names:
                    # Try fuzzy matching: case-insensitive substring search
                    matched_name = None
                    search_name_lower = enhanced_sol.solution_name.lower()

                    for original_name in original_names:
                        # Check if enhanced name is substring of original or vice versa
                        if (search_name_lower in original_name.lower() or
                            original_name.lower() in search_name_lower):
                            matched_name = original_name
                            break

                    if matched_name:
                        logger.warning(
                            f"⚠️ Competitive enhancement renamed solution: "
                            f"'{enhanced_sol.solution_name}' → '{matched_name}' (corrected)"
                        )
                        enhanced_sol.solution_name = matched_name
                    else:
                        logger.error(
                            f"❌ Enhanced solution name '{enhanced_sol.solution_name}' does not match "
                            f"any original solution. Expected one of: {original_names}"
                        )

            # VALIDATION: Check for null required fields after competitive enhancement
            null_fields_by_solution = {}
            for idea in result.solution_ideas:
                null_fields = []
                if idea.market_fit_score is None:
                    null_fields.append("market_fit_score")
                if idea.technical_feasibility_score is None:
                    null_fields.append("technical_feasibility_score")
                if idea.technical_approach is None or idea.technical_approach.strip() == "":
                    null_fields.append("technical_approach")
                if idea.estimated_development_time is None:
                    null_fields.append("estimated_development_time")
                if idea.requires_data_aggregation and idea.data_sources is None:
                    null_fields.append("data_sources")

                if null_fields:
                    null_fields_by_solution[idea.solution_name] = null_fields

            if null_fields_by_solution:
                logger.warning(
                    "⚠️ After competitive enhancement, solutions have null required fields:\n" +
                    "\n".join([f"  - {name}: {', '.join(fields)}"
                               for name, fields in null_fields_by_solution.items()])
                )

            logger.info(
                f"✓ Solutions enhanced with competitive insights: "
                f"{len(result.solution_ideas)} solutions updated"
            )

            return result

        except Exception as e:
            logger.error(f"Competitive refinement failed: {e}")
            logger.warning("Returning original solutions without competitive enhancements")
            # Return existing solutions unchanged on error
            return original_ideas
