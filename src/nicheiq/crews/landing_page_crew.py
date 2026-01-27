"""
LandingPageCrew - Generates unique, fully-designed HTML landing pages.

8-Agent Pipeline:
0. Marketing Strategist -> Creates strategic landing page brief
1. Creative Director -> Creates autonomous visual strategy (archetype, intensity, hero layout)
2. Visual Designer -> Interprets creative direction into specific visual decisions
3. Brand Designer -> Executes creative direction into specific brand assets
4. Copywriter -> Writes conversion-optimized copy following strategy
5. HTML Developer -> Generates complete HTML implementing visual design
6. Animation Enhancer -> Adds premium motion design and micro-interactions
7. QA Reviewer -> Validates and fixes visual design issues

Each run produces a unique design tailored to the specific product.
The Creative Director ensures visual differentiation through niche-derived
archetypes, hero layouts, and layout rhythms - not category stereotypes.
The Visual Designer adds creative interpretation with card treatments,
visual surprises, and animation personality.
"""

import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..tools import CachedSerperDevTool
from ..utils.llm_service import build_llm, build_llm_kwargs
from ..models.landing_page import (
    AnimatedHTMLResult,
    BrandIdentity,
    CreativeDirection,
    HTMLPageResult,
    LandingPageCopy,
    LandingPageResult,
    LandingStrategy,
    QAReviewResult,
    VisualDesignSpec,
)
from ..models.research_state import FinalReport


@CrewBase
class LandingPageCrew:
    """
    Generates unique, fully-designed landing pages from research reports.

    8-Agent Pipeline:
    0. Marketing Strategist -> Creates strategic brief with persona, messaging, memorable element
    1. Creative Director -> Creates autonomous visual strategy (archetype, intensity, hero layout)
    2. Visual Designer -> Interprets creative direction into card treatments, visual surprises
    3. Brand Designer -> Executes creative direction into specific brand assets
    4. Copywriter -> Writes copy following strategic direction
    5. HTML Developer -> Generates complete HTML implementing visual design spec
    6. Animation Enhancer -> Adds premium motion design and micro-interactions
    7. QA Reviewer -> Validates and fixes visual design issues (layout, typography, responsive)

    Each run produces a unique design tailored to the specific product.
    The Creative Director ensures visual differentiation through niche-derived
    archetypes, hero layouts, and layout rhythms - not category stereotypes.
    The Visual Designer adds creative interpretation with specific visual decisions.
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
        Uses high reasoning_effort for creative differentiation (GPT-5.2).
        """
        return Agent(
            config=self.agents_config["marketing_strategist"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.landing_page_llm,
                reasoning_effort=settings.landing_page_creative_reasoning_effort,
            )),
            verbose=True,
        )

    @agent
    def creative_director(self) -> Agent:
        """
        Creative Director agent - makes autonomous visual strategy decisions.
        Uses high reasoning_effort for creative, unexpected combinations (GPT-5.2).
        Has access to web search for landing page inspiration.
        """
        return Agent(
            config=self.agents_config["creative_director"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.landing_page_llm,
                reasoning_effort=settings.landing_page_creative_reasoning_effort,
            )),
            tools=[CachedSerperDevTool()],  # Enable inspiration search
            verbose=True,
        )

    @agent
    def visual_designer(self) -> Agent:
        """
        Visual Designer agent - interprets creative direction into specific visual decisions.
        Makes creative choices about card treatments, memorable element visuals, and visual surprises.
        Uses high reasoning_effort for creative interpretation (GPT-5.2).
        """
        return Agent(
            config=self.agents_config["visual_designer"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.landing_page_llm,
                reasoning_effort=settings.landing_page_creative_reasoning_effort,
            )),
            verbose=True,
        )

    @agent
    def brand_designer(self) -> Agent:
        """
        Creates unique brand identity based on product category.
        Uses high reasoning_effort for unique color/typography choices (GPT-5.2).
        """
        return Agent(
            config=self.agents_config["brand_designer"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.landing_page_llm,
                reasoning_effort=settings.landing_page_creative_reasoning_effort,
            )),
            verbose=True,
        )

    @agent
    def landing_page_copywriter(self) -> Agent:
        """
        Writes conversion-optimized copy and decides which sections to include.
        Uses high reasoning_effort for creative but focused copy (GPT-5.2).
        """
        return Agent(
            config=self.agents_config["landing_page_copywriter"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.landing_page_llm,
                reasoning_effort=settings.landing_page_creative_reasoning_effort,
            )),
            verbose=True,
        )

    @agent
    def html_developer(self) -> Agent:
        """
        Generates complete HTML pages with Tailwind CSS.
        Uses execution LLM (gpt-5.1-codex-max) for reliable code generation.
        Uses max_output_tokens=30000 to prevent truncation of large HTML output.
        """
        return Agent(
            config=self.agents_config["html_developer"],
            llm=build_llm(
                model=settings.landing_page_execution_llm,
                reasoning_effort=settings.landing_page_execution_reasoning_effort,
                max_output_tokens=30000,  # Prevent truncation of large HTML output
            ),
            verbose=True,
        )

    @agent
    def animation_enhancer(self) -> Agent:
        """
        Enhances HTML with premium animations and micro-interactions.
        Uses execution LLM (gpt-5.1-codex-max) for reliable code generation.
        Uses max_output_tokens=30000 to prevent truncation of large HTML output.
        """
        return Agent(
            config=self.agents_config["animation_enhancer"],
            llm=build_llm(
                model=settings.landing_page_execution_llm,
                reasoning_effort=settings.landing_page_execution_reasoning_effort,
                max_output_tokens=30000,  # Prevent truncation of large HTML output
            ),
            verbose=True,
        )

    @agent
    def qa_reviewer(self) -> Agent:
        """
        QA Reviewer agent - validates and fixes visual design issues.
        Uses execution LLM with low reasoning effort for structured validation.
        Uses max_output_tokens=30000 to prevent truncation of fixed HTML output.
        """
        return Agent(
            config=self.agents_config["qa_reviewer"],
            llm=build_llm(
                model=settings.landing_page_execution_llm,
                reasoning_effort=settings.landing_page_validation_reasoning_effort,
                max_output_tokens=30000,  # Prevent truncation of fixed HTML output
            ),
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
    def create_creative_direction_task(self) -> Task:
        """Task 1: Create autonomous creative direction based on niche analysis."""
        return Task(
            config=self.tasks_config["create_creative_direction"],
            agent=self.creative_director(),
            context=[self.create_landing_strategy_task()],  # Uses strategy
            output_pydantic=CreativeDirection,
        )

    @task
    def create_visual_design_task(self) -> Task:
        """Task 2: Create visual design specifications (card treatments, visual surprises)."""
        return Task(
            config=self.tasks_config["create_visual_design"],
            agent=self.visual_designer(),
            context=[
                self.create_landing_strategy_task(),  # For memorable element
                self.create_creative_direction_task(),  # For archetype, intensity
            ],
            output_pydantic=VisualDesignSpec,
        )

    @task
    def design_brand_identity_task(self) -> Task:
        """Task 3: Execute creative direction into specific brand assets."""
        return Task(
            config=self.tasks_config["design_brand_identity"],
            agent=self.brand_designer(),
            context=[
                self.create_creative_direction_task(),
                self.create_visual_design_task(),  # For visual design context
            ],
            output_pydantic=BrandIdentity,
        )

    @task
    def generate_landing_copy_task(self) -> Task:
        """Task 4: Write landing page copy following section_density from creative direction."""
        return Task(
            config=self.tasks_config["generate_landing_copy"],
            agent=self.landing_page_copywriter(),
            context=[
                self.create_landing_strategy_task(),  # Include strategy
                self.create_creative_direction_task(),  # For section_density
                self.create_visual_design_task(),  # For content_redundancy_notes
                self.design_brand_identity_task(),
            ],
            output_pydantic=LandingPageCopy,
        )

    @task
    def generate_html_page_task(self) -> Task:
        """Task 5: Generate complete HTML implementing visual design spec."""
        return Task(
            config=self.tasks_config["generate_html_page"],
            agent=self.html_developer(),
            context=[
                self.create_landing_strategy_task(),  # For memorable element
                self.create_creative_direction_task(),  # For hero/layout/density
                self.create_visual_design_task(),  # For card treatments, visual surprises
                self.design_brand_identity_task(),
                self.generate_landing_copy_task(),
            ],
            output_pydantic=HTMLPageResult,
        )

    @task
    def enhance_animations_task(self) -> Task:
        """Task 6: Enhance HTML with premium animations and micro-interactions."""
        return Task(
            config=self.tasks_config["enhance_animations"],
            agent=self.animation_enhancer(),
            context=[
                self.create_landing_strategy_task(),  # For memorable element animation
                self.create_creative_direction_task(),  # For intensity-to-animation mapping
                self.create_visual_design_task(),  # For animation personality
                self.design_brand_identity_task(),  # For mood-to-animation mapping
                self.generate_html_page_task(),  # The HTML to enhance
            ],
            output_pydantic=AnimatedHTMLResult,
        )

    @task
    def qa_review_task(self) -> Task:
        """Task 7: QA review and fix visual design issues."""
        return Task(
            config=self.tasks_config["qa_review_html"],
            agent=self.qa_reviewer(),
            context=[
                self.create_landing_strategy_task(),  # For memorable element preservation
                self.create_creative_direction_task(),  # For creative direction context
                self.create_visual_design_task(),  # For visual design spec context
                self.design_brand_identity_task(),  # For design mood context
                self.enhance_animations_task(),  # The animated HTML to review
            ],
            output_pydantic=QAReviewResult,
        )

    # ========== CREW ==========

    @crew
    def crew(self) -> Crew:
        """Create the Landing Page Generator crew."""
        # Generate unique log file path for this run
        log_dir = Path(settings.output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"landing_crew_{timestamp}.json"

        logger.info(f"Crew prompts/responses will be logged to: {log_file}")

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
            output_log_file=str(log_file),  # Captures all prompts/responses
        )

    # ========== PUBLIC API ==========

    def generate(self, report: FinalReport, page_mode: str = "coming_soon") -> LandingPageResult:
        """
        Generate complete landing page from research report.

        Args:
            report: FinalReport from NicheIQ pipeline
            page_mode: "coming_soon" (waitlist) or "launched" (full product)

        Returns:
            LandingPageResult with brand, copy, and HTML
        """
        logger.info(f"Generating landing page for: {report.selected_solution_name} (mode: {page_mode})")

        # Extract inputs from report
        inputs = self._extract_inputs(report, page_mode)

        # Add variation context for creative diversity
        variation_context = self._generate_variation_context()
        inputs.update(variation_context)

        # Log input summary
        logger.info(f"Variation hint: {inputs['variation_hint']} (seed: {inputs['variation_seed']})")
        logger.info(f"Extracted inputs: product_name={inputs['product_name']}, "
                   f"solution_type={inputs['solution_type']}, "
                   f"features_count={len(inputs['features'].split(',')) if inputs['features'] else 0}")

        # Run the crew
        result = self.crew().kickoff(inputs=inputs)

        # Extract outputs from each task (8 tasks now)
        strategy = result.tasks_output[0].pydantic
        creative_direction = result.tasks_output[1].pydantic
        visual_design = result.tasks_output[2].pydantic
        brand_identity = result.tasks_output[3].pydantic
        copy = result.tasks_output[4].pydantic
        html_result = result.tasks_output[5].pydantic
        animated_result = result.tasks_output[6].pydantic
        qa_result = result.tasks_output[7].pydantic

        logger.info(f"Landing page generated with {len(html_result.sections_included)} sections")
        logger.info(f"Primary persona: {strategy.primary_persona}")
        logger.info(f"Memorable element: {strategy.memorable_element[:100]}...")
        logger.info(f"Creative direction: {creative_direction.design_archetype}, "
                   f"intensity: {creative_direction.visual_intensity}, "
                   f"hero: {creative_direction.hero_archetype}")
        logger.info(f"Visual design: {len(visual_design.card_treatments)} card treatments, "
                   f"{len(visual_design.visual_surprises)} visual surprises, "
                   f"animation: {visual_design.animation_personality}")
        logger.info(f"Design mood: {brand_identity.design_mood}")
        logger.info(f"Section selection reasoning: {copy.section_selection_reasoning[:100]}...")
        logger.info(f"Animations added: {', '.join(animated_result.animations_added)}")
        logger.info(f"QA Review: {qa_result.issues_fixed_count} issues fixed, score: {qa_result.quality_score}/100, passes: {qa_result.passes_qa}")

        # Combine creative direction, visual design, design notes, animation notes, and QA review notes
        combined_notes = (
            f"Creative Direction: {creative_direction.archetype_rationale}\n\n"
            f"Visual Design: {visual_design.visual_design_rationale}\n\n"
            f"Design: {html_result.design_notes}\n\n"
            f"Animation: {animated_result.animation_notes}\n\n"
            f"QA Review: {qa_result.review_notes}"
        )

        return LandingPageResult(
            landing_strategy=strategy,
            brand_identity=brand_identity,
            page_copy=copy,
            html_output=qa_result.html_content,  # Use QA-reviewed HTML
            sections_generated=html_result.sections_included,
            animations_added=animated_result.animations_added,
            generation_notes=combined_notes,
        )

    def _generate_variation_context(self) -> dict:
        """Generate variation hint including structural nudges.

        Provides subtle nudges to creative agents to explore different
        directions each run, including structural alternatives to the
        default split-showcase hero pattern.
        """
        seed = int(time.time()) % 100000
        rng = random.Random(seed)

        hints = [
            # STRUCTURAL nudges (open-ended)
            "Consider a centered, single-column hero instead of the typical two-column split",
            "What if the hero was full-viewport with dramatic visual impact?",
            "Try a vertical narrative flow where elements stack and reveal on scroll",
            "Experiment with asymmetry - angled sections or overlapping elements",
            "Could the hero work without a side artifact? Focus purely on the message",
            # VISUAL nudges (existing)
            "Consider an unexpected color temperature for this category",
            "Pick fonts that feel fresh, not the obvious choice",
            "Vary the visual intensity from what you'd normally expect",
            "Explore a design archetype that breaks category conventions",
            "Consider warm colors where cool is expected, or vice versa",
            # COLOR-SPECIFIC nudges (new)
            "Consider a light/bright color scheme for this product's energy",
            "Explore cool tones (blues, teals, greens) instead of warm amber",
            "A clean white background might serve this product better than dark",
            "Bold, saturated colors could make this product feel more distinctive",
        ]

        return {
            "variation_hint": rng.choice(hints),
            "variation_seed": seed,
        }

    def _extract_inputs(self, report: FinalReport, page_mode: str = "coming_soon") -> dict:
        """
        Extract crew inputs from FinalReport.

        Maps FinalReport fields to the placeholders in task YAML.
        Includes 10 new uniqueness-driving fields for differentiated landing pages.

        Args:
            report: FinalReport from NicheIQ pipeline
            page_mode: "coming_soon" (waitlist) or "launched" (full product)
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

        # Extract quotes for social proof (from detailed_pain_points)
        quotes = "Not available"
        if report.detailed_pain_points:
            # Use pain point titles as social proof quotes
            quotes = "\n".join(f'"{pp.title}"' for pp in report.detailed_pain_points[:3])

        # Extract solution type
        solution_type = "saas"
        if solution_details and solution_details.project_type:
            solution_type = solution_details.project_type

        # Extract project type for brand design
        project_type = solution_type

        # ========== NEW: Uniqueness-driving fields (V3) ==========

        # Niche category context
        niche = report.niche or ""

        # Pre-computed tagline from executive dashboard
        core_tagline = ""
        if report.executive_dashboard and report.executive_dashboard.recommended_solution_snapshot:
            core_tagline = report.executive_dashboard.recommended_solution_snapshot.tagline or ""

        # GTM Blueprint fields
        core_marketing_message = ""
        message_framework = ""
        content_angles = ""
        if report.go_to_market_blueprint:
            gtm = report.go_to_market_blueprint
            core_marketing_message = gtm.core_marketing_message or ""
            message_framework = gtm.message_framework or ""
            if gtm.example_content_angles:
                # Extract title + hook from each angle
                content_angles = "\n".join(
                    f"- {a.title}: {a.hook}"
                    for a in gtm.example_content_angles[:3]
                )

        # Differentiation factors from solution details
        differentiation_factors = ""
        if solution_details and solution_details.differentiation_factors:
            differentiation_factors = "\n".join(
                f"- {f}" for f in solution_details.differentiation_factors[:4]
            )

        # Runner-up solutions for comparison positioning (from alternative_solutions)
        runner_ups = ""
        if report.alternative_solutions:
            runner_ups = ", ".join(alt.solution_name for alt in report.alternative_solutions[:2])

        # MVP features for roadmap section
        mvp_features = ""
        if report.mvp_scope_definition:
            mvp_features = report.mvp_scope_definition[:300]

        # ========== NEW: Audience Intelligence Fields (Part C) ==========

        # Niche vocabulary for authentic copy
        niche_vocabulary = ""
        primary_segment = ""
        messaging_frameworks = ""
        if report.audience_mapping:
            am = report.audience_mapping
            # Common vocabulary: 10-15 niche-specific terms
            if am.common_vocabulary:
                niche_vocabulary = ", ".join(am.common_vocabulary[:10])
            # Primary target segment
            primary_segment = am.primary_target_segment or ""
            # Messaging frameworks
            if am.messaging_frameworks:
                messaging_frameworks = "\n".join(f"- {mf}" for mf in am.messaging_frameworks[:5])

        # ========== NEW: Market Credibility Fields ==========

        # Trend direction and market momentum
        trend_signal = ""
        market_verdict = ""
        if report.trend_longevity:
            tl = report.trend_longevity
            trend_signal = f"{tl.trend_direction} market (confidence: {tl.trend_confidence})"
            if tl.momentum_score >= 0.7:
                trend_signal += " - Strong momentum"

        if report.market_sizing:
            ms = report.market_sizing
            market_verdict = ms.market_viability_verdict or ""  # "Strong", "Moderate", "Weak"
            if ms.total_addressable_market:
                market_verdict += f" | TAM: {ms.total_addressable_market}"

        return {
            # Page mode context
            "page_mode": page_mode,

            # Original 12 fields
            "product_name": report.selected_solution_name,
            "solution_type": solution_type,
            "project_type": project_type,
            "target_personas": target_personas or "SaaS users looking for this solution",
            "value_proposition": value_proposition or report.executive_summary[:200],
            "pain_points": "\n".join(f"- {pp.title}" for pp in report.detailed_pain_points[:5]) if report.detailed_pain_points else "",
            "pain_points_summary": report.pain_points_summary[:500] if report.pain_points_summary else "",
            "features": features or "Core product features",
            "user_journey": user_journey,
            "pricing_summary": pricing_summary,
            "competitive_summary": report.competitive_summary[:500] if report.competitive_summary else "",
            "quotes": quotes,
            # NEW: 10 uniqueness-driving fields (V3)
            "niche": niche,
            "core_tagline": core_tagline,
            "core_marketing_message": core_marketing_message,
            "message_framework": message_framework,
            "selection_rationale": report.selection_rationale or "",
            "recommended_focus": report.recommended_focus or "",
            "content_angles": content_angles,
            "differentiation_factors": differentiation_factors,
            "runner_ups": runner_ups,
            "mvp_features": mvp_features,
            # NEW: Audience Intelligence (Part C)
            "niche_vocabulary": niche_vocabulary,
            "primary_segment": primary_segment,
            "messaging_frameworks": messaging_frameworks,
            # NEW: Market Credibility (Part C)
            "trend_signal": trend_signal,
            "market_verdict": market_verdict,
            # Competitor links for creative inspiration
            "competitor_links": self._extract_competitor_links(report),
        }

    def _extract_competitor_links(self, report: FinalReport) -> str:
        """Extract competitor URLs from report for creative inspiration.

        Provides the Creative Director with real competitor landing pages
        to analyze and differentiate from.

        Args:
            report: FinalReport from NicheIQ pipeline

        Returns:
            Formatted string of competitor links or "No competitor URLs available"
        """
        if not report.competitor_profiles:
            return "No competitor URLs available"

        links = [
            f"- {cp.name}: {cp.url}"
            for cp in report.competitor_profiles[:5]
            if cp.url
        ]

        return "\n".join(links) if links else "No competitor URLs available"
