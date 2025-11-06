"""
IdeaGenerationCrew - Stage 7: Solution Ideation
Multi-agent crew for generating and refining SaaS solution concepts from validated pain points.
"""

from typing import List

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..models.pain_point import PainPointAnalysisResult
from ..models.solution_idea import IdeaGenerationResult, SolutionIdea


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

    def __init__(self, pain_point_analysis: PainPointAnalysisResult):
        """
        Initialize IdeaGenerationCrew with validated pain points.

        Args:
            pain_point_analysis: Results from PainPointCrew analysis
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.pain_point_analysis = pain_point_analysis

        logger.info(
            f"IdeaGenerationCrew initialized with {len(pain_point_analysis.pain_points)} "
            f"validated pain points"
        )

    @agent
    def solution_ideator(self) -> Agent:
        """
        Agent responsible for generating innovative SaaS solution concepts.
        Focuses on MVP-first approach and practical feasibility.
        """
        return Agent(
            config=self.agents_config["solution_ideator"],
            verbose=True,
        )

    @agent
    def solution_evaluator(self) -> Agent:
        """
        Agent responsible for evaluating solution concepts.
        Assesses technical feasibility, market fit, and differentiation.
        """
        return Agent(
            config=self.agents_config["solution_evaluator"],
            verbose=True,
        )

    @agent
    def solution_refiner(self) -> Agent:
        """
        Agent responsible for refining solutions into comprehensive proposals.
        Adds personas, features, pricing, and positioning details.
        """
        return Agent(
            config=self.agents_config["solution_refiner"],
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

    @crew
    def crew(self) -> Crew:
        """
        Assemble the IdeaGenerationCrew with all agents and tasks.

        Returns:
            Configured Crew instance
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
            process_type="sequential",
        )

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
            # Prepare pain points context for ideation
            high_priority = [
                pp for pp in self.pain_point_analysis.pain_points
                if pp.opportunity_level.value == "high"
            ]
            medium_priority = [
                pp for pp in self.pain_point_analysis.pain_points
                if pp.opportunity_level.value == "medium"
            ]

            # Format high-priority pain points with detailed information
            high_priority_list = "\n".join([
                f"**{i+1}. {pp.title}**\n"
                f"- Problem: {pp.description}\n"
                f"- Severity: {pp.severity_score:.2f} | WTP: {pp.willingness_to_pay:.2f}\n"
                f"- Mentions: {pp.mention_count} across {', '.join(str(p) for p in (pp.source_platforms if pp.source_platforms else []))}\n"
                f"- Key Quote: \"{pp.representative_quotes[0] if pp.representative_quotes else 'N/A'}\"\n"
                for i, pp in enumerate(high_priority[:5])
            ]) if high_priority else "[None identified]"

            # Format medium-priority pain points (summary only)
            medium_priority_list = "\n".join([
                f"**{pp.title}** (Severity: {pp.severity_score:.2f}, WTP: {pp.willingness_to_pay:.2f})"
                for pp in medium_priority[:5]
            ]) if medium_priority else "[None identified]"

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
                "total_mentions": self.pain_point_analysis.total_mentions
            })

            # Extract the Pydantic model from CrewOutput
            result = crew_output.pydantic
            logger.info(
                f"Solution ideation complete: {len(result.solution_ideas)} "
                f"solutions generated"
            )
            return result

        except Exception as e:
            logger.error(f"Solution ideation failed: {e}")
            raise
