"""
Technical Blueprint Crew - Stage 10.5: Site Structure and User Flows.

Generates personalized site architecture and user journey maps based on
the selected solution's features, personas, and project type.
"""


from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.technical_blueprint import SiteStructure, UserFlowsSection
from ..utils.llm_service import build_crew_llm
from ..utils.validation.crew_guardrails import validate_site_structure, validate_user_flows


@CrewBase
class TechnicalBlueprintCrew:
    """
    Crew for generating site structure and user flows.

    Stage 10.5: Creates personalized site architecture and user journey maps
    based on the selected solution's features, personas, and project type.

    Two-agent, two-task crew:
    1. Product Architect - Designs site structure (pages, URLs, priorities)
    2. UX Designer - Maps user flows for target personas
    """

    agents_config = "config/technical_blueprint_agents.yaml"
    tasks_config = "config/technical_blueprint_tasks.yaml"

    def __init__(self):
        """Initialize TechnicalBlueprintCrew."""
        pass  # @CrewBase handles parent init

    @agent
    def product_architect(self) -> Agent:
        """
        Product Architect agent specializing in site structure design.

        Designs SEO-optimized site architecture with programmatic page
        strategies and MVP prioritization.
        """
        return Agent(
            config=self.agents_config["product_architect"],
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.4,  # Balanced: structured but creative
            ),
            verbose=True,
        )

    @agent
    def ux_designer(self) -> Agent:
        """
        UX Designer agent specializing in user flow mapping.

        Maps realistic user journeys for target personas with
        conversion-focused design.
        """
        return Agent(
            config=self.agents_config["ux_designer"],
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.5,  # Slightly higher for flow variety
            ),
            verbose=True,
        )

    @task
    def site_structure_task(self) -> Task:
        """
        Design the site architecture.

        Creates a complete site structure with sections, pages, URLs,
        and MVP prioritization.
        """
        return SafeTask(
            config=self.tasks_config["site_structure_task"],
            agent=self.product_architect(),
            output_pydantic=SiteStructure,
            guardrail=validate_site_structure,
            guardrail_max_retries=2,
        )

    @task
    def user_flows_task(self) -> Task:
        """
        Design user journey flows.

        Creates 2-3 realistic user flows showing how personas discover,
        use, and convert on the product.
        """
        return SafeTask(
            config=self.tasks_config["user_flows_task"],
            agent=self.ux_designer(),
            output_pydantic=UserFlowsSection,
            context=[self.site_structure_task()],  # Uses site structure for page references
            guardrail=validate_user_flows,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the technical blueprint crew.

        Sequential two-agent crew: Product Architect -> UX Designer.
        """
        return Crew(
            agents=[self.product_architect(), self.ux_designer()],
            tasks=[self.site_structure_task(), self.user_flows_task()],
            verbose=True,
        )

    def generate(
        self,
        solution_name: str,
        description: str,
        project_type: str,
        core_features: list[str],
        target_personas: list[str],
        data_sources: list[str],
        estimated_indexable_pages: int,
        content_generation_model: str,
        value_proposition: str,
        organic_discovery_queries: list[str],
        pricing_strategy: str,
    ) -> tuple[SiteStructure | None, UserFlowsSection | None]:
        """
        Execute crew and return site structure and user flows.

        Args:
            solution_name: Name of the selected solution
            description: Solution description
            project_type: Project type (saas, directory, aggregator, etc.)
            core_features: List of core features
            target_personas: List of target personas
            data_sources: List of data sources
            estimated_indexable_pages: Estimated number of programmatic pages
            content_generation_model: How content is generated
            value_proposition: Solution value proposition
            organic_discovery_queries: SEO discovery queries
            pricing_strategy: Pricing/monetization strategy

        Returns:
            Tuple of (SiteStructure, UserFlowsSection) or (None, None) on failure
        """
        logger.info("[Stage 10.5] Starting Technical Blueprint generation...")
        logger.info(f"  Solution: {solution_name}")
        logger.info(f"  Project Type: {project_type}")

        # Format inputs for crew
        inputs = {
            "solution_name": solution_name,
            "description": description[:500] if description else "",
            "project_type": project_type or "saas",
            "core_features": "\n".join(f"- {f}" for f in (core_features or [])[:8]),
            "target_personas": "\n".join(f"- {p}" for p in (target_personas or [])[:4]),
            "data_sources": ", ".join(data_sources) if data_sources else "None",
            "estimated_indexable_pages": estimated_indexable_pages or 50,
            "content_generation_model": content_generation_model or "Manual content",
            "value_proposition": (value_proposition or description or "")[:300],
            "organic_discovery_queries": ", ".join((organic_discovery_queries or [])[:5]),
            "pricing_strategy": (pricing_strategy or "Freemium model")[:300],
        }

        try:
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            # Extract results from sequential tasks
            site_structure = None
            user_flows = None

            # Task results are in order
            tasks_output = result.tasks_output if hasattr(result, 'tasks_output') else []

            if len(tasks_output) >= 1 and tasks_output[0].pydantic:
                site_structure = tasks_output[0].pydantic
                logger.info(f"[OK] Site structure: {len(site_structure.sections)} sections, "
                           f"{site_structure.mvp_page_count} MVP pages")

            if len(tasks_output) >= 2 and tasks_output[1].pydantic:
                user_flows = tasks_output[1].pydantic
                logger.info(f"[OK] User flows: {len(user_flows.flows)} flows")

            return site_structure, user_flows

        except Exception as e:
            logger.error(f"[Stage 10.5] Technical Blueprint crew failed: {e}")
            return None, None

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get usage metrics from the last crew execution.

        Returns:
            CrewAI UsageMetrics object or None if no execution yet
        """
        if hasattr(self, '_last_crew') and self._last_crew:
            return self._last_crew.usage_metrics
        return None
