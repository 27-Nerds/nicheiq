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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..flows.checkpoint_manager import CheckpointManager

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ..config.settings import settings
from ..utils.llm_service import LLMService, build_crew_llm, build_llm_kwargs
from ..models.competitor import CompetitiveAnalysisResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import AudienceMappingResult, NicheContext
from ..models.social_content import SocialContentCollection
from ..models.solution_idea import (
    FilteredConceptList,
    IdeaGenerationResult,
    RawConcept,
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
from ..utils.validation.crew_guardrails import (
    _tags_match,
    raw_concept_quality_error,
    validate_raw_concept_list,
)


_NAME_STOP_WORDS = {"the", "a", "an", "app", "tool", "pro", "hub", "io", "ai", "my"}


def _tokenize_name(name: str) -> list[str]:
    """Tokenize a concept name into normalized fragments for frequency analysis.

    Order: strip hyphens between alnum → split camelCase → split whitespace/underscores
    → lowercase → filter stop words and short tokens.
    """
    # 1. Strip hyphens between alphanumeric chars (e.g. "Model-3" → "Model3")
    result = re.sub(r"(?<=[A-Za-z0-9])-(?=[A-Za-z0-9])", "", name)
    # 2. Split camelCase boundaries (SideEffect → Side Effect)
    result = re.sub(r"([a-z])([A-Z])", r"\1 \2", result)
    result = re.sub(r"([0-9])([A-Z])", r"\1 \2", result)
    # 3. Split on whitespace/underscores
    tokens = re.split(r"[\s_]+", result)
    # 4-5. Lowercase, filter stop words and tokens < 2 chars
    return [t.lower() for t in tokens if len(t) >= 2 and t.lower() not in _NAME_STOP_WORDS]


# Independent creative lenses for multi-sample divergent generation. Each divergent
# sample renders the SAME prompt with a different {lens_directive} so the independent
# LLM contexts explore orthogonal strategies (the only diversity lever on a reasoning
# model, since temperature is inert). Domain-NEUTRAL: they describe a thinking strategy,
# never a niche or a named product. The "extremize" clause fights middle-ground
# convergence between blind parallel samples.
_LENS_EXTREMIZE = (
    " Another independent call is generating concepts from a DIFFERENT lens right now; "
    "you cannot see it. Do NOT hedge toward safe middle-ground ideas — push your lens "
    "further than feels warranted so the two sets stay distinct."
)
_DIVERGENT_LENSES = [
    (
        "## CREATIVE LENS FOR THIS PASS: POWER-USER GAP\n"
        "Approach EVERY pain from the perspective of the most sophisticated person already "
        "using existing tools in this space — someone who knows precisely where every current "
        "tool falls short. Bias your concepts toward: (a) data or signals that existing tools "
        "collect or touch but never expose to the user; (b) steps that are manual, offline, or "
        "copy-pasted today but are automatable; (c) pains that only surface after months of "
        "serious use. Exploit gaps a novice would never even notice." + _LENS_EXTREMIZE
    ),
    (
        "## CREATIVE LENS FOR THIS PASS: STRUCTURAL INVERSION + CROSS-DOMAIN TRANSFER\n"
        "For each pain, first INVERT the obvious flow — what if the product worked output-first "
        "instead of input-first, passively monitored instead of actively searched, or served the "
        "producer side instead of the consumer side? Then TRANSFER the structural logic of an "
        "abstract archetype from an unrelated domain — a professional data terminal (charges for "
        "exclusive, structured data generalists don't organize), a curated editorial product "
        "(human-verified, opinionated, trust over volume), a passive activity tracker (collects "
        "value over time without explicit input), or a developer-toolchain module (slots into an "
        "existing workflow rather than being a destination). Do NOT name any specific real product "
        "or brand — inherit only the structural pattern. Generate AT LEAST one concept that works "
        "under a hard constraint: no user accounts, or fully offline, or operable by a "
        "non-technical person." + _LENS_EXTREMIZE
    ),
]


# Interpolate only `{identifier}` tokens (CrewAI's _VARIABLE_PATTERN), leaving JSON
# braces and unknown tokens untouched — so rendering the divergent prompt for direct
# LLM calls is safe where str.format would crash on the prompt's literal JSON examples.
_TEMPLATE_VAR = re.compile(r"\{([A-Za-z_][A-Za-z0-9_\-]*)\}")


def _interpolate_template(template: str, values: dict) -> str:
    def _sub(m):
        key = m.group(1)
        return str(values[key]) if key in values else m.group(0)
    return _TEMPLATE_VAR.sub(_sub, template)


class _LooseConceptBatch(BaseModel):
    """Lenient per-sample divergent output (no min/max on concepts), so a sample that
    under-produces does NOT raise inside invoke_structured. Pooled into a proper
    RawConceptList (clamped) afterward."""
    model_config = ConfigDict(extra='ignore')
    concepts: list[RawConcept] = Field(default_factory=list)
    techniques_used: list[str] = Field(default_factory=list)
    pain_points_referenced: list[str] = Field(default_factory=list)


class _NoveltyVerdict(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: str = ""
    independent_obviousness: float = 0.5
    already_exists: bool = False
    reason: str = ""


class _NoveltyVerdicts(BaseModel):
    model_config = ConfigDict(extra='ignore')
    verdicts: list[_NoveltyVerdict] = Field(default_factory=list)


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

        # Caveats from post-crew pain-coverage enforcement (set in execute_pipeline).
        self.coverage_caveats: list[str] = []

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

            # M/D/J structural tags (when persisted) so the cross-run dedup gate can
            # catch a reworded idea with the same mechanism+data+journey.
            m, d, j = idea.get("mechanism_tag"), idea.get("data_source_tag"), idea.get("journey_tag")
            mdj = f" [M/D/J: {m or '?'} | {d or '?'} | {j or '?'}]" if (m or d or j) else ""

            if compact:
                lines.append(f"- {name_part}{mdj} | summary: {summary}")
            else:
                if max_desc_len > 0 and desc:
                    desc_truncated = desc[:max_desc_len] + ("..." if len(desc) > max_desc_len else "")
                    lines.append(f"- {name_part}{mdj} [summary: {summary}]: {desc_truncated}")
                else:
                    lines.append(f"- {name_part}{mdj} [summary: {summary}]")

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

    def _format_regeneration_directive(self) -> str:
        """Regeneration-only block: re-approach the SAME pains from new ANGLES.

        Empty string on first generation. On regeneration it reframes the task
        from "avoid the previous ideas" (pure blacklist) to "deliberately explore
        the dimensions the previous batch did NOT" — different mechanism, persona,
        journey moment, data source, or a contrarian framing — so the new batch is
        genuinely additive rather than reworded cousins of what already exists.
        """
        if not self.existing_ideas:
            return ""
        n = len(self.existing_ideas)
        return (
            "## STEP 0.6: REGENERATION — Explore NEW ANGLES (this is a 'generate more' run)\n\n"
            f"The user already has the {n} ideas listed above and asked for MORE. They do\n"
            "NOT want the same concepts reworded — they want genuinely different angles on\n"
            "the same validated pains. Avoiding the blacklist is necessary but NOT enough.\n\n"
            "Before generating, do this in writing:\n"
            "1. ANGLE MAP: for the existing ideas, note which (pain × mechanism × data\n"
            "   source × user-journey moment × persona) combinations they already cover.\n"
            "2. FIND THE GAPS: for each high-value pain, identify angles the existing set\n"
            "   did NOT take. Deliberately shift AT LEAST ONE dimension per new concept:\n"
            "   - Different MECHANISM (if a pain was solved by a calculator, try an\n"
            "     aggregator, a monitor/alert, a community-data loop, or a directory).\n"
            "   - Different USER-JOURNEY MOMENT (before buying vs during use vs\n"
            "     troubleshooting-after-a-mistake vs ongoing monitoring).\n"
            "   - Different PERSONA/segment within the niche (e.g. first-timer vs\n"
            "     power user vs the person who advises others).\n"
            "   - Different DATA SOURCE or wedge.\n"
            "   - A CONTRARIAN / inverted framing of the same pain.\n"
            "3. Also cover any UNDER-SERVED pain the previous batch barely touched.\n\n"
            "Each new concept's why_non_obvious must state WHICH angle it takes that the\n"
            "existing ideas did not. A concept that shares M+D, M+J, or all three with any\n"
            "existing idea (see its [M/D/J: ...] tags above) is a reworded cousin — REJECT it\n"
            "in the STEP 0.75 gate and replace it with one that shifts a real dimension.\n"
        )

    # ========== MULTI-SAMPLE DIVERGENT GENERATION ==========

    def _render_divergent_prompt(self, inputs: dict, lens: str) -> str:
        """Render the divergent task description for a direct LLM call under one lens.

        Uses identifier-only interpolation (CrewAI-faithful) — never str.format, which
        crashes on the prompt's literal JSON braces.
        """
        template = self.tasks_config["divergent_exploration"]["description"]
        return _interpolate_template(template, {**inputs, "lens_directive": lens})

    def _generate_divergent_pool(self, inputs: dict) -> tuple[list, object]:
        """Run N INDEPENDENT divergent calls under different lenses (parallel), validate
        each leniently with one re-prompt, and return (pooled_concepts, total_usage).

        Pure over locals — no self.* writes inside threads (thread-safety).
        """
        n = max(1, settings.num_divergent_samples)
        lenses = [_DIVERGENT_LENSES[i % len(_DIVERGENT_LENSES)] for i in range(n)]

        def _one_sample(idx: int, lens: str):
            prompt = self._render_divergent_prompt(inputs, lens)
            usages = []
            last_err = None
            for attempt in range(2):  # validate + one re-prompt
                p = prompt if attempt == 0 else (
                    prompt + f"\n\nYOUR PREVIOUS ATTEMPT FAILED VALIDATION: {last_err}. "
                    "Fix it and return the full concept list again."
                )
                try:
                    batch, usage = LLMService.invoke_structured(
                        prompt=p,
                        output_model=_LooseConceptBatch,
                        temperature=0.85,
                        timeout=180,
                        model_name=settings.brainstorm_llm,
                        reasoning_effort=settings.brainstorm_reasoning_effort,
                    )
                    usages.append(usage)
                except Exception as e:  # parse/timeout — retry once then give up
                    last_err = str(e)[:160]
                    logger.warning(f"[Divergent sample {idx}] call failed (attempt {attempt+1}): {last_err}")
                    continue
                # lenient validation, but DROP per-concept low-quality items
                valid = [c for c in batch.concepts if raw_concept_quality_error(c) is None]
                ok, err = validate_raw_concept_list(
                    batch, min_concepts=1, check_technique_diversity=False
                )
                if ok and valid:
                    logger.info(f"[Divergent sample {idx}] lens-{idx % len(lenses)}: {len(valid)} concepts")
                    return valid, usages
                last_err = err or "all concepts failed per-concept quality"
                if valid:  # keep whatever passed even if the batch as a whole was thin
                    logger.info(f"[Divergent sample {idx}] kept {len(valid)} valid concepts (batch flagged: {last_err})")
                    return valid, usages
            logger.warning(f"[Divergent sample {idx}] produced no valid concepts")
            return [], usages

        pooled: list = []
        all_usages: list = []
        with ThreadPoolExecutor(max_workers=min(n, 4)) as ex:
            futures = {ex.submit(_one_sample, i, lens): i for i, lens in enumerate(lenses)}
            for fut in as_completed(futures):
                concepts, usages = fut.result()
                pooled.extend(concepts)
                all_usages.extend(usages)
        logger.info(f"[Divergent] {n} samples → {len(pooled)} pooled concepts (pre-dedup)")
        return pooled, all_usages

    def _score_pool_novelty(self, concepts: list) -> list:
        """INDEPENDENT novelty critic (separate cheap call, runs BEFORE dedup).

        Overwrites each concept's obviousness_score with an independent estimate and
        DROPS concepts that already exist (per the competitor/tool data we collect).
        Fail-open: on any error or empty competitor data, return concepts unchanged.
        """
        if not concepts:
            return concepts
        competitor_block = self._format_competitor_mentions()
        tools_block = ""
        if self.audience_mapping and getattr(self.audience_mapping, "tools_currently_used", None):
            tools_block = ", ".join(str(t) for t in self.audience_mapping.tools_currently_used[:12])
        if not (competitor_block and competitor_block.strip()) and not tools_block:
            return concepts  # no reality anchor → advisory only, skip

        listing = "\n".join(
            f"- {c.concept_name}: {(c.one_liner or '')[:160]}" for c in concepts
        )
        prompt = (
            "You are an INDEPENDENT novelty critic (a different judge from whoever "
            "generated these concepts). For EACH concept, estimate:\n"
            "- independent_obviousness (0.0-1.0): the fraction of competent SaaS builders "
            "who would ALSO propose essentially this concept. 0.0=almost none (genuinely "
            "novel), 1.0=nearly everyone (cached first-thought). Consider: is the data "
            "source genuinely unusual or a standard API? is the mechanism a known pattern "
            "(calculator/directory/comparison)? \n"
            "- already_exists (true/false): does a close equivalent appear in the EXISTING "
            "TOOLS / COMPETITORS below, or is it an obvious skin on a known product?\n\n"
            f"EXISTING TOOLS / COMPETITORS (what already exists):\n{competitor_block}\n"
            f"Tools the audience already uses: {tools_block}\n\n"
            f"CONCEPTS:\n{listing}\n\n"
            "Return a verdict for EVERY concept, keyed by its exact name."
        )
        try:
            result, _usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=_NoveltyVerdicts,
                temperature=0,
                timeout=120,
                model_name=settings.ideation_judge_llm,
                reasoning_effort=settings.ideation_judge_reasoning_effort,
            )
            self._record_divergent_usage([_usage])
        except Exception as e:
            logger.warning(f"[CRITIC] novelty scoring skipped (fail-open): {str(e)[:120]}")
            return concepts

        by_name = {v.name.strip().lower(): v for v in result.verdicts if v.name}
        kept: list = []
        dropped = 0
        for c in concepts:
            v = by_name.get((c.concept_name or "").strip().lower())
            if v is not None:
                c.obviousness_score = max(0.0, min(1.0, v.independent_obviousness))
                if v.already_exists:
                    dropped += 1
                    logger.info(f"[CRITIC] dropped already-existing: {c.concept_name} — {v.reason[:80]}")
                    continue
            kept.append(c)
        if dropped:
            logger.info(f"[CRITIC] dropped {dropped} already-existing concepts; {len(kept)} remain")
        return kept if kept else concepts  # never drop everything

    def _pool_and_dedup_raw_concepts(self, concepts: list) -> list:
        """Dedup the pooled concepts and clamp to [6, divergent_pool_cap].

        Name dedup first (exact/normalized, keep lower INDEPENDENT obviousness), then
        ADVISORY structural M/D/J dedup that is FLOOR-GUARDED (won't collapse the pool
        below the minimum — two independent lenses on the same pains collide a lot).
        The -1.0 'not scored' sentinel is treated as unknown (never 'most novel').
        """
        cap = settings.divergent_pool_cap
        MIN_KEEP = 6

        def _obv(c) -> float:
            s = getattr(c, "obviousness_score", -1.0)
            return s if (s is not None and s >= 0) else 1.5  # unknown ranked worst, not best

        # 1. Normalized-name dedup
        by_norm: dict[str, object] = {}
        for c in concepts:
            key = "".join((c.concept_name or "").lower().split())
            if not key:
                continue
            if key not in by_norm or _obv(c) < _obv(by_norm[key]):
                by_norm[key] = c
        deduped = sorted(by_norm.values(), key=_obv)  # most-novel first

        # 2. Advisory structural dedup, floor-guarded
        kept: list = []
        dropped: list = []
        for c in deduped:
            is_struct_dup = any(
                sum((
                    _tags_match(getattr(c, "mechanism_tag", None), getattr(k, "mechanism_tag", None)),
                    _tags_match(getattr(c, "data_source_tag", None), getattr(k, "data_source_tag", None)),
                    _tags_match(getattr(c, "journey_tag", None), getattr(k, "journey_tag", None)),
                )) >= 2
                for k in kept
            )
            if is_struct_dup:
                dropped.append(c)
            else:
                kept.append(c)
        # Refill if structural dedup over-collapsed below the floor
        while len(kept) < MIN_KEEP and dropped:
            kept.append(dropped.pop(0))

        # 3. Clamp to cap (keep most-novel)
        return sorted(kept, key=_obv)[:cap]

    def _format_pooled_concepts(self, concepts: list) -> str:
        """Render pooled concepts as a text block for the filter prompt (carries all
        fields the filter must pass through unchanged: tags + obviousness)."""
        lines = []
        for i, c in enumerate(concepts, 1):
            kws = ", ".join(c.target_keywords or [])
            lines.append(
                f"{i}. {c.concept_name} [{c.project_type}] (technique: {c.ideation_technique}, "
                f"obviousness: {getattr(c, 'obviousness_score', -1.0)})\n"
                f"   one_liner: {c.one_liner}\n"
                f"   target_keywords: {kws}\n"
                f"   data_source_hint: {c.data_source_hint or ''}\n"
                f"   why_non_obvious: {c.why_non_obvious or ''}\n"
                f"   M/D/J: {c.mechanism_tag or '?'} | {c.data_source_tag or '?'} | {c.journey_tag or '?'}"
            )
        return "\n\n".join(lines) if lines else "(no concepts)"

    def _refine_single_concept(self, concept, pain):
        """Expand ONE pooled concept into a COMPLETE BaseSolutionIdea via the brainstorm
        model — so a re-injected (coverage/bold) idea is as complete as the others.

        Returns a fully-populated BaseSolutionIdea, or falls back to the lightweight
        stub synthesizer on any failure (never raises)."""
        from ..models.solution_idea import BaseSolutionIdea
        from ..utils.validation.crew_guardrails import _synthesize_idea_from_concept

        niche = getattr(self.niche_context, "niche_description", "") if self.niche_context else ""
        pain_title = getattr(pain, "title", "") if pain else ""
        allowed = ", ".join(self.allowed_project_types) if self.allowed_project_types else "any"
        prompt = (
            "Expand this ONE solution concept into a COMPLETE product specification with "
            "the SAME depth and field coverage as a fully-refined idea. Fill EVERY field, "
            "grounded in the concept and niche (do not leave fields blank):\n"
            "headline (5-12 words), short_description (<180 chars), description (4-6 "
            "sentences on HOW it works for the user), value_proposition, pain_points_addressed "
            f"(MUST include \"{pain_title}\"), core_features, target_personas, technical_approach, "
            "differentiation_factors, requires_data_aggregation, data_sources, "
            "estimated_development_time, pricing_strategy, programmatic_seo_opportunity, "
            "content_generation_model, organic_discovery_queries (5-10), estimated_cac_organic, "
            "estimated_cac_paid. ALL numeric scores are 0.0-1.0 decimals: market_fit_score, "
            "technical_feasibility_score, seo_scalability_score, solo_dev_feasibility, "
            "novelty_score. For novelty justification fill conventional_approach, "
            "innovation_angle, why_it_works (each a real sentence), and why_it_works_short "
            "(<=120 chars).\n\n"
            f"NICHE: {niche}\n"
            f"ALLOWED PROJECT TYPES: {allowed}\n"
            f"This concept addresses the high-severity pain: \"{pain_title}\".\n\n"
            f"CONCEPT NAME: {concept.concept_name}\n"
            f"ONE-LINER: {concept.one_liner}\n"
            f"PROJECT TYPE: {concept.project_type}\n"
            f"TARGET KEYWORDS: {', '.join(concept.target_keywords or [])}\n"
            f"WHY NON-OBVIOUS: {concept.why_non_obvious or ''}\n"
        )
        try:
            idea, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=BaseSolutionIdea,
                temperature=0.4,
                timeout=180,
                model_name=settings.ideation_refine_llm,
                reasoning_effort=settings.ideation_refine_reasoning_effort,
            )
            self._record_divergent_usage([usage])
            # Carry structural tags + guarantee the two required scores are present.
            idea.solution_name = idea.solution_name or concept.concept_name
            idea.mechanism_tag = concept.mechanism_tag
            idea.data_source_tag = concept.data_source_tag
            idea.journey_tag = concept.journey_tag
            _obv = getattr(concept, "obviousness_score", -1.0)
            idea.obviousness_score = _obv if (_obv is not None and _obv >= 0) else None
            if idea.market_fit_score is None:
                idea.market_fit_score = 0.5
            if idea.technical_feasibility_score is None:
                idea.technical_feasibility_score = 0.5
            if not idea.pain_points_addressed:
                idea.pain_points_addressed = [pain_title or "high-severity pain"]
            return idea
        except Exception as e:
            logger.warning(f"[REINJECT] full refinement of '{concept.concept_name}' failed, "
                           f"using stub: {str(e)[:120]}")
            return _synthesize_idea_from_concept(concept, pain)

    def _record_divergent_usage(self, usages: list) -> None:
        """Record direct-LLM divergent/critic token usage into the cost tracker (these
        calls bypass the crew's usage_metrics, which only covers the convergent crew)."""
        if not (hasattr(self, "cost_tracker") and self.cost_tracker):
            return
        for usage in usages or []:
            try:
                self.cost_tracker.record_llm_usage(
                    "Stage 7 - Divergent Sampling",
                    usage.to_dict() if hasattr(usage, "to_dict") else usage,
                )
            except Exception:
                pass

    # Bold-slot thresholds: a final idea "counts" as bold if its novelty_score is high
    # OR it traces to a low-obviousness pooled concept.
    _BOLD_NOVELTY = 0.6
    _BOLD_OBVIOUSNESS = 0.35

    def _enforce_bold_slot(self, final_ideas: list, raw_concepts) -> None:
        """Ensure the final set has >=1 genuinely original idea; else re-inject the
        lowest-obviousness pooled concept (fully refined). Mutates in place; never raises."""
        concepts = list(getattr(raw_concepts, "concepts", None) or [])
        if not final_ideas or not concepts:
            return

        def _norm(n: str) -> str:
            return "".join((n or "").lower().split())

        # obviousness by concept name (treat -1.0 sentinel as ineligible/unknown)
        obv_by_name = {}
        for c in concepts:
            s = getattr(c, "obviousness_score", -1.0)
            if s is not None and s >= 0:
                obv_by_name[_norm(c.concept_name)] = s

        # Already bold? (high novelty OR traces to a low-obviousness concept)
        for idea in final_ideas:
            nov = getattr(idea, "novelty_score", None)
            if nov is not None and nov >= self._BOLD_NOVELTY:
                return
            src = obv_by_name.get(_norm(getattr(idea, "solution_name", "")))
            if src is not None and src <= self._BOLD_OBVIOUSNESS:
                return

        # Pick the lowest-obviousness ELIGIBLE concept not already in the final set.
        final_names = {_norm(getattr(i, "solution_name", "")) for i in final_ideas}
        candidates = [
            c for c in concepts
            if _norm(c.concept_name) not in final_names
            and _norm(c.concept_name) in obv_by_name
        ]
        if not candidates:
            return
        boldest = min(candidates, key=lambda c: obv_by_name[_norm(c.concept_name)])

        pains = self.pain_point_analysis.pain_points
        top_pain = max(pains, key=lambda p: getattr(p, "severity_score", 0) or 0) if pains else None
        if top_pain is None:
            return
        # Fully refine the boldest concept so it's as complete as the rest.
        bold = self._refine_single_concept(boldest, top_pain)
        if bold is None:
            return
        # It IS the lowest-obviousness concept → floor novelty so the bold signal holds.
        bold.novelty_score = max(bold.novelty_score or 0.0, 0.6)
        final_ideas.append(bold)
        self.coverage_caveats = list(getattr(self, "coverage_caveats", []) or []) + [
            f"Bold slot: re-injected '{bold.solution_name}' as a deliberately original option "
            f"(the generated set lacked a high-novelty idea)."
        ]
        logger.warning(f"[BOLD SLOT] Re-injected '{bold.solution_name}' "
                       f"(obviousness {obv_by_name[_norm(boldest.concept_name)]:.2f})")

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
        Agent for evaluating/filtering solution concepts (convergent JUDGE tier).
        Scoring against fixed criteria — no creativity needed — so it runs on the cheaper
        ideation_judge_llm at ideation_judge_reasoning_effort (default gpt-5.4-mini / low)
        instead of the expensive creative model.

        GPT-5 series: reasoning_effort from settings (judge tier)
        Older models: temperature=0.2
        """
        return Agent(
            config=self.agents_config["solution_evaluator"],
            llm=build_crew_llm(
                model=settings.ideation_judge_llm,
                temperature=0.2,  # Used for non-reasoning models only
                reasoning_effort=settings.ideation_judge_reasoning_effort,
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
            # build_crew_llm forwards reasoning_effort to the API for GPT-5 models
            # (a ChatOpenAI instance would have it dropped by CrewAI's create_llm).
            function_calling_llm=build_crew_llm(
                model=settings.function_calling_llm,
                reasoning_effort="minimal",  # Fast/cheap tool-arg synthesis
            ),
            verbose=True,
        )

    

    @agent
    def solution_refiner(self) -> Agent:
        """
        Agent for refining solutions with competitive insights (convergent REFINE tier).
        Structured enhancement, not divergent ideation — runs on ideation_refine_llm at
        ideation_refine_reasoning_effort (default gpt-5.2 / medium: keeps the full model
        because it writes user-facing copy, but drops off the creative tier's 'high').

        GPT-5 series: reasoning_effort from settings (refine tier)
        Older models: temperature=0.4
        """
        return Agent(
            config=self.agents_config["solution_refiner"],
            llm=build_crew_llm(
                model=settings.ideation_refine_llm,
                temperature=0.4,  # Used for non-reasoning models only
                reasoning_effort=settings.ideation_refine_reasoning_effort,
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
        return SafeTask(
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
        return SafeTask(
            config=self.tasks_config["diversity_filtering"],
            agent=self.solution_evaluator(),  # Low temp (0.2) for objective filtering
            # No CrewAI context: concepts arrive via the {pooled_concepts} input block
            # (pooled from N independent divergent samples, generated outside this crew).
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
        return SafeTask(
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
        return SafeTask(
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
        return SafeTask(
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

    def _convergent_crew(self, skip_selection: bool) -> Crew:
        """Crew for the CONVERGENT half only: filter → refine → (select).

        The divergent stage runs separately (multi-sample, pooled) and is injected via
        the {pooled_concepts} input, so this crew has no divergent task. Filter→refine→
        select still chain via CrewAI context.
        """
        # Build the agent list explicitly (self.agents is only populated by the @crew
        # method, which the multi-sample flow no longer calls). Each task already
        # carries its own agent; the Crew just needs the matching agent list.
        tasks = [self.diversity_filtering_task(), self.solution_refinement_task()]
        agents = [self.solution_evaluator(), self.solution_refiner()]
        if not skip_selection:
            tasks.append(self.solution_selection_task())
            agents.append(self.strategic_selector())
        return Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process_type="sequential",
            embedder={"provider": "openai", "config": {"model_name": "text-embedding-3-small"}},
        )

    def _divergent_fallback(self, inputs: dict) -> list:
        """Guarded fallback when the multi-sample pool is too small: run the single
        legacy CrewAI divergent task (SafeTask guardrail + retries) and return its
        concepts. Ensures the filter never receives an empty/degenerate pool."""
        logger.warning("[Divergent] pool too small — falling back to single guarded divergent task")
        crew = Crew(
            agents=[self.solution_ideator()],
            tasks=[self.divergent_exploration_task()],
            verbose=True,
            process_type="sequential",
            embedder={"provider": "openai", "config": {"model_name": "text-embedding-3-small"}},
        )
        out = crew.kickoff(inputs={**inputs, "lens_directive": ""})
        try:
            rcl = out.tasks_output[0].pydantic if getattr(out, "tasks_output", None) else None
            return list(rcl.concepts) if rcl else []
        except Exception as e:
            logger.error(f"[Divergent] fallback also failed: {e}")
            return []

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

            # Format existing ideas blacklist for prompt injection
            if self.existing_ideas:
                existing_ideas_blacklist = self._format_blacklist(compact=False)
                existing_ideas_blacklist_compact = self._format_blacklist(compact=True)
                logger.info(f"Injecting {len(self.existing_ideas)} existing ideas into blacklist prompt")
            else:
                existing_ideas_blacklist = "None (first generation — no previously generated ideas)"
                existing_ideas_blacklist_compact = existing_ideas_blacklist
            # Regeneration-only directive: actively re-approach the SAME pains from
            # different angles rather than merely avoiding prior ideas. Empty on first gen.
            regeneration_directive = self._format_regeneration_directive()

            crew_inputs = {
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
                "regeneration_directive": regeneration_directive,
                # Direct context injection (replaces RAG)
                "competitor_mentions": self._format_competitor_mentions(),
                "theme_categories": theme_categories_formatted,
            }

            # ── DIVERGENT: N independent samples → critic → pool/dedup ──
            n = max(1, settings.num_divergent_samples)
            logger.info(
                f"Executing Pipeline: {n}× independent Divergent → novelty critic → pool "
                f"→ Filter → Refinement{'' if skip_selection else ' → Selection'}..."
            )
            pooled, divergent_usages = self._generate_divergent_pool(crew_inputs)
            self._record_divergent_usage(divergent_usages)
            pooled = self._score_pool_novelty(pooled)            # independent critic (before dedup)
            pooled = self._pool_and_dedup_raw_concepts(pooled)   # dedup + clamp [6, cap]
            # Fail-open: if the pool is too small for the filter, use the guarded
            # single-call divergent task instead of feeding the filter a degenerate pool.
            if len(pooled) < 6:
                fb = self._divergent_fallback(crew_inputs)
                if len(fb) >= len(pooled):
                    pooled = self._pool_and_dedup_raw_concepts(fb) or fb
            if len(pooled) < 6:
                raise ValueError(
                    f"Divergent generation produced only {len(pooled)} concepts after pooling "
                    "and fallback — cannot proceed (need >= 6 for the diversity filter)."
                )
            raw_concepts = RawConceptList(
                concepts=pooled[:15],
                techniques_used=sorted({c.ideation_technique for c in pooled if c.ideation_technique}),
                pain_points_referenced=[],
            )
            logger.info(f"  Divergent pool: {len(raw_concepts.concepts)} concepts fed to filter")
            crew_inputs["pooled_concepts"] = self._format_pooled_concepts(raw_concepts.concepts)

            # ── CONVERGENT crew: filter → refine → (select) ──
            self._last_crew = self._convergent_crew(skip_selection)  # for usage_metrics
            crew_output = self._last_crew.kickoff(inputs=crew_inputs)

            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            min_expected = 2 if skip_selection else 3
            if len(task_outputs) < min_expected:
                raise ValueError(
                    f"Expected {min_expected} convergent task outputs, got {len(task_outputs)}. "
                    "Pipeline may have failed mid-execution."
                )

            # Convergent indices: [0]=filter, [1]=refine, (select is crew_output.pydantic)
            filtered_concepts = task_outputs[0].pydantic  # FilteredConceptList
            if filtered_concepts:
                logger.info(f"  Filter: kept {len(filtered_concepts.concepts)} unique concepts")
                if filtered_concepts.removed_concepts:
                    logger.info(f"  Removed {len(filtered_concepts.removed_concepts)} similar concepts")

            # Extract refinement (task index 1) - REQUIRED
            base_solutions = task_outputs[1].pydantic
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

            # Carry M/D/J structural tags from the filtered concepts onto the refined
            # solutions (refinement drops them). Match on whitespace-normalized name
            # ("BPC Lot Mapper" -> "bpclotmapper" == "BPCLotMapper"). Persisted so the
            # regeneration dedup can catch reworded structural duplicates.
            if filtered_concepts and filtered_concepts.concepts:
                def _norm(n: str) -> str:
                    return "".join((n or "").lower().split())
                tag_lookup = {
                    _norm(c.concept_name): (
                        c.mechanism_tag, c.data_source_tag, c.journey_tag,
                        c.obviousness_score,
                    )
                    for c in filtered_concepts.concepts
                }
                for sol in refined_solutions.solution_ideas:
                    tags = tag_lookup.get(_norm(getattr(sol, "solution_name", "")))
                    if tags:
                        sol.mechanism_tag, sol.data_source_tag, sol.journey_tag = tags[:3]
                        # Carry the independent obviousness score (skip the -1.0 sentinel).
                        if tags[3] is not None and tags[3] >= 0:
                            sol.obviousness_score = tags[3]

            # Post-crew pain-coverage enforcement (deterministic, never crashes):
            # restore coverage of high-severity on-niche pains the diversity filter
            # may have dropped, by re-injecting the best-covering divergent concept;
            # otherwise record a caveat. Coverage outranks structural spread.
            try:
                from ..utils.validation.crew_guardrails import enforce_pain_coverage
                self.coverage_caveats = enforce_pain_coverage(
                    refined_solutions.solution_ideas,
                    raw_concepts.concepts if raw_concepts else [],
                    self.pain_point_analysis.pain_points,
                    synthesize_fn=self._refine_single_concept,  # full refinement, not a stub
                )
            except Exception as e:
                logger.warning(f"Pain-coverage enforcement skipped: {e}")
                self.coverage_caveats = []

            # Post-crew BOLD SLOT: guarantee >=1 genuinely novel idea even at lower
            # market-fit (deterministic, never crashes). Re-injects the lowest-obviousness
            # pooled concept if the final set has no bold idea.
            try:
                self._enforce_bold_slot(refined_solutions.solution_ideas, raw_concepts)
            except Exception as e:
                logger.warning(f"Bold-slot enforcement skipped: {e}")

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
