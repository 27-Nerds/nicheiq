"""
Traffic Monetization Crew (Stage 8).

For directories, aggregators, and comparison tools that monetize via
traffic (ads, affiliates) rather than subscriptions.

Routes from research_flow.py when:
    project_type in ['directory', 'aggregator', 'comparison-tool']
"""

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger
import re

from ..config.settings import settings
from ..utils.content_security import prompt_field
from ..utils.llm_service import build_crew_llm
from ..models.research_state import TrafficMonetizationResult, TrafficUnitValueEvidence
from ..models.competitor import VerifiedPricingProvenance
from ..utils.commercial_route import (
    CommercialLane,
    assess_commercial_lane,
)
from ..utils.validation.crew_guardrails import validate_traffic_monetization
from ..utils.crew_helpers import (
    compute_ad_revenue_estimate,
    compute_traffic_projection,
    match_niche_to_cpm,
)


@CrewBase
class TrafficMonetizationCrew:
    """
    Crew for analyzing traffic-based monetization strategies.

    Used for project types: directory, aggregator, comparison-tool

    Analyzes:
    - Traffic potential from keyword search volumes
    - Display ad revenue (CPM/RPM by niche)
    - Affiliate program opportunities
    - Sponsored listing/lead gen potential (B2B)

    Outputs:
    - Traffic projections (monthly pageviews)
    - Ad revenue estimates (CPM, networks)
    - Affiliate revenue estimates (programs, commissions)
    - B2B monetization options (sponsored, lead gen)
    - Total revenue projection with scaling strategy
    """

    agents_config = "config/traffic_monetization_agents.yaml"
    tasks_config = "config/traffic_monetization_tasks.yaml"

    def __init__(self):
        """Initialize TrafficMonetizationCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def traffic_monetization_analyst(self) -> Agent:
        """
        Traffic Monetization Analyst agent.

        Specializes in publisher revenue, display ads, affiliate marketing,
        and traffic-based monetization strategies.
        """
        return Agent(
            config=self.agents_config["traffic_monetization_analyst"],
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.4,  # Balanced for creative revenue suggestions (ignored for reasoning models)
            ),
            verbose=True,
        )

    @task
    def traffic_monetization_analysis_task(self) -> Task:
        """
        Main traffic monetization analysis task.

        Analyzes keyword volumes, niche CPM rates, and affiliate opportunities
        to recommend optimal traffic monetization strategy.
        """
        return SafeTask(
            config=self.tasks_config["traffic_monetization_analysis"],
            agent=self.traffic_monetization_analyst(),
            output_pydantic=TrafficMonetizationResult,
            guardrail=self._traffic_guardrail,
            guardrail_max_retries=2,
        )

    def _traffic_guardrail(self, task_output):
        """Bound guardrail wrapper: passes the evidence-based traffic ceiling
        (set in analyze() when SEO data exists) so pageview claims are clamped."""
        checked = validate_traffic_monetization(
            task_output,
            traffic_ceiling_y1_high=getattr(self, '_seo_traffic_ceiling_y1_high', None),
        )
        # The shared legacy guard still requires an ad network. Lead/funnel routes are allowed
        # to reject ads honestly; preserve every other validation and only relax that one rule.
        if checked[0] or "recommended_ad_networks" not in str(checked[1]):
            return checked
        try:
            raw = getattr(task_output, "raw", "")
            result = TrafficMonetizationResult.model_validate_json(raw)
            if result.monetization_model in {"Lead-Gen", "Free-Tool-Funnel"}:
                return True, raw
        except Exception:
            pass
        return checked

    @crew
    def crew(self) -> Crew:
        """
        Assemble the traffic monetization crew.

        Single-agent, single-task crew optimized for traffic monetization analysis.
        """
        return Crew(
            agents=[self.traffic_monetization_analyst()],
            tasks=[self.traffic_monetization_analysis_task()],
            verbose=True,
        )

    def _format_keyword_data(self, keyword_validation_results, solution_name: str, seo_strategy_report=None) -> str:
        """
        Format keyword data for traffic estimation.

        Prefers SEO strategy report data when available (comprehensive).
        Falls back to keyword_validation_results for backward compatibility.

        Args:
            keyword_validation_results: List of CrewKeywordValidationResult (may be None)
            solution_name: Name of solution to find keyword data for
            seo_strategy_report: Optional SEOStrategyReport with comprehensive keyword data

        Returns:
            Formatted string with keyword volumes and metrics
        """
        # The SEO report's raw tiers can still contain category/head terms. Only its
        # code-computed idea-intent aggregate is safe for candidate economics.
        if seo_strategy_report:
            relevant_volume = getattr(seo_strategy_report, "idea_intent_monthly_volume", None)
            if isinstance(relevant_volume, int):
                demand_signal = (
                    "strong" if relevant_volume >= 5000
                    else "moderate" if relevant_volume >= 2000 else "weak"
                )
                return "\n".join([
                    f"**Candidate-Relevant Search Volume:** {relevant_volume:,} searches/month "
                    "(code-graded SEO data)",
                    f"**Demand Signal:** {demand_signal}",
                    "**Constraint:** Ungraded category/head-term volume is excluded.",
                ])

        # Fallback: use keyword validation results
        if not keyword_validation_results:
            return "No keyword data available."

        for validation in keyword_validation_results:
            if validation.solution_name == solution_name:
                qualified_volume = TrafficMonetizationCrew._qualified_keyword_volume(
                    keyword_validation_results, solution_name)
                if qualified_volume is None:
                    legacy_count = len(getattr(validation, "validated_keywords", None) or [])
                    return "\n".join([
                        "**Candidate-Relevant Search Volume:** unknown (relevance unmeasured)",
                        f"**Validated Keywords:** {legacy_count}",
                        "**Demand Signal:** unknown; do not infer demand from raw total volume.",
                    ])
                rows = list(getattr(validation, "validated_keywords", None) or [])
                has_grades = any(
                    isinstance(row, dict) and row.get("idea_intent_grade") is not None
                    for row in rows
                )
                qualified_rows = [
                    row for row in rows
                    if isinstance(row, dict) and (
                        not has_grades or (
                            isinstance(row.get("idea_intent_grade"), (int, float))
                            and row["idea_intent_grade"] >= 2
                        )
                    )
                ]
                demand_signal = (
                    "strong" if qualified_volume >= 5000
                    else "moderate" if qualified_volume >= 2000 else "weak"
                )
                lines = [
                    f"**Candidate-Relevant Search Volume:** {qualified_volume:,} searches/month",
                    f"**Validated Keywords:** {len(qualified_rows)} (candidate-relevant)",
                    f"**Demand Signal:** {demand_signal}",
                    "",
                    "**Top Relevant Keywords by Volume:**"
                ]

                top_keywords = sorted(
                    qualified_rows,
                    key=lambda x: x.get('search_volume', x.get('volume', 0)),
                    reverse=True
                )[:15]

                for kw in top_keywords:
                    keyword = kw.get('keyword', 'N/A')
                    volume = kw.get('search_volume', kw.get('volume', 0))
                    lines.append(f"  - {keyword}: {volume:,}/month")

                return "\n".join(lines)

        return f"No keyword data found for solution: {solution_name}"

    @staticmethod
    def _qualified_keyword_volume(keyword_validation_results, solution_name: str) -> int | None:
        """Candidate-owned, relevance-qualified demand only; never raw head-term volume."""
        validation = next(
            (row for row in (keyword_validation_results or [])
             if getattr(row, "solution_name", None) == solution_name),
            None,
        )
        if validation is None:
            return None
        rows = list(getattr(validation, "validated_keywords", None) or [])
        grades = [
            row.get("idea_intent_grade") for row in rows
            if isinstance(row, dict) and row.get("idea_intent_grade") is not None
        ]
        if grades:
            # Grade 0/1 is off-topic/category reach, not evidence for this product's demand.
            return sum(
                int(row.get("search_volume", row.get("volume", 0)) or 0)
                for row in rows
                if isinstance(row, dict)
                and isinstance(row.get("idea_intent_grade"), (int, float))
                and row["idea_intent_grade"] >= 2
            )
        relevant = getattr(validation, "niche_relevant_volume", None)
        if isinstance(relevant, (int, float)) and not isinstance(relevant, bool):
            return max(0, int(relevant))
        # Legacy total_volume is deliberately not a fallback: it includes unqualified head terms.
        return None

    @staticmethod
    def _money_range(value: str | None) -> tuple[int, int] | None:
        match = re.search(
            r"\$\s*([0-9][0-9,]*)(?:\s*[-–—]\s*\$?\s*([0-9][0-9,]*))?",
            value or "",
        )
        if not match:
            return None
        low = int(match.group(1).replace(",", ""))
        high = int((match.group(2) or match.group(1)).replace(",", ""))
        return min(low, high), max(low, high)

    @staticmethod
    def _attributed_unit_value_evidence(
        competitive_analysis,
        solution_name: str,
        value_capture_mode: str | None,
        solution_description: str | None = None,
        *,
        candidate_idea_id: str | None = None,
        candidate_idea_revision: int | None = None,
        niche_description: str | None = None,
        verified_pricing_evidence: list[VerifiedPricingProvenance] | None = None,
    ) -> TrafficUnitValueEvidence | None:
        """Bind deterministic verifier output to this candidate's exact landscape.

        Competitor URL/pricing fields are LLM-authored discovery hints, never verification.
        With no bounded safe-fetch verifier output, this method deliberately returns None.
        """
        capture = (value_capture_mode or "").strip().lower()
        landscapes = list(
            getattr(competitive_analysis, "solution_landscapes", None) or []
        )
        needle = " ".join(solution_name.lower().split())
        named_landscapes = [
            row for row in landscapes
            if " ".join((getattr(row, "solution_name", "") or "").lower().split())
            == needle
        ]
        if (
            len(named_landscapes) != 1
            or not candidate_idea_id
            or not isinstance(candidate_idea_revision, int)
            or isinstance(candidate_idea_revision, bool)
        ):
            return None
        landscape = named_landscapes[0]
        if (
            getattr(landscape, "candidate_idea_id", None) != candidate_idea_id
            or getattr(landscape, "candidate_idea_revision", None)
            != candidate_idea_revision
            or getattr(landscape, "off_niche_caveat", None)
        ):
            return None

        route_text = re.sub(r"([a-z])([A-Z])", r"\1 \2", solution_name)
        route_text = (
            f"{route_text} {solution_description or ''} {niche_description or ''}"
        ).lower()
        generic_tokens = {
            "app", "calculator", "compare", "comparison", "directory", "finder",
            "business", "customer", "data", "free", "guide", "hub", "lead", "paid",
            "platform", "route", "service", "software", "solution", "tool", "user",
            "using", "with",
        }
        niche_tokens = {
            token for token in re.findall(r"[a-z0-9]+", route_text)
            if len(token) >= 4 and token not in generic_tokens
        }

        competitors = list(getattr(landscape, "competitors", None) or [])
        verified = [
            row for row in (verified_pricing_evidence or [])
            if row.candidate_idea_id == candidate_idea_id
            and row.candidate_idea_revision == candidate_idea_revision
            and row.route == capture
        ]
        if len(verified) != 1:
            return None
        provenance = verified[0]
        exact_sources = [
            competitor for competitor in competitors
            if (getattr(competitor, "name", None) or "").strip() == provenance.source_name
            and (getattr(competitor, "url", None) or "").strip() == provenance.source_url
        ]
        if len(exact_sources) != 1:
            return None

        source_name = provenance.source_name.strip()
        evidence_text = provenance.retrieved_quote.strip()
        source_tokens = set(re.findall(
            r"[a-z0-9]+", f"{source_name} {evidence_text}".lower()
        ))
        if len(niche_tokens & source_tokens) < 2:
            return None

        expected_basis = {
            "lead_generation": "per_lead",
            "sponsorship": "per_sponsored_listing_month",
            "paid_upgrade_funnel": "per_paid_upgrade_month",
            "affiliate": "affiliate_program",
        }.get(capture)
        if expected_basis is None or provenance.billing_basis != expected_basis:
            return None
        return TrafficUnitValueEvidence(
            route=provenance.route,
            source_name=source_name,
            source_url=provenance.source_url,
            evidence_text=evidence_text,
            candidate_idea_id=provenance.candidate_idea_id,
            candidate_idea_revision=provenance.candidate_idea_revision,
            retrieved_quote=evidence_text,
            retrieved_at=provenance.retrieved_at,
            verification_marker=provenance.verification_marker,
            value_low=provenance.value_low,
            value_high=provenance.value_high,
            billing_basis=provenance.billing_basis,
            commission_pct_low=provenance.commission_pct_low,
            commission_pct_high=provenance.commission_pct_high,
        )

    @staticmethod
    def _commercial_route_value(solution, field: str) -> str | None:
        """Nested contract is authoritative; flat fields support legacy records only."""
        route = getattr(solution, "commercial_route", None)
        if route is not None:
            value = route.get(field) if isinstance(route, dict) else getattr(route, field, None)
        else:
            value = getattr(solution, field, None)
        normalized = (value or "").strip().lower()
        return normalized or None

    @staticmethod
    def _apply_deterministic_viability(
        result: TrafficMonetizationResult,
        *,
        value_capture_mode: str | None,
        payer: str | None,
        projected_pageviews: tuple[int, int],
        deterministic_ad_revenue: tuple[int, int],
        deterministic_cpm_rate: str | None = None,
        unit_value_evidence: TrafficUnitValueEvidence | dict | None = None,
        solution=None,
        commercial_lane: CommercialLane | None = None,
    ) -> None:
        """Replace LLM economics with one canonical, code-owned route record."""
        if solution is not None:
            capture = TrafficMonetizationCrew._commercial_route_value(
                solution, "value_capture_mode"
            ) or ""
            payer_value = TrafficMonetizationCrew._commercial_route_value(
                solution, "payer"
            ) or ""
        else:
            capture = (value_capture_mode or "").strip().lower()
            payer_value = (payer or "").strip().lower()
        lane = commercial_lane or (
            assess_commercial_lane(solution) if solution is not None else CommercialLane.UNKNOWN
        )
        page_low, page_high = projected_pageviews
        ad_low, ad_high = deterministic_ad_revenue

        if isinstance(unit_value_evidence, dict):
            unit_value_evidence = TrafficUnitValueEvidence.model_validate(unit_value_evidence)

        def clear_economics() -> None:
            for field in (
                "estimated_cpm_rate", "estimated_monthly_ad_revenue",
                "affiliate_commission_rate", "estimated_affiliate_ctr",
                "estimated_monthly_affiliate_revenue", "sponsored_listing_price",
                "premium_placement_price", "lead_gen_price_per_lead",
                "estimated_monthly_revenue_range", "estimated_annual_revenue_range",
                "break_even_traffic_threshold", "funnel_target", "qualified_actions",
                "conversion_assumptions", "estimated_funnel_value", "unit_value_evidence",
                "traffic_methodology", "traffic_data_sources", "year3_monthly_pageviews",
                "year3_monthly_revenue", "full_potential_monthly_pageviews",
                "full_potential_monthly_revenue", "revenue_growth_note", "revenue_milestones",
                "scaling_strategy",
            ):
                setattr(result, field, None)
            result.recommended_ad_networks = []
            result.recommended_affiliate_programs = []

        def money(low: int, high: int, period: str) -> str:
            return f"${low:,} - ${high:,}/{period}"

        clear_economics()
        result.economics_evaluated = True
        result.estimated_monthly_pageviews = f"{page_low:,} - {page_high:,}"

        # No typed commercial route means the economics were not measured. Preserve
        # that third state instead of inferring a route from LLM prose, a model label,
        # or a plausible-looking affiliate-program list.
        if not capture:
            result.viability_verdict = None
            result.monetization_confidence = "Low"
            result.monetization_rationale = (
                "Route economics are unknown because no typed value-capture route was measured."
            )
            return

        def reject_route(reason: str) -> None:
            clear_economics()
            result.viability_verdict = "nonviable"
            result.monetization_confidence = "Low"
            # The deterministic ad estimate is retained only as rejection evidence,
            # never copied into the total revenue fields.
            result.estimated_monthly_ad_revenue = money(ad_low, ad_high, "month")
            result.monetization_rationale = (
                f"Deterministic route economics: nonviable — {reason}."
            )
            result.saas_vs_traffic_recommendation = (
                "Do not treat traffic monetization as validated; test a different payer or "
                "commercial route before investing in acquisition."
            )

        if lane is not CommercialLane.NON_DIRECT:
            reject_route("the typed commercial route is incomplete or not non-direct")
            return

        def verified_for_candidate(evidence: TrafficUnitValueEvidence | None) -> bool:
            if evidence is None or solution is None:
                return False
            return (
                evidence.verification_marker == "exact_quote_in_fetched_public_content"
                and bool(evidence.retrieved_quote and evidence.retrieved_quote.strip())
                and evidence.retrieved_at is not None
                and evidence.candidate_idea_id == getattr(solution, "idea_id", None)
                and evidence.candidate_idea_revision == getattr(solution, "idea_revision", None)
            )

        if capture in {"lead_generation", "sponsorship", "paid_upgrade_funnel"}:
            allowed_payers = {
                "lead_generation": {"downstream_customer", "vendor", "lead_buyer", "listed_business"},
                "sponsorship": {"advertiser", "sponsor", "vendor", "listed_business"},
                "paid_upgrade_funnel": {"end_user", "team_or_employer", "listed_business", "vendor"},
            }[capture]
            if payer_value not in allowed_payers:
                reject_route("no compatible explicit payer supports the qualified action")
                return
            expected_basis = {
                "lead_generation": "per_lead",
                "sponsorship": "per_sponsored_listing_month",
                "paid_upgrade_funnel": "per_paid_upgrade_month",
            }[capture]
            if (
                not verified_for_candidate(unit_value_evidence)
                or unit_value_evidence.route != capture
                or unit_value_evidence.billing_basis != expected_basis
                or not unit_value_evidence.source_name.strip()
                or not unit_value_evidence.source_url.startswith(("https://", "http://"))
                or not unit_value_evidence.value_low
                or not unit_value_evidence.value_high
            ):
                reject_route("no attributed competitor unit-value evidence supports this route")
                return
            rate_low, rate_high = (0.005, 0.01) if capture != "paid_upgrade_funnel" else (0.005, 0.02)
            action_low = int(page_low * rate_low)
            action_high = int(page_high * rate_high)
            result.unit_value_evidence = unit_value_evidence
            if capture == "lead_generation":
                result.monetization_model = "Lead-Gen"
                result.funnel_target = "qualified downstream lead"
                result.qualified_actions = f"{action_low:,} - {action_high:,} qualified actions/month"
                result.conversion_assumptions = [
                    f"{rate_low:.1%}-{rate_high:.1%} of candidate-relevant visits complete a qualified action"
                ]
                result.lead_gen_price_per_lead = money(
                    unit_value_evidence.value_low or 0,
                    unit_value_evidence.value_high or 0,
                    "lead",
                )
                value_low = action_low * (unit_value_evidence.value_low or 0)
                value_high = action_high * (unit_value_evidence.value_high or 0)
            elif capture == "sponsorship":
                result.monetization_model = "Free-Tool-Funnel"
                result.funnel_target = "sponsored listing"
                # This is a fixed monthly listing price. It is deliberately not
                # multiplied by traffic-derived actions.
                value_low = unit_value_evidence.value_low or 0
                value_high = unit_value_evidence.value_high or 0
                result.sponsored_listing_price = money(value_low, value_high, "month")
                result.conversion_assumptions = [
                    "One attributed sponsored-listing price is treated as fixed monthly value; it is not multiplied by traffic actions"
                ]
                result.viability_verdict = "conditional"
            else:
                result.monetization_model = "Free-Tool-Funnel"
                result.funnel_target = "paid upgrade"
                result.qualified_actions = f"{action_low:,} - {action_high:,} paid upgrades/month"
                result.conversion_assumptions = [
                    f"{rate_low:.1%}-{rate_high:.1%} of candidate-relevant visits convert to a paid upgrade"
                ]
                value_low = action_low * (unit_value_evidence.value_low or 0)
                value_high = action_high * (unit_value_evidence.value_high or 0)
            result.estimated_funnel_value = money(value_low, value_high, "month")
            result.estimated_monthly_revenue_range = result.estimated_funnel_value
            result.estimated_annual_revenue_range = money(value_low * 12, value_high * 12, "year")
            # Unit price is attributed, but the qualified-action rate is still an
            # explicit assumption. Keep every funnel route conditional until measured
            # conversion data replaces that assumption.
            result.viability_verdict = "conditional"
            result.monetization_confidence = "Medium"
            result.monetization_rationale = (
                f"Deterministic {capture} economics use {unit_value_evidence.source_name}'s "
                f"attributed price ({unit_value_evidence.source_url})."
            )
            result.scaling_strategy = "Validate the qualified-action rate before increasing acquisition spend."
            return

        if capture == "affiliate":
            affiliate_payers = {"merchant", "vendor", "platform", "listed_business", "downstream_customer"}
            if payer_value not in affiliate_payers:
                reject_route("no merchant, vendor, or platform-compatible affiliate payer was established")
                return
            if (
                not verified_for_candidate(unit_value_evidence)
                or unit_value_evidence.route != "affiliate"
                or unit_value_evidence.billing_basis != "affiliate_program"
                or not unit_value_evidence.source_name.strip()
                or not unit_value_evidence.source_url.startswith(("https://", "http://"))
            ):
                reject_route("no real candidate-specific affiliate program was established")
                return
            result.monetization_model = "Affiliate"
            result.viability_verdict = "conditional"
            result.monetization_confidence = "Low"
            result.unit_value_evidence = unit_value_evidence
            result.recommended_affiliate_programs = [unit_value_evidence.source_name]
            if unit_value_evidence.commission_pct_low is not None:
                low = unit_value_evidence.commission_pct_low
                high = unit_value_evidence.commission_pct_high or low
                result.affiliate_commission_rate = f"{low:g}-{high:g}%"
            result.monetization_rationale = (
                f"An exact-candidate affiliate program is attributed to "
                f"{unit_value_evidence.source_name} ({unit_value_evidence.source_url}), but "
                "traffic-to-purchase economics remain unmeasured."
            )
            result.scaling_strategy = "Measure outbound clicks and attributed purchases before projecting revenue."
            return

        # Ads need meaningful projected dollars, not merely a positive CPM calculation.
        if capture == "advertising":
            if payer_value != "advertiser":
                reject_route("no advertiser-compatible payer was established")
                return
            result.viability_verdict = (
                "viable" if ad_low >= 500 else "conditional" if ad_high >= 100 else "nonviable"
            )
            if result.viability_verdict == "nonviable":
                reject_route(
                    f"projected display-ad revenue is only ${ad_low:,}-${ad_high:,}/month"
                )
                return
            result.monetization_model = "Ad-Supported"
            result.estimated_cpm_rate = deterministic_cpm_rate
            result.estimated_monthly_ad_revenue = money(ad_low, ad_high, "month")
            result.estimated_monthly_revenue_range = result.estimated_monthly_ad_revenue
            result.estimated_annual_revenue_range = money(ad_low * 12, ad_high * 12, "year")
            result.monetization_confidence = (
                "High" if result.viability_verdict == "viable" else "Medium"
            )
            result.monetization_rationale = (
                "Display-ad viability is computed only from candidate-relevant projected "
                "pageviews and the deterministic niche CPM band."
            )
            result.scaling_strategy = "Recompute ad economics after measured traffic replaces the projection."
            return

        reject_route("no evidenced non-direct revenue route clears the minimum economics")

    def _format_competitor_analysis(self, competitive_analysis, solution_name: str) -> str:
        """
        Extract competitor monetization strategies.

        Args:
            competitive_analysis: CompetitiveAnalysisResult from Stage 7.2
            solution_name: Name of solution to find competitors for

        Returns:
            Formatted string with competitor monetization data
        """
        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            return "No competitor data available."

        # Find landscape for this solution
        for landscape in competitive_analysis.solution_landscapes:
            if landscape.solution_name == solution_name:
                lines = ["**Competitor Monetization Strategies:**"]

                for comp in (landscape.competitors or [])[:8]:
                    comp_name = comp.name
                    pricing_model = comp.pricing_model or "Unknown"
                    comp_type = getattr(comp, 'competitor_type', 'N/A')

                    lines.append(f"  - {comp_name} ({comp_type}): {pricing_model}")

                    # Add description if available
                    if comp.description:
                        # Prompt input: at 100 chars the competitor's actual monetization shape
                        # was gone before the model that must differentiate from it ever saw it.
                        desc = prompt_field(comp.description)
                        lines.append(f"    Description: {desc}")

                # Add pricing insights from landscape
                if hasattr(landscape, 'pricing_insights') and landscape.pricing_insights:
                    lines.append("")
                    lines.append(f"**Pricing Insights:** {landscape.pricing_insights}")

                # Add market gaps
                if hasattr(landscape, 'market_gaps') and landscape.market_gaps:
                    lines.append("")
                    lines.append("**Market Gaps:**")
                    for gap in landscape.market_gaps[:3]:
                        lines.append(f"  - {gap}")

                return "\n".join(lines)

        return f"No competitor landscape found for solution: {solution_name}"

    def analyze(
        self,
        selected_solution,
        keyword_validation_results,
        competitive_analysis,
        niche_description: str,
        seo_strategy_report=None,
        verified_pricing_evidence: list[VerifiedPricingProvenance] | None = None,
    ) -> TrafficMonetizationResult | None:
        """
        Execute traffic monetization analysis.

        Args:
            selected_solution: SolutionIdea with project_type in [directory, aggregator, comparison-tool]
            keyword_validation_results: List of CrewKeywordValidationResult from keyword validation
            competitive_analysis: CompetitiveAnalysisResult from Stage 7.2
            niche_description: Niche description for context
            seo_strategy_report: Optional SEOStrategyReport for enriched traffic data

        Returns:
            TrafficMonetizationResult with traffic-based monetization strategy, or None if analysis fails
        """
        logger.info("[Stage 8] Starting Traffic Monetization Analysis...")
        logger.info(f"  Solution: {selected_solution.solution_name}")
        logger.info(f"  Project Type: {selected_solution.project_type}")
        logger.info(f"  Analyzing traffic potential and monetization channels...")

        qualified_keyword_volume = self._qualified_keyword_volume(
            keyword_validation_results, selected_solution.solution_name)
        seo_intent_volume = (
            getattr(seo_strategy_report, "idea_intent_monthly_volume", None)
            if seo_strategy_report is not None else None
        )
        if isinstance(seo_intent_volume, int):
            qualified_keyword_volume = seo_intent_volume
        if qualified_keyword_volume is None or qualified_keyword_volume <= 0:
            logger.warning(
                f"[Stage 8] {selected_solution.solution_name}: no candidate-owned, "
                "idea-relevant keyword demand; traffic economics remain unknown"
            )
            return None

        # Format keyword data for traffic estimation
        keyword_data = self._format_keyword_data(
            keyword_validation_results,
            selected_solution.solution_name,
            seo_strategy_report=seo_strategy_report
        )
        logger.debug(f"  Keyword data formatted: {len(keyword_data)} chars")

        # Format competitor analysis
        competitor_info = self._format_competitor_analysis(
            competitive_analysis,
            selected_solution.solution_name
        )
        logger.debug(f"  Competitor info formatted: {len(competitor_info)} chars")

        # Pre-compute deterministic traffic and monetization values
        # Prefer SEO strategy report volume (comprehensive) over keyword validation
        total_volume = qualified_keyword_volume

        # SEO tiers are intentionally not passed here: tier models discard the relevance
        # grade, so their difficulty-weighted sum can re-introduce contaminated head terms.
        traffic_projection, total_low, total_high = compute_traffic_projection(total_volume)
        self._seo_traffic_ceiling_y1_high = total_high
        cpm_low, cpm_high, cpm_vertical = match_niche_to_cpm(niche_description)
        suggested_cpm = f"${cpm_low}-${cpm_high} CPM ({cpm_vertical} vertical)"
        ad_revenue_estimate = compute_ad_revenue_estimate(total_low, total_high, cpm_low, cpm_high)

        # Set unconditional defaults for all template variables FIRST
        seo_enrichment = ""
        seo_traffic_ceiling_y1 = "N/A (no SEO data)"
        seo_commercial_intent_pct = "N/A (no SEO data)"
        affiliate_revenue_estimate = ""
        total_revenue_estimate = ""

        if seo_strategy_report:
            seo_enrichment = (
                "SEO report supplied for this candidate. Economics use only its code-graded "
                "idea-intent volume; raw tier totals are excluded."
            )
            seo_traffic_ceiling_y1 = f"{total_low:,}-{total_high:,} visits/mo"

        # Prepare inputs for the task
        inputs = {
            "solution_name": selected_solution.solution_name,
            "project_type": selected_solution.project_type or "directory",
            "solution_description": selected_solution.description or "No description provided",
            "niche_description": niche_description,
            "keyword_data": keyword_data,
            "competitor_analysis": competitor_info,
            "traffic_projection": traffic_projection,
            "suggested_cpm": suggested_cpm,
            "ad_revenue_estimate": ad_revenue_estimate,
            "seo_enrichment": seo_enrichment,
            "seo_traffic_ceiling_y1": seo_traffic_ceiling_y1,
            "seo_commercial_intent_pct": seo_commercial_intent_pct,
            "affiliate_revenue_estimate": affiliate_revenue_estimate,
            "total_revenue_estimate": total_revenue_estimate,
            "access_model": self._commercial_route_value(selected_solution, "access_model") or "unknown",
            "value_capture_mode": self._commercial_route_value(selected_solution, "value_capture_mode") or "unknown",
            "payer": self._commercial_route_value(selected_solution, "payer") or "unknown",
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                traffic_result = result.pydantic
                ad_low = int(total_low * cpm_low / 1000) if total_low > 0 else 0
                ad_high = int(total_high * cpm_high / 1000) if total_high > 0 else 0
                capture = self._commercial_route_value(
                    selected_solution, "value_capture_mode"
                )
                self._apply_deterministic_viability(
                    traffic_result,
                    value_capture_mode=capture,
                    payer=self._commercial_route_value(selected_solution, "payer"),
                    projected_pageviews=(total_low, total_high),
                    deterministic_ad_revenue=(ad_low, ad_high),
                    deterministic_cpm_rate=suggested_cpm,
                    unit_value_evidence=self._attributed_unit_value_evidence(
                        competitive_analysis,
                        selected_solution.solution_name,
                        capture,
                        selected_solution.description,
                        candidate_idea_id=getattr(selected_solution, "idea_id", None),
                        candidate_idea_revision=getattr(
                            selected_solution, "idea_revision", None
                        ),
                        niche_description=niche_description,
                        verified_pricing_evidence=verified_pricing_evidence,
                    ),
                    solution=selected_solution,
                )
                logger.info("[Stage 8] Traffic Monetization Analysis Complete")
                logger.info(f"  Monetization Model: {traffic_result.monetization_model}")
                logger.info(f"  Est. Monthly Pageviews: {traffic_result.estimated_monthly_pageviews}")
                logger.info(f"  Est. Monthly Revenue: {traffic_result.estimated_monthly_revenue_range}")
                logger.info(f"  Confidence: {traffic_result.monetization_confidence}")
                return traffic_result
            else:
                logger.error("[Stage 8] Traffic monetization analysis failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 8] Traffic monetization analysis error: {str(e)}")
            return None

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
