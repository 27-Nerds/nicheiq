"""
Market Sizing & Validation Crew (Stage 9).

Calculates TAM/SAM/SOM (Total/Serviceable/Obtainable Market) estimates and validates
market attractiveness using keyword demand, pain point frequency, and competitive analysis.
"""

import json
from typing import Any

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_crew_llm
from ..models.competitor import CompetitiveAnalysisResult, find_landscape_for_solution
from ..models.keyword_data import CrewKeywordValidationResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import MarketSizingResult
from ..models.solution_idea import SolutionIdea
from ..utils.score_helpers import score_band
from ..utils.crew_helpers import (
    collect_all_tiered_keywords,
    compute_commercial_intent_ratio,
    compute_difficulty_weighted_traffic,
    compute_intent_breakdown,
    compute_seo_market_enrichment,
    compute_strive_pre_check,
    compute_saturation_level,
    compute_tam_seed,
    compute_wtp_stats,
)
from ..utils.parsing.json_extractor import clean_llm_response


@CrewBase
class MarketSizingCrew:
    """
    Crew for market sizing and validation in Stage 9.

    Analyzes:
    - Keyword search volumes (market demand signals)
    - Pain point frequency (problem validation)
    - Competitive landscape (market saturation)
    - Selected solution positioning

    Outputs:
    - TAM/SAM/SOM estimates
    - Market validation signals
    - Growth potential assessment
    - Market viability verdict
    """

    agents_config = "config/market_sizing_agents.yaml"
    tasks_config = "config/market_sizing_tasks.yaml"

    def __init__(self):
        """Initialize MarketSizingCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def market_analyst(self) -> Agent:
        """
        Market Sizing Specialist agent.

        Calculates TAM/SAM/SOM using keyword-based, top-down,
        and bottom-up methodologies.
        """
        return Agent(
            config=self.agents_config["market_analyst"],
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.2,  # Low temperature for numerical accuracy (ignored for reasoning models)
            ),
            verbose=True,
        )

    @task
    def market_sizing_analysis_task(self) -> Task:
        """
        Main market sizing and validation task.

        Calculates TAM/SAM/SOM estimates and assesses market viability.
        """
        return SafeTask(
            config=self.tasks_config["market_sizing_analysis"],
            agent=self.market_analyst(),
            output_pydantic=MarketSizingResult,
            guardrail=self._validate_market_sizing_output,
        )

    def _validate_market_sizing_output(self, task_output) -> tuple[bool, Any]:
        """
        Validate market sizing output meets CRITICAL RULES.

        NOTE: This guardrail must remain (not moved to Pydantic) because it performs
        complex TAM > SAM > SOM hierarchy validation that requires cross-field comparison.

        CrewAI 1.8.1 Compatibility: When guardrails exist, pydantic=None by design.
        We must parse .raw directly and return (True, raw_string) on success.

        Checks:
        - TAM/SAM/SOM hierarchy (TAM > SAM > SOM)
        - Required numeric estimates present
        - Viability verdict matches data

        Args:
            task_output: Task output from CrewAI

        Returns:
            (True, raw_string) if validation passes, (False, error_message) if fails
        """
        try:
            # CrewAI 1.8.1: When guardrails exist, pydantic is intentionally None
            # Try pydantic first, then fall back to parsing .raw
            result = task_output.pydantic
            if result is None:
                # CrewAI 1.8.1 behavior: parse from .raw
                if not hasattr(task_output, 'raw') or not task_output.raw:
                    return (False, "Market sizing returned empty output (no pydantic or raw)")

                try:
                    # Clean LLM response to remove XML-like tags that may confuse JSON parsing
                    cleaned_raw = clean_llm_response(task_output.raw)
                    raw_json = json.loads(cleaned_raw)
                    result = MarketSizingResult.model_validate(raw_json)
                    logger.debug("Market sizing guardrail: Parsed MarketSizingResult from .raw")
                except json.JSONDecodeError as e:
                    logger.warning(f"[DEBUG] Failed to parse JSON from .raw: {e}")
                    logger.warning(f"[DEBUG] .raw first 500 chars: {task_output.raw[:500]}")
                    return (False, f"Invalid JSON in task output: {e}")
                except Exception as e:
                    logger.warning(f"[DEBUG] Failed to validate MarketSizingResult: {e}")
                    return (False, f"Failed to parse MarketSizingResult: {e}")

            # Ensure all required fields have estimates (not placeholders)
            if not result.total_addressable_market or result.total_addressable_market == "TBD":
                return (False, "TAM estimate must be provided (not TBD or empty)")

            if not result.serviceable_available_market or result.serviceable_available_market == "TBD":
                return (False, "SAM estimate must be provided (not TBD or empty)")

            if not result.serviceable_obtainable_market_y1 or result.serviceable_obtainable_market_y1 == "TBD":
                return (False, "SOM Year 1 estimate must be provided (not TBD or empty)")

            # Validate viability verdict is one of expected values
            valid_verdicts = ["Strong", "Moderate", "Weak"]
            if result.market_viability_verdict not in valid_verdicts:
                return (False, f"Viability verdict must be one of: {valid_verdicts}, got '{result.market_viability_verdict}'")

            # Validate saturation level
            valid_saturation = ["Low", "Medium", "High"]
            if result.market_saturation_level not in valid_saturation:
                return (False, f"Saturation level must be one of: {valid_saturation}, got '{result.market_saturation_level}'")

            # Validate timing assessment
            valid_timing = ["Early", "Growth", "Mature"]
            if result.market_timing_assessment not in valid_timing:
                return (False, f"Timing assessment must be one of: {valid_timing}, got '{result.market_timing_assessment}'")

            # Validate TAM/SAM/SOM hierarchy numerically (best effort).
            # Range-aware parsing: "$50-80M" → midpoint 65M (the old first-number
            # regex parsed it as 50 with no multiplier, breaking comparisons).
            try:
                from ..utils.validation.numeric_parsers import parse_dollar_amount

                tam_val = parse_dollar_amount(result.total_addressable_market) or 0.0
                sam_val = parse_dollar_amount(result.serviceable_available_market) or 0.0
                som_y1_val = parse_dollar_amount(result.serviceable_obtainable_market_y1) or 0.0
                som_y3_val = parse_dollar_amount(result.serviceable_obtainable_market_y3) or 0.0

                # Validate TAM > SAM > SOM hierarchy
                if tam_val > 0 and sam_val > 0:
                    if not (tam_val > sam_val):
                        return (False, f"TAM/SAM hierarchy violated: TAM ({result.total_addressable_market}) must be > SAM ({result.serviceable_available_market})")

                if sam_val > 0 and som_y1_val > 0:
                    if not (sam_val > som_y1_val):
                        return (False, f"SAM/SOM hierarchy violated: SAM ({result.serviceable_available_market}) must be > SOM Y1 ({result.serviceable_obtainable_market_y1})")

                # Validate SOM Y3 > SOM Y1 (growth over time)
                if som_y1_val > 0 and som_y3_val > 0:
                    if not (som_y3_val > som_y1_val):
                        return (False, f"SOM growth violated: SOM Y3 ({result.serviceable_obtainable_market_y3}) must be > SOM Y1 ({result.serviceable_obtainable_market_y1})")

                # 3-2-1 Rule: hard failure → LLM retry with the reason.
                # (Deterministic arithmetic the LLM can reliably correct.
                # Retry-thrash fallback if observed in practice: keep the
                # hierarchy checks above hard, demote these two to warnings.)
                if tam_val > 0 and sam_val > 0:
                    if tam_val < sam_val * 3:
                        return (False, f"3-2-1 Rule violated: TAM ({result.total_addressable_market}) must be >3x SAM ({result.serviceable_available_market}). Recalculate with a realistic narrowing from TAM to SAM.")

                if sam_val > 0 and som_y1_val > 0:
                    if sam_val < som_y1_val * 2:
                        return (False, f"3-2-1 Rule violated: SAM ({result.serviceable_available_market}) must be >2x SOM Y1 ({result.serviceable_obtainable_market_y1}). Recalculate with a realistic Year-1 obtainable share.")

            except Exception as numeric_error:
                # Log but don't fail validation if numeric parsing fails
                logger.warning(f"[Guardrail] Could not validate numeric hierarchy: {str(numeric_error)}")

            # CrewAI 1.8.1: Return raw string for CrewAI to re-parse
            return (True, task_output.raw)
        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    @crew
    def crew(self) -> Crew:
        """
        Assemble the market sizing crew.

        Single-agent, single-task crew optimized for market analysis.
        """
        return Crew(
            agents=[self.market_analyst()],
            tasks=[self.market_sizing_analysis_task()],
            verbose=True,
        )

    def analyze(
        self,
        selected_solution: SolutionIdea,
        keyword_validation: CrewKeywordValidationResult,
        pain_point_analysis: PainPointAnalysisResult,
        competitive_analysis: CompetitiveAnalysisResult,
        niche_description: str,
        seo_strategy_report=None,
        pricing_strategy=None,
    ) -> MarketSizingResult | None:
        """
        Execute market sizing crew to calculate TAM/SAM/SOM and validate market.

        Args:
            selected_solution: Selected solution from Stage 5
            keyword_validation: Keyword validation data from keyword validation
            pain_point_analysis: Pain point data from Stage 6
            competitive_analysis: Competitive landscape from Stage 7
            niche_description: Niche description for context

        Returns:
            MarketSizingResult with TAM/SAM/SOM estimates and viability verdict, or None if analysis fails
        """
        logger.info("[Stage 9] Starting Market Sizing & Validation...")
        logger.info(f"  Solution: {selected_solution.solution_name}")

        # Extract keyword demand signals
        keyword_signals = self._format_keyword_signals(keyword_validation, seo_strategy_report=seo_strategy_report)

        # Extract pain point signals
        pain_signals = self._format_pain_signals(pain_point_analysis, selected_solution)

        # Extract competitive signals (scoped to selected solution)
        competitive_signals = self._format_competitive_signals(competitive_analysis, selected_solution.solution_name)

        # Extract solution context
        solution_context = self._format_solution_context(selected_solution)

        # Pre-compute deterministic values.
        # BEACHHEAD vs FOLLOW-ON anchor (market-sizing methodology, docs/MARKET_SIZING_METHODOLOGY.md):
        # the headline SAM/SOM is anchored on the solution's OWN validated keyword demand (the beachhead
        # slice it actually serves), while the broad niche/SEO keyword expansion is the FOLLOW-ON reach
        # ceiling (drives TAM only, never the SAM headline). Anchoring SAM independently on the beachhead —
        # rather than as a % of an inflated niche TAM — avoids the "1% fallacy" for narrow ideas.
        if keyword_validation:
            unfiltered_volume = keyword_validation.total_volume or 0
            nrv = keyword_validation.niche_relevant_volume
            # niche_relevant_volume is the preferred semantically-filtered demand, BUT it is 0 when
            # keyword validation degraded (empty validated_keywords) — fall back to the solution's total
            # validated volume rather than zeroing the beachhead anchor.
            kv_volume = nrv if nrv else unfiltered_volume
            if kv_volume != unfiltered_volume and unfiltered_volume > 0:
                logger.info(
                    f"[Stage 9] Beachhead demand {kv_volume:,} (niche-relevant; "
                    f"unfiltered: {unfiltered_volume:,}, reduction: {(1 - kv_volume / unfiltered_volume) * 100:.0f}%)"
                )
        elif seo_strategy_report:
            kv_volume = seo_strategy_report.total_monthly_volume or 0
            unfiltered_volume = kv_volume
            logger.info(f"[Stage 9] No per-solution keyword validation — beachhead falls back to SEO volume {kv_volume:,}")
        else:
            kv_volume = 0
            unfiltered_volume = 0

        # Follow-on reach ceiling = the broadest keyword universe available (niche SEO expansion, or the
        # unfiltered keyword total). Equals the beachhead when no broader signal exists (honest no-op).
        beachhead_volume = kv_volume
        seo_total_volume = (seo_strategy_report.total_monthly_volume or 0) if seo_strategy_report else 0
        niche_reach_ceiling = max(seo_total_volume, unfiltered_volume, beachhead_volume)
        if niche_reach_ceiling > beachhead_volume and beachhead_volume > 0:
            logger.info(
                f"[Stage 9] Follow-on reach ceiling {niche_reach_ceiling:,} "
                f"({niche_reach_ceiling / beachhead_volume:.1f}x the beachhead) — TAM only, not the SAM headline"
            )

        # Pricing anchor (rec #3): ground the per-customer value on the real Stage-7 pricing analysis
        # (ARPU/LTV) so the LLM doesn't invent a number. Falls back to a WTP-derivation instruction.
        if pricing_strategy is not None:
            _pp = []
            _summ = pricing_strategy.format_summary() if hasattr(pricing_strategy, "format_summary") else None
            if _summ:
                _pp.append(f"Pricing model: {_summ}")
            if getattr(pricing_strategy, "estimated_arpu", None):
                _pp.append(f"Estimated ARPU: {pricing_strategy.estimated_arpu}")
            if getattr(pricing_strategy, "estimated_ltv", None):
                _pp.append(f"Estimated LTV: {pricing_strategy.estimated_ltv}")
            pricing_anchor = " | ".join(_pp) if _pp else "No pricing analysis available."
        else:
            pricing_anchor = ("No pricing analysis available — derive the per-customer value from the "
                              "willingness-to-pay signals and competitor pricing in the context above.")

        pp_mentions = pain_point_analysis.total_mentions if pain_point_analysis else 0
        selected_landscape = find_landscape_for_solution(competitive_analysis, selected_solution.solution_name)
        competitor_count = len(selected_landscape.competitors or []) if selected_landscape else 0

        strive_pre_check = compute_strive_pre_check(kv_volume, pp_mentions, competitor_count)
        suggested_saturation_level = compute_saturation_level(competitor_count)
        tam_seed = compute_tam_seed(kv_volume)
        wtp = compute_wtp_stats(pain_point_analysis)
        seo_market_enrichment = compute_seo_market_enrichment(seo_strategy_report)

        # Set unconditional defaults for all new template variables FIRST
        seo_som_ceiling_y1 = "N/A (no SEO data)"
        seo_commercial_intent_pct = "N/A (no SEO data)"

        # Override with real values if SEO data available
        if seo_strategy_report:
            tier_1 = getattr(seo_strategy_report, "tier_1_keywords", None) or []
            tier_2 = getattr(seo_strategy_report, "tier_2_keywords", None) or []
            t1_low, t1_high = compute_difficulty_weighted_traffic(tier_1)
            t2_low, t2_high = compute_difficulty_weighted_traffic(tier_2)
            y1_low = t1_low + int(t2_low * 0.6)
            y1_high = t1_high + int(t2_high * 0.6)
            seo_som_ceiling_y1 = f"{y1_low:,}-{y1_high:,} visits/mo"

            all_keywords = collect_all_tiered_keywords(seo_strategy_report)
            intent = compute_intent_breakdown(all_keywords)
            commercial_pct = compute_commercial_intent_ratio(intent)
            seo_commercial_intent_pct = f"{commercial_pct:.0f}%"

        # Prepare inputs for market sizing task
        inputs = {
            "solution_name": selected_solution.solution_name,
            "solution_description": selected_solution.description,
            "solution_context": solution_context,
            "niche_description": niche_description,
            "keyword_demand_signals": keyword_signals,
            "pain_point_signals": pain_signals,
            "competitive_signals": competitive_signals,
            "total_keyword_volume": kv_volume,
            "beachhead_demand_volume": beachhead_volume,
            "niche_reach_ceiling": niche_reach_ceiling,
            "pricing_anchor": pricing_anchor,
            "unfiltered_keyword_volume": unfiltered_volume,
            "validated_keyword_count": keyword_validation.validated_count if keyword_validation else (seo_strategy_report.total_keywords_analyzed if seo_strategy_report else 0),
            "pain_point_count": len(pain_point_analysis.pain_points) if pain_point_analysis else 0,
            "competitor_count": competitor_count,
            "strive_pre_check": strive_pre_check,
            "suggested_saturation_level": suggested_saturation_level,
            "tam_seed": tam_seed,
            "high_severity_count": wtp["high_severity_count"],
            "high_wtp_count": wtp["high_wtp_count"],
            "avg_wtp": wtp["avg_wtp"],
            "seo_market_enrichment": seo_market_enrichment,
            "seo_som_ceiling_y1": seo_som_ceiling_y1,
            "seo_commercial_intent_pct": seo_commercial_intent_pct,
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                market_result = result.pydantic
                logger.info("[Stage 9] Market Sizing Complete")
                logger.info(f"  TAM: {market_result.total_addressable_market}")
                logger.info(f"  SAM: {market_result.serviceable_available_market}")
                logger.info(f"  SOM (Y1): {market_result.serviceable_obtainable_market_y1}")
                logger.info(f"  Viability: {market_result.market_viability_verdict}")
                logger.info(f"  Entry Strategy: {market_result.recommended_entry_strategy}")
                return market_result
            else:
                logger.error("[Stage 9] Market sizing failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 9] Market sizing error: {str(e)}")
            return None

    def _format_keyword_signals(self, keyword_validation: CrewKeywordValidationResult | None, seo_strategy_report=None) -> str:
        """Format keyword demand signals for market sizing.

        Prefers SEO strategy report data when keyword_validation is None.
        """
        # Primary path: use SEO strategy report when keyword_validation is None
        if not keyword_validation and seo_strategy_report:
            import re

            all_keywords = []
            for tier_attr in ['tier_0_keywords', 'tier_1_keywords', 'tier_2_keywords']:
                tier_kws = getattr(seo_strategy_report, tier_attr, None) or []
                all_keywords.extend(tier_kws)

            total_volume = seo_strategy_report.total_monthly_volume or 0
            keyword_count = seo_strategy_report.total_keywords_analyzed or 0

            if total_volume >= 5000:
                demand_signal = "strong"
            elif total_volume >= 2000:
                demand_signal = "moderate"
            else:
                demand_signal = "weak"

            # Parse avg competition from tier keywords
            competitions = []
            for k in all_keywords:
                comp = getattr(k, 'competition', None)
                if comp and isinstance(comp, str):
                    match = re.search(r'\((\d+)\)', comp)
                    if match:
                        competitions.append(int(match.group(1)))
                        continue
                kd = getattr(k, 'keyword_difficulty', None)
                if kd is not None:
                    competitions.append(int(kd))
            avg_competition = sum(competitions) / len(competitions) if competitions else 50.0

            signals = []
            signals.append(f"**Total Monthly Search Volume:** {total_volume:,} searches (SEO strategy data)")
            signals.append(f"**Analyzed Keywords:** {keyword_count}")
            signals.append(f"**Demand Signal:** {demand_signal}")
            signals.append(f"**Average Competition:** {avg_competition:.2f}")

            top_keywords = sorted(all_keywords, key=lambda k: k.search_volume, reverse=True)[:5]
            if top_keywords:
                signals.append("\n**Top Keywords:**")
                for kw in top_keywords:
                    signals.append(f"- {kw.keyword}: {kw.search_volume:,}/month")

            return "\n".join(signals)

        if not keyword_validation:
            return "No keyword validation data available."

        signals = []
        signals.append(f"**Total Monthly Search Volume:** {keyword_validation.total_volume:,} searches")
        signals.append(f"**Validated Keywords:** {keyword_validation.validated_count}")
        signals.append(f"**Demand Signal:** {keyword_validation.demand_signal}")
        signals.append(f"**Average Competition:** {keyword_validation.avg_competition:.2f}")

        if keyword_validation.top_keywords:
            signals.append("\n**Top Keywords:**")
            for kw in keyword_validation.top_keywords[:5]:
                keyword_text = kw.get('keyword', 'N/A')
                volume = kw.get('volume', 0)
                signals.append(f"- {keyword_text}: {volume:,}/month")

        return "\n".join(signals)

    def _format_pain_signals(
        self,
        pain_point_analysis: PainPointAnalysisResult | None,
        selected_solution: SolutionIdea | None = None,
    ) -> str:
        """Format pain point signals for market validation.

        When the solution declares which pains it addresses, narrow the niche-wide pain corpus
        to just the addressed slice so the LLM sizes the SERVICEABLE market, not the whole niche
        (top-down keyword volume already captures the niche). Bands severity/WTP so no raw 0-1
        score leaks into the sizing prose.
        """
        if not pain_point_analysis or not pain_point_analysis.pain_points:
            return "No pain point data available."

        all_pains = pain_point_analysis.pain_points
        pains = all_pains
        scope_note = None
        if (
            selected_solution is not None
            and getattr(selected_solution, "pain_points_addressed", None)
        ):
            scoped = self._scope_pains_to_solution(all_pains, selected_solution.pain_points_addressed)
            if scoped:
                pains = scoped
                scope_note = (
                    f"**Scope:** this idea addresses {len(scoped)} of {len(all_pains)} validated pains. "
                    "Size the SERVICEABLE slice these pains represent, not the whole niche."
                )

        signals = []
        if scope_note:
            signals.append(scope_note)
        signals.append(f"**Pain Points In Scope:** {len(pains)}")
        signals.append(f"**Total Mentions (niche-wide):** {pain_point_analysis.total_mentions}")

        high_severity = [pp for pp in pains if pp.severity_score >= 0.7]
        signals.append(f"**High Severity Pain Points (in scope):** {len(high_severity)}")

        if pains:
            signals.append("\n**Top Pain Points:**")
            for pp in pains[:5]:
                signals.append(
                    f"- {pp.title} (severity: {score_band(pp.severity_score)}, "
                    f"willingness-to-pay: {score_band(pp.commercial_intent)})"
                )

        return "\n".join(signals)

    @staticmethod
    def _scope_pains_to_solution(pains: list, addressed: list[str]) -> list:
        """Return the subset of ``pains`` the solution's ``pain_points_addressed`` strings refer to,
        by token overlap (>=0.5 of the smaller token set) against each pain's title/categories/description.
        Reuses ``segment_matching._tokens`` (shared stemmer/stopwords) so we don't fork a tokenizer."""
        from ..utils.segment_matching import _tokens

        addressed_tokens = [_tokens(a) for a in addressed if a]
        addressed_tokens = [t for t in addressed_tokens if t]
        if not addressed_tokens:
            return []
        out = []
        for pp in pains:
            pv = _tokens(
                getattr(pp, "title", "") or "",
                " ".join(getattr(pp, "categories", None) or []),
                getattr(pp, "description", "") or "",
            )
            if not pv:
                continue
            for av in addressed_tokens:
                shared = pv & av
                if shared and len(shared) >= 0.5 * min(len(pv), len(av)):
                    out.append(pp)
                    break
        return out

    def _format_competitive_signals(
        self,
        competitive_analysis: CompetitiveAnalysisResult | None,
        selected_solution_name: str | None = None,
    ) -> str:
        """Format competitive landscape for market saturation assessment.

        Scoped to the selected solution's landscape rather than aggregating
        across all landscapes.
        """
        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            return "No competitive analysis data available."

        landscape = find_landscape_for_solution(competitive_analysis, selected_solution_name)
        if not landscape:
            return "No competitive analysis data available."

        signals = []

        competitor_count = len(landscape.competitors or [])
        signals.append(f"**Competitors Identified:** {competitor_count}")

        if landscape.market_gaps:
            signals.append(f"\n**Market Gaps:** {len(landscape.market_gaps)} opportunities identified")

        if landscape.competitors:
            signals.append("\n**Sample Competitors:**")
            for comp in landscape.competitors[:5]:
                signals.append(f"- {comp.name}")

        return "\n".join(signals)

    def _format_solution_context(self, solution: SolutionIdea) -> str:
        """Format solution details for market sizing context."""
        context = []
        context.append(f"**Market Fit Score:** {solution.market_fit_score:.2f}")

        if solution.target_personas:
            context.append(f"\n**Target Personas:** {', '.join(solution.target_personas[:3])}")

        if solution.core_features:
            context.append(f"\n**Core Features:** {len(solution.core_features)} features")

        return "\n".join(context)

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
