"""
LandingPageCrew - Generates unique, fully-designed HTML landing pages.

4-Agent Pipeline:
0. Marketing Strategist -> Creates strategic landing page brief
1. Brand Designer -> Creates unique color palette and design mood
2. Copywriter -> Writes conversion-optimized copy following strategy
3. HTML Developer -> Generates complete HTML with Tailwind CSS

Each run produces a unique design tailored to the specific product.
The Marketing Strategist defines the "one memorable element" that makes
the page stand out from generic AI-generated content.
"""

from typing import Optional

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_llm_kwargs
from ..models.landing_page import (
    BrandIdentity,
    HTMLPageResult,
    LandingPageCopy,
    LandingPageResult,
    LandingStrategy,
)
from ..models.research_state import FinalReport


@CrewBase
class LandingPageCrew:
    """
    Generates unique, fully-designed landing pages from research reports.

    4-Agent Pipeline:
    0. Marketing Strategist -> Creates strategic brief with persona, messaging, memorable element
    1. Brand Designer -> Creates color palette and design mood aligned with strategy
    2. Copywriter -> Writes copy following strategic direction
    3. HTML Developer -> Generates complete HTML implementing the memorable element

    Each run produces a unique design tailored to the specific product.
    The Marketing Strategist defines the "one memorable element" that makes
    each page stand out from generic AI-generated content.
    """

    agents_config = "config/landing_page_agents.yaml"
    tasks_config = "config/landing_page_tasks.yaml"

    def __init__(self):
        """Initialize LandingPageCrew."""
        logger.info("LandingPageCrew initialized")

    # ========== AGENTS ==========

    @agent
    def marketing_strategist(self) -> Agent:
        """
        Creates strategic landing page brief before design/copy.
        Moderate temperature (0.7) for strategic creativity while
        maintaining focus on research data.
        """
        return Agent(
            config=self.agents_config["marketing_strategist"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.7,  # Strategic creativity (ignored for reasoning models)
            )),
            verbose=True,
        )

    @agent
    def brand_designer(self) -> Agent:
        """
        Creates unique brand identity based on product category.
        High temperature (0.8) for creative, unique color choices.
        """
        return Agent(
            config=self.agents_config["brand_designer"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.8,  # High creativity for unique colors (ignored for reasoning models)
            )),
            verbose=True,
        )

    @agent
    def landing_page_copywriter(self) -> Agent:
        """
        Writes conversion-optimized copy and decides which sections to include.
        Moderate temperature (0.7) for creative but focused copy.
        """
        return Agent(
            config=self.agents_config["landing_page_copywriter"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.7,  # Creative but focused (ignored for reasoning models)
            )),
            verbose=True,
        )

    @agent
    def html_developer(self) -> Agent:
        """
        Generates complete HTML pages with Tailwind CSS.
        Lower temperature (0.3) for valid, working code.
        """
        return Agent(
            config=self.agents_config["html_developer"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.3,  # Lower for valid code (ignored for reasoning models)
            )),
            verbose=True,
        )

    # ========== TASKS ==========

    @task
    def create_landing_strategy_task(self) -> Task:
        """Task 0: Create strategic landing page brief."""
        return Task(
            config=self.tasks_config["create_landing_strategy"],
            agent=self.marketing_strategist(),
            output_pydantic=LandingStrategy,
        )

    @task
    def design_brand_identity_task(self) -> Task:
        """Task 1: Design unique brand identity aligned with strategy."""
        return Task(
            config=self.tasks_config["design_brand_identity"],
            agent=self.brand_designer(),
            context=[self.create_landing_strategy_task()],  # Chain from strategy
            output_pydantic=BrandIdentity,
        )

    @task
    def generate_landing_copy_task(self) -> Task:
        """Task 2: Write landing page copy following strategic direction."""
        return Task(
            config=self.tasks_config["generate_landing_copy"],
            agent=self.landing_page_copywriter(),
            context=[
                self.create_landing_strategy_task(),  # Include strategy
                self.design_brand_identity_task(),
            ],
            output_pydantic=LandingPageCopy,
        )

    @task
    def generate_html_page_task(self) -> Task:
        """Task 3: Generate complete HTML implementing the memorable element."""
        return Task(
            config=self.tasks_config["generate_html_page"],
            agent=self.html_developer(),
            context=[
                self.create_landing_strategy_task(),  # Include strategy for memorable element
                self.design_brand_identity_task(),
                self.generate_landing_copy_task(),
            ],
            output_pydantic=HTMLPageResult,
        )

    # ========== CREW ==========

    @crew
    def crew(self) -> Crew:
        """Create the Landing Page Generator crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
        )

    # ========== PUBLIC API ==========

    def generate(self, report: FinalReport) -> LandingPageResult:
        """
        Generate complete landing page from research report.

        Args:
            report: FinalReport from NicheIQ pipeline

        Returns:
            LandingPageResult with brand, copy, and HTML
        """
        logger.info(f"Generating landing page for: {report.selected_solution_name}")

        # Extract inputs from report
        inputs = self._extract_inputs(report)

        # Log input summary
        logger.info(f"Extracted inputs: product_name={inputs['product_name']}, "
                   f"solution_type={inputs['solution_type']}, "
                   f"features_count={len(inputs['features'].split(',')) if inputs['features'] else 0}")

        # Run the crew
        result = self.crew().kickoff(inputs=inputs)

        # Extract outputs from each task (4 tasks now)
        strategy = result.tasks_output[0].pydantic
        brand_identity = result.tasks_output[1].pydantic
        copy = result.tasks_output[2].pydantic
        html_result = result.tasks_output[3].pydantic

        logger.info(f"Landing page generated with {len(html_result.sections_included)} sections")
        logger.info(f"Primary persona: {strategy.primary_persona}")
        logger.info(f"Memorable element: {strategy.memorable_element[:100]}...")
        logger.info(f"Design mood: {brand_identity.design_mood}")
        logger.info(f"Section selection reasoning: {copy.section_selection_reasoning[:100]}...")

        return LandingPageResult(
            landing_strategy=strategy,
            brand_identity=brand_identity,
            page_copy=copy,
            html_output=html_result.html_content,
            sections_generated=html_result.sections_included,
            generation_notes=html_result.design_notes,
        )

    def _extract_inputs(self, report: FinalReport) -> dict:
        """
        Extract crew inputs from FinalReport.

        Maps FinalReport fields to the placeholders in task YAML.
        """
        # Get solution details
        solution_details = report.selected_solution_details

        # Extract features as comma-separated string
        features = ""
        if solution_details and solution_details.core_features:
            features = "\n".join(f"- {f}" for f in solution_details.core_features[:5])

        # Extract target personas
        target_personas = ""
        if solution_details and solution_details.target_personas:
            target_personas = "\n".join(f"- {p}" for p in solution_details.target_personas[:4])

        # Extract value proposition
        value_proposition = ""
        if solution_details and solution_details.value_proposition:
            value_proposition = solution_details.value_proposition

        # Extract user journey
        user_journey = report.solution_user_journey or "Not available"

        # Extract pricing summary
        pricing_summary = "Join waitlist for early pricing"
        if report.pricing_strategy:
            ps = report.pricing_strategy
            pricing_summary = f"Starter: {ps.recommended_starter_price} | Pro: {ps.recommended_pro_price}"
            if ps.pricing_rationale:
                pricing_summary += f"\n{ps.pricing_rationale[:200]}"

        # Extract quotes for social proof
        quotes = "Not available"
        if report.top_pain_points:
            quotes = "\n".join(f'"{pp}"' for pp in report.top_pain_points[:3])

        # Extract solution type
        solution_type = "saas"
        if solution_details and solution_details.project_type:
            solution_type = solution_details.project_type

        # Extract project type for brand design
        project_type = solution_type

        return {
            "product_name": report.selected_solution_name,
            "solution_type": solution_type,
            "project_type": project_type,
            "target_personas": target_personas or "SaaS users looking for this solution",
            "value_proposition": value_proposition or report.executive_summary[:200],
            "pain_points": "\n".join(f"- {pp}" for pp in report.top_pain_points[:5]),
            "pain_points_summary": report.pain_points_summary[:500] if report.pain_points_summary else "",
            "features": features or "Core product features",
            "user_journey": user_journey,
            "pricing_summary": pricing_summary,
            "competitive_summary": report.competitive_summary[:500] if report.competitive_summary else "",
            "quotes": quotes,
        }
