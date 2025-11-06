"""
CompetitiveCrew - Stage 8: Competitive Analysis
Multi-agent crew for researching competitors and identifying market opportunities.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult, CompetitiveLandscape
from ..models.solution_idea import IdeaGenerationResult, SolutionIdea


@CrewBase
class CompetitiveCrew:
    """
    Specialized crew for competitive intelligence and market analysis.
    Maps competitive landscape and identifies differentiation opportunities.

    Architecture:
    - 2 agents working in pipeline
    - Researcher discovers and profiles competitors
    - Analyst identifies gaps and positioning strategies
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, solution_ideas: IdeaGenerationResult):
        """
        Initialize CompetitiveCrew with refined solution ideas.

        Args:
            solution_ideas: Results from IdeaGenerationCrew
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.solution_ideas = solution_ideas

        # Initialize search tool for competitive research
        self.search_tool = SerperDevTool()

        logger.info(
            f"CompetitiveCrew initialized with {len(solution_ideas.solution_ideas)} "
            f"solution concepts"
        )

    @agent
    def competitive_researcher(self) -> Agent:
        """
        Agent responsible for discovering and profiling competitors.
        Uses search tools to find existing solutions and alternatives.
        """
        return Agent(
            config=self.agents_config["competitive_researcher"],
            tools=[self.search_tool],
            verbose=True,
        )

    @agent
    def competitive_analyst(self) -> Agent:
        """
        Agent responsible for analyzing competitive landscape.
        Identifies gaps, opportunities, and differentiation strategies.
        """
        return Agent(
            config=self.agents_config["competitive_analyst"],
            verbose=True,
        )

    @task
    def research_competitors_task(self) -> Task:
        """
        Task: Research existing competitors and alternative solutions.

        Output: Comprehensive competitive landscape mapping.
        """
        return Task(
            config=self.tasks_config["research_competitors"],
            agent=self.competitive_researcher(),
        )

    @task
    def analyze_competitive_landscape_task(self) -> Task:
        """
        Task: Analyze competitive research to identify opportunities.

        Depends on: research_competitors_task
        Output: Strategic analysis with gaps and differentiation strategies.
        """
        return Task(
            config=self.tasks_config["analyze_competitive_landscape"],
            agent=self.competitive_analyst(),
            context=[self.research_competitors_task()],
            output_pydantic=CompetitiveAnalysisResult,
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the CompetitiveCrew with all agents and tasks.

        Returns:
            Configured Crew instance
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
            process_type="sequential",
        )

    def _analyze_single_solution(self, idea: SolutionIdea, index: int, total: int) -> CompetitiveLandscape:
        """
        Analyze a single solution's competitive landscape.

        Args:
            idea: Solution idea to analyze
            index: Current solution number (1-based)
            total: Total number of solutions

        Returns:
            CompetitiveLandscape for this solution
        """
        logger.info(f"[{index}/{total}] Researching solution: {idea.solution_name}")
        logger.debug(f"  Value Proposition: {idea.value_proposition}")

        # Format single solution for crew input
        solution_data = (
            f"### Solution: {idea.solution_name}\n"
            f"**Value Proposition:** {idea.value_proposition}\n"
            f"**Description:** {idea.description}\n"
            f"**Target Users:** {'; '.join(str(p) for p in (idea.target_personas[:2] if idea.target_personas else ['Not specified']))}\n"
            f"**Key Features:** {', '.join(str(f) for f in (idea.core_features[:5] if idea.core_features else ['Not specified']))}\n"
            f"**Pain Points Solved:** {', '.join(str(p) for p in (idea.pain_points_addressed if idea.pain_points_addressed else ['Not specified']))}"
        )

        # Execute crew for this single solution
        crew_output = self.crew().kickoff(inputs={
            "solution_count": 1,
            "market_insights": self.solution_ideas.market_insights,
            "recommended_solution": f"Focus on {idea.solution_name}",
            "solutions_list": solution_data
        })

        # Extract the Pydantic model from CrewOutput
        single_result = crew_output.pydantic

        # Return the landscape for this solution
        if single_result.solution_landscapes:
            landscape = single_result.solution_landscapes[0]
            competitors_found = len(landscape.competitors)
            logger.info(f"[{index}/{total}] ✓ Completed {idea.solution_name}: {competitors_found} competitor(s) identified")
            return landscape
        else:
            logger.warning(f"[{index}/{total}] ✗ No landscape data returned for {idea.solution_name}")
            # Return empty landscape
            return CompetitiveLandscape(
                solution_name=idea.solution_name,
                competitors=[],
                market_gaps=["Analysis incomplete"],
                differentiation_opportunities=["Further research needed"],
                competitive_intensity="Unknown - analysis incomplete",
                recommended_positioning="Requires additional research",
                pricing_insights="Insufficient data"
            )

    def analyze_competition(self, parallel: bool = True, max_workers: int = 2) -> CompetitiveAnalysisResult:
        """
        Execute competitive analysis workflow.

        Args:
            parallel: If True, analyze solutions in parallel (default: True)
            max_workers: Maximum parallel workers (default: 2, conservative for API limits)

        Returns:
            CompetitiveAnalysisResult with landscape and opportunities
        """
        total_solutions = len(self.solution_ideas.solution_ideas)
        mode = "parallel" if parallel and total_solutions > 1 else "sequential"
        logger.info(f"Starting competitive analysis for {total_solutions} solution(s) in {mode} mode...")

        if not self.solution_ideas.solution_ideas:
            logger.warning("No solution ideas provided for competitive analysis")
            return CompetitiveAnalysisResult(
                solution_landscapes=[],
                top_opportunities=[],
                strategic_recommendations="No solution ideas available for competitive analysis"
            )

        try:
            all_landscapes = []

            if parallel and total_solutions > 1:
                # Parallel processing with ThreadPoolExecutor
                logger.info(f"Using parallel processing with {max_workers} worker(s)")

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all solutions for analysis
                    future_to_solution = {
                        executor.submit(
                            self._analyze_single_solution,
                            idea,
                            i,
                            total_solutions
                        ): idea
                        for i, idea in enumerate(self.solution_ideas.solution_ideas, 1)
                    }

                    # Collect results as they complete
                    for future in as_completed(future_to_solution):
                        solution_idea = future_to_solution[future]
                        try:
                            landscape = future.result()
                            all_landscapes.append(landscape)
                        except Exception as e:
                            logger.error(f"Failed to analyze {solution_idea.solution_name}: {e}")
                            # Add a placeholder landscape for failed analysis
                            all_landscapes.append(CompetitiveLandscape(
                                solution_name=solution_idea.solution_name,
                                competitors=[],
                                market_gaps=[f"Analysis failed: {str(e)}"],
                                differentiation_opportunities=["Retry recommended"],
                                competitive_intensity="Unknown - analysis failed",
                                recommended_positioning="Analysis incomplete",
                                pricing_insights="Analysis failed"
                            ))
            else:
                # Sequential processing (original behavior)
                logger.info("Using sequential processing")

                for i, idea in enumerate(self.solution_ideas.solution_ideas, 1):
                    landscape = self._analyze_single_solution(idea, i, total_solutions)
                    all_landscapes.append(landscape)

            # Aggregate insights across all solutions
            logger.info("Generating cross-solution strategic insights...")

            # Collect all differentiation opportunities from individual solutions
            all_opportunities = []
            for landscape in all_landscapes:
                all_opportunities.extend(landscape.differentiation_opportunities)

            # Take top 5 unique opportunities
            top_opportunities = list(dict.fromkeys(all_opportunities))[:5]

            # Generate strategic recommendations summary
            total_competitors = sum(len(l.competitors) for l in all_landscapes)
            strategic_recommendations = (
                f"Analyzed {len(all_landscapes)} solution(s) across the competitive landscape. "
                f"Total of {total_competitors} competitors identified. "
                f"Key insights: {' '.join(all_landscapes[0].market_gaps[:2]) if all_landscapes and all_landscapes[0].market_gaps else 'Market validation needed.'}"
            )

            result = CompetitiveAnalysisResult(
                solution_landscapes=all_landscapes,
                top_opportunities=top_opportunities if top_opportunities else ["Further market research recommended"],
                strategic_recommendations=strategic_recommendations
            )

            logger.info(
                f"Competitive analysis complete: {len(result.solution_landscapes)} "
                f"landscape(s) analyzed, {len(result.top_opportunities)} top opportunities identified"
            )
            return result

        except Exception as e:
            logger.error(f"Competitive analysis failed: {e}")
            raise
