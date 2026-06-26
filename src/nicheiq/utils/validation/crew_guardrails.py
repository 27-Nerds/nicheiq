"""
Crew Guardrails - Validation functions for CrewAI task outputs.

NOTE: CrewAI 1.8.1 intentionally sets task_output.pydantic = None when guardrails exist.
Most validation has been migrated to Pydantic model validators (the recommended approach).
Only complex cross-solution comparisons remain here as guardrails.

Guardrail Return Convention:
- (True, raw_string) - Validation passed, return a string for CrewAI to re-parse
- (False, error_message) - Validation failed, CrewAI will retry up to guardrail_max_retries times
"""

import json
import re
from typing import Any

from loguru import logger

from ...models.competitor import CompetitiveAnalysisResult
from ...models.data_source import DataImplementationPlan, SourceEvaluationReport
from ...models.landing_page import AnimatedHTMLResult, HTMLPageResult, QAReviewResult
from ...models.pain_point import ContentCategorizationReport
from ...models.research_state import (
    AudienceMappingLLMResult,
    PricingStrategyResult,
    TrafficMonetizationResult,
    TrendNarrativeOutput,
)
from ...models.seo_strategy import (
    CategoryLightResult,
    ContentStrategyResultLight,
    GeographicLightResult,
    ImplementationPlanResult,
    KeywordSummaryResult,
    StrategicLightResult,
)
from ...models.solution_idea import (
    CompetitiveEnhancements,
    IdeaGenerationResult,
    RawConceptList,
)
from ...models.solution_refinement import SolutionRefinement
from ...models.solution_selection import SolutionSelection
from ...models.technical_blueprint import SiteStructure, UserFlowsSection
from ..parsing.json_extractor import clean_llm_response, extract_json_object_from_text


def _guardrail_success_payload(task_output, parsed_result: Any | None = None) -> str:
    """Return a string payload that CrewAI can store in TaskOutput.raw."""
    raw = getattr(task_output, "raw", None)

    if isinstance(raw, str):
        # If the model wrapped the JSON in a reasoning preamble ("Thought: ...{...}"),
        # the raw string won't parse when CrewAI materializes .pydantic downstream.
        # When the guardrail already produced a validated object, hand CrewAI clean
        # serialized JSON instead. Gated on "raw is not already clean JSON", so this
        # is a NO-OP for well-behaved models (raw returned unchanged).
        if parsed_result is not None and hasattr(parsed_result, "model_dump_json"):
            if not clean_llm_response(raw).lstrip().startswith("{"):
                logger.info("Guardrail payload: normalizing prose-wrapped output to clean JSON")
                return parsed_result.model_dump_json()
        return raw

    payload = raw if raw is not None else parsed_result
    if payload is None:
        return ""

    if hasattr(payload, "model_dump_json"):
        return payload.model_dump_json()

    if isinstance(payload, (dict, list, tuple, int, float, bool)):
        return json.dumps(payload, default=str)

    logger.warning(
        f"Guardrail success payload was {type(payload).__name__}, not str; coercing to string"
    )
    return str(payload)


def validate_diversity(
    task_output, allowed_project_types: list[str] | None = None,
    nudge_diversity: bool = False,
) -> tuple[bool, Any]:
    """
    Guardrail for solution_refinement_task to enforce diversity.

    NOTE: This guardrail must remain (not moved to Pydantic) because it performs
    cross-solution comparisons that cannot be expressed as single-field validators.

    CrewAI 1.8.1 Compatibility: When guardrails exist, pydantic=None by design.
    We must parse .raw directly and return (True, raw_string) on success.

    Adaptive rules based on allowed_project_types:
    - If multiple types allowed: require at least 2 different project_types
    - If single type allowed: require diversity WITHIN that type (different data sources)
    - Always: check for duplicate value propositions via similarity detection

    Args:
        task_output: CrewAI task output object
        allowed_project_types: List of allowed project types from crew init

    Returns:
        tuple[bool, Any]: (success, result_or_error)
    """
    try:
        # CrewAI 1.8.1: When guardrails exist, pydantic is intentionally None
        # Try pydantic first, then fall back to parsing .raw
        result = task_output.pydantic
        if result is None:
            # CrewAI 1.8.1 behavior: parse from .raw
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Solution refinement returned empty output (no pydantic or raw)")

            try:
                # Clean LLM response to remove XML-like tags that may confuse JSON parsing
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = IdeaGenerationResult.model_validate(raw_json)
                logger.debug("Diversity guardrail: Parsed IdeaGenerationResult from .raw")
            except json.JSONDecodeError as e:
                # Recover JSON embedded in a reasoning preamble ("Thought: ...{...}").
                extracted = extract_json_object_from_text(task_output.raw)
                if extracted is not None:
                    try:
                        result = IdeaGenerationResult.model_validate(extracted)
                        logger.info("Diversity guardrail: recovered IdeaGenerationResult from prose-wrapped output")
                    except Exception as ve:
                        logger.warning(f"[DEBUG] extracted JSON failed validation: {ve}")
                        return (False, f"Failed to parse IdeaGenerationResult: {ve}")
                else:
                    logger.warning(f"[DEBUG] Failed to parse JSON from .raw: {e}")
                    logger.warning(f"[DEBUG] .raw first 500 chars: {task_output.raw[:500]}")
                    return (False, f"Invalid JSON in task output: {e}")
            except Exception as e:
                logger.warning(f"[DEBUG] Failed to validate IdeaGenerationResult: {e}")
                return (False, f"Failed to parse IdeaGenerationResult: {e}")

        if not isinstance(result, IdeaGenerationResult):
            return (
                False,
                f"Invalid output type: expected IdeaGenerationResult, got {type(result)}",
            )

        ideas = result.solution_ideas
        if len(ideas) < 3:
            return (False, f"Need at least 3 solutions, got {len(ideas)}")

        # Get allowed project types
        allowed_types = allowed_project_types or []

        # Rule 1: If multiple types allowed, nudge toward type diversity.
        # SELF-LIMITING: on the FIRST guardrail invocation we may fail once to
        # nudge a regeneration toward >=2 project types (the all-SEO-hub monotony
        # fix); on any subsequent invocation we only warn and proceed. This can
        # never loop/crash (allowing a type doesn't mean the niche suits it).
        if len(allowed_types) >= 2:
            used_types = set(idea.project_type for idea in ideas if idea.project_type)
            if len(used_types) < 2:
                if nudge_diversity:
                    return (
                        False,
                        f"Project-type monotony: {len(allowed_types)} types allowed "
                        f"({allowed_types}) but only {used_types} used across "
                        f"{len(ideas)} solutions. Regenerate so the set spans at least 2 "
                        f"distinct project_types. A calculator and a content-hub are the "
                        f"SAME architecture — vary the product mechanism, don't return "
                        f"variations of one SEO page-factory."
                    )
                logger.warning(
                    f"Low project type diversity: {len(allowed_types)} types allowed "
                    f"but only {used_types} used. Proceeding (nudge already spent)."
                )
            else:
                logger.info(f"✓ Project type diversity check passed: {used_types}")

        # Rule 2: If single type allowed, require diversity WITHIN that type
        elif len(allowed_types) == 1:
            # Check data sources diversity (advisory only — single-type niches
            # naturally share data sources; the pairwise similarity check in
            # Rule 3 catches genuinely duplicate solutions)
            data_sources_list = [set(idea.data_sources or []) for idea in ideas]
            unique_sources = len(
                set(tuple(sorted(ds)) for ds in data_sources_list if ds)
            )
            if unique_sources < len(ideas) * 0.5:
                logger.warning(
                    f"Low data source diversity within {allowed_types[0]}: "
                    f"Only {unique_sources}/{len(ideas)} have unique data sources. "
                    f"Proceeding — pairwise similarity check will catch true duplicates."
                )
            else:
                logger.info(
                    f"✓ Within-type diversity check passed: {unique_sources} unique data source combinations"
                )

        # NOTE: info-products (directory/aggregator/comparison) are intentionally NOT penalized —
        # they are first-class, often-best monetizable side-project outcomes (programmatic SEO).
        # Variety across the pool is driven by the pain-partition + the type-spread nudge above
        # (Rule 1), which is type-NEUTRAL; we do not force away from info-products.

        # Rule 3: Always check for duplicate value propositions
        for i, idea_a in enumerate(ideas):
            for idea_b in ideas[i + 1 :]:
                if detect_similarity(idea_a, idea_b):
                    return (
                        False,
                        f"Similarity violation: '{idea_a.solution_name}' too similar to '{idea_b.solution_name}'. "
                        f"These solutions have overlapping value propositions or mechanisms. "
                        f"Generate more distinct solutions with different approaches.",
                    )

        logger.info(f"✓ Diversity guardrail passed: {len(ideas)} unique solutions")
        # CrewAI 1.8.1: Return raw string for CrewAI to re-parse
        return (True, _guardrail_success_payload(task_output, result))

    except Exception as e:
        return (False, f"Diversity validation error: {str(e)}")


def _fuzzy_set_overlap(items_a, items_b) -> float:
    """Stem-token Jaccard-style overlap between two free-text string lists.

    Tokenizes + stems every entry, then computes overlap / min-size. Exact set
    equality was trivially defeated by rewording ('county court records' vs
    'court filings data') — the precise failure mode guardrail retries exploit.
    """
    from ..text_stemmer import stem_tokens

    tokens_a = stem_tokens({t for item in items_a for t in str(item).lower().split()})
    tokens_b = stem_tokens({t for item in items_b for t in str(item).lower().split()})
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def detect_similarity(idea_a, idea_b) -> bool:
    """
    Detect if two solution ideas are too similar.

    Uses a multi-signal approach: at least 2 of 3 signals must fire to flag a
    pair as "too similar" — OR a single overwhelming value-proposition overlap
    (>80%), which is a duplicate regardless of cosmetic differences elsewhere.

    Signals (1 and 3 use fuzzy stem-token overlap, not exact set equality —
    an LLM retry can trivially reword a string without changing the structure):
    1. Data source overlap ≥ 60%
    2. Value proposition keyword overlap > 60% (alone fails at > 80%)
    3. Target persona overlap ≥ 60%

    Returns:
        bool: True if ideas are too similar
    """
    similarity_signals = 0

    # Signal 1: Overlapping data sources = likely similar mechanism (fuzzy)
    sources_a = idea_a.data_sources or []
    sources_b = idea_b.data_sources or []
    if sources_a and sources_b and _fuzzy_set_overlap(sources_a, sources_b) >= 0.6:
        logger.debug(f"Similarity signal: Overlapping data sources ({sources_a} ~ {sources_b})")
        similarity_signals += 1

    # Signal 2: Value proposition keyword overlap
    if idea_a.value_proposition and idea_b.value_proposition:
        # Remove common stop words for better comparison
        stop_words = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "that",
            "which",
            "who",
            "whom",
            "this",
            "these",
            "those",
            "it",
            "its",
            "their",
            "them",
            "they",
            "we",
            "our",
            "you",
            "your",
        }

        from ..text_stemmer import stem_tokens
        vp_a = stem_tokens(set(idea_a.value_proposition.lower().split()) - stop_words)
        vp_b = stem_tokens(set(idea_b.value_proposition.lower().split()) - stop_words)

        if vp_a and vp_b:
            overlap = len(vp_a & vp_b) / min(len(vp_a), len(vp_b))
            if overlap > 0.8:
                # Single-strong-signal failure: a near-identical value prop is a
                # duplicate no matter how the other fields were reworded
                logger.debug(
                    f"Similarity detected between '{idea_a.solution_name}' and "
                    f"'{idea_b.solution_name}': {overlap:.0%} value proposition overlap (single strong signal)"
                )
                return True
            if overlap > 0.6:  # >60% overlap in value prop
                logger.debug(
                    f"Similarity signal: {overlap:.0%} value proposition overlap"
                )
                similarity_signals += 1

    # Signal 3: Overlapping target personas (fuzzy)
    if idea_a.target_personas and idea_b.target_personas:
        if _fuzzy_set_overlap(idea_a.target_personas, idea_b.target_personas) >= 0.6:
            logger.debug("Similarity signal: Overlapping target personas")
            similarity_signals += 1

    if similarity_signals >= 2:
        logger.debug(
            f"Similarity detected between '{idea_a.solution_name}' and "
            f"'{idea_b.solution_name}': {similarity_signals}/3 signals"
        )
        return True

    return False


def detect_catalog_duplicate(new_solution, existing_idea: dict) -> bool:
    """Structural duplicate check between a regenerated solution and an existing
    catalog idea (plain dict from the backend: name, description, and — when
    available — value_proposition and target_personas).

    Replaces the exact-name-only worker filter: renamed structural duplicates
    passed every previous gate (the within-batch guardrail never compares
    against the catalog, and the backend insert dedup is exact-name too).

    Signals:
    - Fuzzy name match (≥ 0.85 sequence ratio)
    - Value-proposition stem-token overlap > 0.8 (falls back to description
      text when value_proposition is absent on either side)
    - Value-prop overlap > 0.6 AND persona overlap ≥ 0.6
    """
    from difflib import SequenceMatcher

    new_name = (getattr(new_solution, 'solution_name', '') or '').lower().strip()
    existing_name = (existing_idea.get('name') or '').lower().strip()
    if new_name and existing_name:
        if new_name == existing_name or SequenceMatcher(None, new_name, existing_name).ratio() >= 0.85:
            return True

    # Structural duplicate: same mechanism + data + journey, even when the idea was
    # REWORDED (text-based signals below miss those). Only fires when BOTH sides
    # carry M/D/J tags, so callers passing legacy/tag-less ideas are unaffected.
    new_m = getattr(new_solution, 'mechanism_tag', None)
    new_d = getattr(new_solution, 'data_source_tag', None)
    new_j = getattr(new_solution, 'journey_tag', None)
    ex_m = existing_idea.get('mechanism_tag')
    ex_d = existing_idea.get('data_source_tag')
    ex_j = existing_idea.get('journey_tag')
    if (new_m or new_d or new_j) and (ex_m or ex_d or ex_j):
        matched = sum((
            _tags_match(new_m, ex_m),
            _tags_match(new_d, ex_d),
            _tags_match(new_j, ex_j),
        ))
        if matched >= 2:
            return True

    new_vp = (
        getattr(new_solution, 'value_proposition', None)
        or getattr(new_solution, 'description', None)
        or ''
    )
    existing_vp = existing_idea.get('value_proposition') or existing_idea.get('description') or ''
    vp_overlap = _fuzzy_set_overlap([new_vp], [existing_vp]) if new_vp and existing_vp else 0.0
    if vp_overlap > 0.8:
        return True

    new_personas = getattr(new_solution, 'target_personas', None) or []
    existing_personas = existing_idea.get('target_personas') or []
    if vp_overlap > 0.6 and new_personas and existing_personas:
        if _fuzzy_set_overlap(new_personas, existing_personas) >= 0.6:
            return True

    return False


# ── Post-crew pain-coverage enforcement (deterministic; never crashes) ──────────
# High-severity on-niche pains must each be addressed by >=1 final solution. The
# old behaviour let the diversity filter delete the only on-niche idea covering a
# pain. This runs AFTER the crew (not as a guardrail) so it can RESTORE coverage
# by re-injecting the best-covering divergent concept, degrading to a caveat when
# no concept covers the pain — it can never loop or raise.
_COVERAGE_SEVERITY_FLOOR = 0.6
_COVERAGE_MENTION_FLOOR = 8
_COVERAGE_MAX_PAINS = 4
_COVERAGE_MATCH_THRESHOLD = 0.5   # pain considered covered by a solution
_REINJECT_MATCH_THRESHOLD = 0.34  # min concept↔pain overlap to re-inject


def _pain_terms(pain) -> list[str]:
    terms = [getattr(pain, "title", "") or ""]
    terms.extend(getattr(pain, "categories", None) or [])
    return [t for t in terms if t]


def _idea_blob_terms(idea) -> list[str]:
    parts = [
        getattr(idea, "solution_name", "") or "",
        getattr(idea, "value_proposition", "") or "",
        getattr(idea, "headline", "") or "",
    ]
    parts.extend(getattr(idea, "pain_points_addressed", None) or [])
    return [p for p in parts if p]


def _concept_blob_terms(concept) -> list[str]:
    parts = [
        getattr(concept, "concept_name", "") or "",
        getattr(concept, "one_liner", "") or "",
        getattr(concept, "why_non_obvious", "") or "",
    ]
    parts.extend(getattr(concept, "target_keywords", None) or [])
    return [p for p in parts if p]


def _high_severity_pains(pain_points: list) -> list:
    eligible = [
        p for p in (pain_points or [])
        if (getattr(p, "severity_score", 0) or 0) >= _COVERAGE_SEVERITY_FLOOR
        or (getattr(p, "mention_count", 0) or 0) >= _COVERAGE_MENTION_FLOOR
    ]
    eligible.sort(
        key=lambda p: (getattr(p, "severity_score", 0) or 0, getattr(p, "mention_count", 0) or 0),
        reverse=True,
    )
    return eligible[:_COVERAGE_MAX_PAINS]


def _synthesize_idea_from_concept(concept, pain):
    """Build a minimal-but-valid BaseSolutionIdea from a divergent concept.

    Conservative defaults; flags itself as a coverage re-injection so the report
    can treat it appropriately. Never invents scores beyond a neutral midpoint.
    """
    from ...models.solution_idea import BaseSolutionIdea

    one_liner = (getattr(concept, "one_liner", "") or getattr(concept, "concept_name", "")).strip()
    features = list(getattr(concept, "target_keywords", None) or [])[:3] or ["Core MVP feature"]
    diff = getattr(concept, "why_non_obvious", None)
    # Clean display fields so a re-injected idea renders completely (not blank "--").
    short_desc = (one_liner[:175] + "…") if len(one_liner) > 176 else one_liner
    headline = " ".join(one_liner.split()[:12]) or getattr(concept, "concept_name", "")
    obv = getattr(concept, "obviousness_score", -1.0)
    novelty = round(max(0.0, min(1.0, 1.0 - obv)), 2) if (obv is not None and obv >= 0) else 0.5
    return BaseSolutionIdea(
        solution_name=getattr(concept, "concept_name", "Untitled concept"),
        headline=headline,
        short_description=short_desc,
        description=(
            f"{one_liner} (Re-injected to keep coverage of the high-severity pain "
            f"\"{getattr(pain, 'title', '')}\"; expand before shipping.)"
        ),
        value_proposition=one_liner,
        pain_points_addressed=[getattr(pain, "title", "") or "high-severity pain"],
        core_features=features,
        target_personas=["Primary niche audience"],
        differentiation_factors=[diff] if diff else None,
        project_type=getattr(concept, "project_type", None),
        organic_discovery_queries=list(getattr(concept, "target_keywords", None) or []) or None,
        # Neutral placeholder scores so the card isn't blank; the description flags it
        # as a re-injected concept to refine. Novelty derived from the concept's
        # independent obviousness when available.
        market_fit_score=0.5,
        technical_feasibility_score=0.5,
        seo_scalability_score=0.5,
        solo_dev_feasibility=0.5,
        novelty_score=novelty,
        # Carry the concept's M/D/J tags so the regeneration ("generate more") dedup
        # can still catch a reworded duplicate of this re-injected idea later.
        mechanism_tag=getattr(concept, "mechanism_tag", None),
        data_source_tag=getattr(concept, "data_source_tag", None),
        journey_tag=getattr(concept, "journey_tag", None),
        # Independent obviousness signal (skip the -1.0 sentinel) for the Originality UI.
        obviousness_score=obv if (obv is not None and obv >= 0) else None,
    )


def enforce_pain_coverage(
    final_ideas: list, raw_concepts: list, pain_points: list, synthesize_fn=None
) -> list:
    """Ensure every high-severity on-niche pain is covered by a final solution.

    Mutates `final_ideas` in place (appends re-injected concepts) and returns a
    list of human-readable caveat strings for pains that could not be covered.
    Pure/deterministic; any internal error is swallowed (coverage is best-effort).

    `synthesize_fn(concept, pain) -> BaseSolutionIdea` builds the re-injected idea.
    Defaults to the lightweight stub; the crew passes a full LLM refiner so re-injected
    ideas are as complete as the rest.
    """
    synthesize_fn = synthesize_fn or _synthesize_idea_from_concept
    caveats: list[str] = []
    try:
        pains = _high_severity_pains(pain_points)
        if not pains:
            return caveats
        existing_names = {
            (getattr(i, "solution_name", "") or "").lower().strip() for i in final_ideas
        }
        for pain in pains:
            pterms = _pain_terms(pain)
            if not pterms:
                continue
            covered = any(
                _fuzzy_set_overlap(pterms, _idea_blob_terms(i)) >= _COVERAGE_MATCH_THRESHOLD
                for i in final_ideas
            )
            if covered:
                continue
            # Find the best divergent concept that covers this pain and is new.
            best, best_score = None, 0.0
            for c in raw_concepts or []:
                cname = (getattr(c, "concept_name", "") or "").lower().strip()
                if cname in existing_names:
                    continue
                score = _fuzzy_set_overlap(pterms, _concept_blob_terms(c))
                if score > best_score:
                    best, best_score = c, score
            if best is not None and best_score >= _REINJECT_MATCH_THRESHOLD:
                synthesized = synthesize_fn(best, pain)
                final_ideas.append(synthesized)
                existing_names.add((synthesized.solution_name or "").lower().strip())
                logger.warning(
                    f"[COVERAGE] Re-injected '{synthesized.solution_name}' to cover "
                    f"high-severity pain '{getattr(pain, 'title', '')}' "
                    f"(overlap={best_score:.2f})"
                )
            else:
                msg = (
                    f"High-severity pain '{getattr(pain, 'title', '')}' is not addressed "
                    f"by any generated solution."
                )
                caveats.append(msg)
                logger.warning(f"[COVERAGE] {msg}")
    except Exception as e:  # never let coverage enforcement break the run
        logger.warning(f"[COVERAGE] enforcement skipped due to error: {e}")
    return caveats


def create_diversity_guardrail(allowed_project_types: list[str] | None = None):
    """
    Factory function to create a diversity guardrail with specific project types.

    Args:
        allowed_project_types: List of allowed project types

    Returns:
        Guardrail function with project types bound
    """

    # Mutable cell so the closure can track its own invocation count across
    # CrewAI retries (the closure can't read CrewAI's retry counter). This makes
    # the project-type nudge SELF-LIMITING: fail at most once, then always pass.
    state = {"calls": 0}

    def guardrail(task_output) -> tuple[bool, Any]:
        state["calls"] += 1
        nudge = state["calls"] == 1
        return validate_diversity(task_output, allowed_project_types, nudge_diversity=nudge)

    return guardrail


def validate_competitive_analysis(task_output) -> tuple[bool, Any]:
    """
    Guardrail for competitive_analysis_task to detect truncated JSON output.

    CrewAI 1.8.1 Compatibility: When guardrails exist, pydantic=None by design.
    Must parse from .raw and return (True, raw_string) on success.

    Validates:
    1. JSON is complete and parseable (catches truncation)
    2. Has solution_landscapes list with at least 1 entry
    3. Each landscape has minimum required competitors and gaps
    4. top_opportunities and strategic_recommendations present

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        # CrewAI 1.8.1: When guardrails exist, pydantic is intentionally None
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Competitive analysis returned empty output (no pydantic or raw)")

            try:
                # Clean and parse JSON from raw output
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = CompetitiveAnalysisResult.model_validate(raw_json)
                logger.debug("Competitive analysis guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                # This catches truncation errors like "EOF while parsing"
                logger.warning(f"Truncated JSON detected in competitive analysis: {e}")
                return (
                    False,
                    f"Output appears truncated - JSON parse error at line {e.lineno}: {e.msg}. "
                    "Reduce output size: limit to 3-4 competitors per solution with shorter descriptions."
                )
            except Exception as e:
                logger.warning(f"Failed to validate CompetitiveAnalysisResult: {e}")
                return (False, f"Failed to parse CompetitiveAnalysisResult: {e}")

        if not isinstance(result, CompetitiveAnalysisResult):
            return (
                False,
                f"Invalid type: expected CompetitiveAnalysisResult, got {type(result)}"
            )

        # Validate structure completeness
        if len(result.solution_landscapes) < 1:
            return (False, "Need at least 1 solution landscape in solution_landscapes")

        for landscape in result.solution_landscapes:
            if len(landscape.competitors) == 0:
                logger.warning(f"No competitors found for '{landscape.solution_name}' - may be emerging niche or search tool issue")
            elif len(landscape.competitors) < 2:
                logger.info(f"Limited competitors ({len(landscape.competitors)}) for '{landscape.solution_name}'")
            # Continue validation - don't fail on low competitor count
            if len(landscape.market_gaps) < 2:
                return (
                    False,
                    f"Landscape '{landscape.solution_name}' needs at least 2 market gaps, got {len(landscape.market_gaps)}"
                )

        if not result.top_opportunities:
            return (False, "Missing top_opportunities list - provide 3-5 differentiation opportunities")

        if not result.strategic_recommendations or len(result.strategic_recommendations) < 50:
            return (
                False,
                f"strategic_recommendations too short ({len(result.strategic_recommendations or '')} chars, minimum 50)"
            )

        logger.info(f"✓ Competitive analysis guardrail passed: {len(result.solution_landscapes)} landscapes")
        # CrewAI 1.8.1: Return raw string for CrewAI to re-parse
        return (True, _guardrail_success_payload(task_output, result))

    except Exception as e:
        return (False, f"Competitive analysis validation error: {str(e)}")


def validate_competitive_enhancements(task_output) -> tuple[bool, Any]:
    """
    Guardrail for competitive_refinement_task to handle JSON errors.

    This task's overall_competitive_insights field (2-3 paragraphs) often contains
    unescaped literal newlines that break JSON parsing. The guardrail:
    1. Uses _parse_pydantic_from_task_output which calls _fix_common_json_errors
    2. Provides specific error message about newline escaping
    3. Validates structure completeness
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, CompetitiveEnhancements, "Competitive refinement"
    )
    if error:
        return (
            False,
            f"{error} The overall_competitive_insights field likely contains "
            "unescaped newlines. Use \\n for paragraph breaks, not literal newlines."
        )

    if not result.solution_enhancements:
        return (False, "Need at least 1 solution_enhancement.")

    for enh in result.solution_enhancements:
        if not enh.solution_name or not enh.solution_name.strip():
            return (False, "Each enhancement needs a solution_name.")
        if not enh.new_core_features:
            return (False, f"Enhancement '{enh.solution_name}' needs new_core_features.")
        if not enh.new_differentiation_factors:
            return (False, f"Enhancement '{enh.solution_name}' needs new_differentiation_factors.")

    if len(result.overall_competitive_insights or '') < 100:
        return (False, "overall_competitive_insights too short (min 100 chars).")

    logger.info(f"[OK] Competitive enhancements: {len(result.solution_enhancements)} solutions")
    return (True, _guardrail_success_payload(task_output, result))


# ========================================
# SEO KEYWORD ANALYSIS GUARDRAILS
# ========================================
# These guardrails catch JSON truncation and repetition loop issues in keyword analysis tasks


def validate_category_tier_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for analyze_category_tier_parallel_task to detect truncated/malformed JSON.

    Catches issues like:
    - JSON truncation from token limits
    - Infinite repetition loops causing invalid JSON
    - Missing required fields

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Category tier analysis returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = CategoryLightResult.model_validate(raw_json)
                logger.debug("Category tier guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                # Detect repetition loop pattern
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED - Output contains repeated identical content. "
                        "Generate DIVERSE category groups with UNIQUE keywords. "
                        "Each category must have DIFFERENT keywords - no duplicates allowed."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output size: create 8-12 category groups max with 5-10 keywords each."
                )
            except Exception as e:
                return (False, f"Failed to parse CategoryLightResult: {e}")

        if not isinstance(result, CategoryLightResult):
            return (False, f"Invalid type: expected CategoryLightResult, got {type(result)}")

        # Validate structure
        if not result.tier_4_category_groups or len(result.tier_4_category_groups) < 1:
            return (
                False,
                f"Need at least 1 category group, got {len(result.tier_4_category_groups or [])}. "
                "Create meaningful thematic groups from the keywords. "
                "Do not put all keywords in a single category - find natural themes."
            )

        # Check for duplicate keywords across groups (sign of repetition issue)
        all_keywords = []
        for group in result.tier_4_category_groups:
            # CategoryLightEntry has keyword_name field
            all_keywords.extend(kw.keyword_name.lower().strip() for kw in group.keywords)

        unique_keywords = set(all_keywords)
        if len(unique_keywords) < len(all_keywords) * 0.7:  # >30% duplicates
            duplicate_count = len(all_keywords) - len(unique_keywords)
            return (
                False,
                f"Too many duplicate keywords across groups ({duplicate_count} duplicates). "
                "IMPORTANT: Each keyword must appear in ONLY ONE category group. "
                "Review your output and remove keywords that appear in multiple categories."
            )

        logger.info(f"✓ Category tier guardrail passed: {len(result.tier_4_category_groups)} groups")
        return (True, _guardrail_success_payload(task_output, result))

    except Exception as e:
        return (False, f"Category tier validation error: {str(e)}")


def validate_geographic_tier_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for analyze_geographic_tier_parallel_task to detect truncated/malformed JSON.

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Geographic tier analysis returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = GeographicLightResult.model_validate(raw_json)
                logger.debug("Geographic tier guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED - Output contains repeated content. "
                        "Generate UNIQUE geographic regions with DISTINCT location-based keywords."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output: 5-10 geographic regions with 3-8 keywords each."
                )
            except Exception as e:
                return (False, f"Failed to parse GeographicLightResult: {e}")

        if not isinstance(result, GeographicLightResult):
            return (False, f"Invalid type: expected GeographicLightResult, got {type(result)}")

        # Geographic groups are optional (niche may not have location keywords)
        if result.tier_3_geographic_groups:
            # Check for duplicate keywords
            all_keywords = []
            for group in result.tier_3_geographic_groups:
                # GeographicLightEntry has keyword field
                all_keywords.extend(kw.keyword.lower().strip() for kw in group.keywords)

            unique_keywords = set(all_keywords)
            if len(all_keywords) > 5 and len(unique_keywords) < len(all_keywords) * 0.8:
                return (
                    False,
                    "Too many duplicate keywords in geographic groups. "
                    "Each location keyword should appear in only ONE region."
                )

        logger.info(f"✓ Geographic tier guardrail passed: {len(result.tier_3_geographic_groups or [])} regions")
        return (True, _guardrail_success_payload(task_output, result))

    except Exception as e:
        return (False, f"Geographic tier validation error: {str(e)}")


def validate_strategic_tier_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for analyze_strategic_tier_task to detect truncated/malformed JSON.

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Strategic tier analysis returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = StrategicLightResult.model_validate(raw_json)
                logger.debug("Strategic tier guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED - Output contains repeated content. "
                        "Analyze each keyword ONCE and provide UNIQUE strategic recommendations."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output: focus on top 20-30 strategic keywords with concise analysis."
                )
            except Exception as e:
                return (False, f"Failed to parse StrategicLightResult: {e}")

        if not isinstance(result, StrategicLightResult):
            return (False, f"Invalid type: expected StrategicLightResult, got {type(result)}")

        # Strategic keywords are filtered by opp_score 50-100, may be empty
        logger.info(f"✓ Strategic tier guardrail passed: {len(result.tier_2_keywords or [])} keywords")
        return (True, _guardrail_success_payload(task_output, result))

    except Exception as e:
        return (False, f"Strategic tier validation error: {str(e)}")


def _detect_repetition_pattern(text: str, min_repetitions: int = 3) -> bool:
    """
    Detect if text contains suspicious repetition patterns indicating an LLM loop.

    Looks for:
    - Same keyword appearing 3+ times in sequence
    - Identical JSON object patterns repeated

    Args:
        text: Raw output text to analyze
        min_repetitions: Minimum repetitions to trigger detection

    Returns:
        bool: True if repetition pattern detected
    """
    if not text or len(text) < 100:
        return False

    # Split into lines and look for repeated content
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    if len(lines) < min_repetitions * 2:
        return False

    # Check for consecutive identical lines (strong signal)
    consecutive_count = 1
    for i in range(1, len(lines)):
        if lines[i] == lines[i - 1] and len(lines[i]) > 20:
            consecutive_count += 1
            if consecutive_count >= min_repetitions:
                logger.warning(f"Repetition detected: '{lines[i][:50]}...' repeated {consecutive_count}x")
                return True
        else:
            consecutive_count = 1

    # Check for repeated JSON-like patterns
    # Look for patterns like '"keyword": "same value"' appearing multiple times
    import re
    keyword_pattern = re.findall(r'"keyword":\s*"([^"]+)"', text, re.IGNORECASE)
    if keyword_pattern:
        from collections import Counter
        keyword_counts = Counter(keyword_pattern)
        for keyword, count in keyword_counts.most_common(3):
            if count >= min_repetitions * 2:  # Same keyword appearing many times
                logger.warning(f"Repetition detected: keyword '{keyword}' appears {count} times")
                return True

    return False


# ========================================
# TASK 5: IMPLEMENTATION GUIDE GUARDRAIL (CRITICAL)
# ========================================
# Validates deeply nested JSON with JSON-LD code - highest risk for truncation/repetition


def _detect_template_variables(text: str) -> list[str]:
    """
    Detect placeholder template variables in text.

    Catches patterns like:
    - [solution_name], [city], [keyword]
    - {variable}, {placeholder}
    - {{mustache_style}}

    Args:
        text: Text to scan for template variables

    Returns:
        List of detected template patterns
    """
    if not text:
        return []

    import re

    patterns = []

    # [bracket] placeholders (but not JSON arrays like ["item"])
    bracket_matches = re.findall(r'\[([a-z_]+(?:\s+[a-z_]+)*)\]', text, re.IGNORECASE)
    for match in bracket_matches:
        # Skip if it looks like a valid JSON array content
        if match.lower() not in ['example', 'optional', 'required']:
            patterns.append(f"[{match}]")

    # {brace} placeholders (but not JSON objects)
    brace_matches = re.findall(r'\{([a-z_]+)\}', text, re.IGNORECASE)
    for match in brace_matches:
        patterns.append(f"{{{match}}}")

    # {{mustache}} placeholders
    mustache_matches = re.findall(r'\{\{([^}]+)\}\}', text)
    for match in mustache_matches:
        patterns.append(f"{{{{{match}}}}}")

    return patterns


def _validate_json_ld(code: str) -> tuple[bool, str]:
    """
    Validate that JSON-LD code is valid JSON.

    Args:
        code: JSON-LD code string to validate

    Returns:
        tuple[bool, str]: (is_valid, error_message_or_empty)
    """
    if not code or not code.strip():
        return (False, "Empty JSON-LD code")

    try:
        parsed = json.loads(code)

        # Check for @context (required for JSON-LD)
        if isinstance(parsed, dict) and '@context' not in parsed:
            return (False, "Missing @context in JSON-LD")

        return (True, "")
    except json.JSONDecodeError as e:
        return (False, f"Invalid JSON at line {e.lineno}: {e.msg}")


# validate_implementation_guide_output and validate_implementation_guide_light_output
# removed - Task 5 deleted, technical SEO is now in Task 2's technical_seo_recommendations


def _has_unquoted_keys(raw: str) -> bool:
    """Detect unquoted JSON keys like { key: value } instead of { "key": value }."""
    # Pattern: opening brace or comma, whitespace, then word without quotes before colon
    # Matches: { cluster_name: or , primary_keyword:
    return bool(re.search(r'[{,]\s*[a-zA-Z_][a-zA-Z0-9_]*\s*:', raw))


# ========================================
# TASK 2: CONTENT STRATEGY GUARDRAIL (HIGH)
# ========================================


def validate_content_strategy_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for develop_content_technical_strategy_task (Task 2 - HIGH).

    Validates:
    - 3+ topic_clusters
    - 5+ supporting_keywords per cluster
    - 4+ keyword_based_page_types
    - technical_seo_recommendations has substantial content

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Content strategy returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = ContentStrategyResultLight.model_validate(raw_json)
                logger.debug("Content strategy guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED in content strategy. "
                        "Generate UNIQUE topic clusters with DIFFERENT keywords."
                    )
                # Detect unquoted JSON keys (common LLM error)
                if "key must be a string" in str(e.msg) or _has_unquoted_keys(raw_sample):
                    return (
                        False,
                        "JSON SYNTAX ERROR: All object keys must be double-quoted strings. "
                        'WRONG: { cluster_name: "value" }  '
                        'CORRECT: { "cluster_name": "value" }  '
                        "Re-output with ALL keys in double quotes."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output: 3-5 topic clusters, 5-10 keywords per cluster."
                )
            except Exception as e:
                return (False, f"Failed to parse ContentStrategyResultLight: {e}")

        if not isinstance(result, ContentStrategyResultLight):
            return (False, f"Invalid type: expected ContentStrategyResultLight, got {type(result)}")

        # Validate topic_clusters (minimum 3)
        if result.topic_clusters:
            if len(result.topic_clusters) < 3:
                return (
                    False,
                    f"Need at least 3 topic_clusters, got {len(result.topic_clusters)}. "
                    "Create clusters for different content pillars based on keyword analysis."
                )

            # Validate supporting_keywords count per cluster
            for cluster in result.topic_clusters:
                if not cluster.supporting_keywords or len(cluster.supporting_keywords) < 5:
                    return (
                        False,
                        f"Topic cluster '{cluster.cluster_name}' needs at least 5 supporting_keywords, "
                        f"got {len(cluster.supporting_keywords or [])}. "
                        "Add more related keywords from the CSV data."
                    )

        # Validate keyword_based_page_types (minimum 4)
        if result.keyword_based_page_types:
            if len(result.keyword_based_page_types) < 4:
                return (
                    False,
                    f"Need at least 4 keyword_based_page_types, got {len(result.keyword_based_page_types)}. "
                    "Create page types for different keyword intents and tiers."
                )

        # Validate technical_seo_recommendations is comprehensive (now replaces Task 5)
        tech_seo = result.technical_seo_recommendations or ""
        if len(tech_seo) < 500:
            return (
                False,
                f"technical_seo_recommendations too short ({len(tech_seo)} chars, minimum 500). "
                "This field is the COMPLETE technical SEO guide. Include all 5 sections: "
                "Title Tag Strategy, URL Structure Patterns, Schema Markup Types, "
                "H1/H2 Structure Recommendations, and Internal Linking Strategy."
            )

        # Check for required sections (at least 3 of 5 must be present)
        required_sections = [
            ("title tag", "Title Tag Strategy"),
            ("url structure", "URL Structure Patterns"),
            ("schema", "Schema Markup Types"),
            ("h1", "H1/H2 Structure"),
            ("internal link", "Internal Linking Strategy"),
        ]
        tech_seo_lower = tech_seo.lower()
        found_sections = sum(1 for keyword, _ in required_sections if keyword in tech_seo_lower)
        if found_sections < 3:
            missing = [name for keyword, name in required_sections if keyword not in tech_seo_lower]
            return (
                False,
                f"technical_seo_recommendations missing key sections. Found {found_sections}/5 required sections. "
                f"Missing: {', '.join(missing[:3])}. "
                "Include comprehensive technical SEO guidance."
            )

        logger.info(
            f"✓ Content strategy guardrail passed: "
            f"{len(result.topic_clusters or [])} clusters, "
            f"{len(result.keyword_based_page_types or [])} page types, "
            f"{len(tech_seo)} chars technical SEO ({found_sections}/5 sections)"
        )
        return (True, _guardrail_success_payload(task_output, result))

    except Exception as e:
        return (False, f"Content strategy validation error: {str(e)}")


# ========================================
# TASK 3: IMPLEMENTATION PLAN GUARDRAIL (HIGH)
# ========================================


def validate_implementation_plan_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for create_implementation_plan_task (Task 3 - HIGH).

    Validates:
    - implementation_roadmap has substantial content

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Implementation plan returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = ImplementationPlanResult.model_validate(raw_json)
                logger.debug("Implementation plan guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED in implementation plan. "
                        "Generate UNIQUE phases and checklist items."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output: focus on 3-4 phases with concise descriptions."
                )
            except Exception as e:
                return (False, f"Failed to parse ImplementationPlanResult: {e}")

        if not isinstance(result, ImplementationPlanResult):
            return (False, f"Invalid type: expected ImplementationPlanResult, got {type(result)}")

        # Validate implementation_roadmap has content
        if not result.implementation_roadmap or len(result.implementation_roadmap) < 100:
            return (
                False,
                f"implementation_roadmap too short ({len(result.implementation_roadmap or '')} chars, minimum 100). "
                "Include phased plan with timelines and specific targets."
            )

        logger.info(
            f"✓ Implementation plan guardrail passed: "
            f"roadmap has {len(result.implementation_roadmap)} chars"
        )
        return (True, _guardrail_success_payload(task_output, result))

    except Exception as e:
        return (False, f"Implementation plan validation error: {str(e)}")


# validate_final_synthesis_output removed - Task 4 deleted (generic boilerplate)


def _parse_pydantic_from_task_output(task_output, model_class, task_name: str) -> tuple[Any | None, str | None]:
    """
    Unified helper to parse Pydantic model from task output.

    CrewAI 1.8.1 Compatibility: When guardrails exist, pydantic=None by design.
    This helper attempts to parse from .raw when .pydantic is None.

    Args:
        task_output: CrewAI task output object
        model_class: Pydantic model class to validate against
        task_name: Name of the task for error messages

    Returns:
        tuple[result | None, error_message | None]:
        - (result, None) on success
        - (None, error_message) on failure
    """
    try:
        # Try pydantic first
        result = task_output.pydantic
        if result is not None:
            if isinstance(result, model_class):
                return (result, None)
            return (None, f"Invalid type: expected {model_class.__name__}, got {type(result)}")

        # CrewAI 1.8.1: pydantic is None when guardrails exist, parse from .raw
        if not hasattr(task_output, 'raw') or not task_output.raw:
            return (None, f"{task_name} returned empty output (no pydantic or raw)")

        try:
            # Clean LLM response (remove XML tags, markdown fencing, etc.)
            cleaned_raw = clean_llm_response(task_output.raw)
            raw_json = json.loads(cleaned_raw)
            result = model_class.model_validate(raw_json)
            logger.debug(f"{task_name} guardrail: Parsed {model_class.__name__} from .raw")
            return (result, None)
        except json.JSONDecodeError as e:
            # Reasoning models (e.g. DeepSeek) sometimes emit a chain-of-thought
            # preamble as plain text BEFORE the JSON ("Thought: ...{...}"), so a
            # whole-string json.loads fails at char 0. Recover the embedded object
            # via bracket-matching before giving up (avoids a wasted retry).
            extracted = extract_json_object_from_text(task_output.raw)
            if extracted is not None:
                try:
                    result = model_class.model_validate(extracted)
                    logger.info(
                        f"{task_name} guardrail: recovered {model_class.__name__} "
                        f"from prose-wrapped output (model emitted text before JSON)"
                    )
                    return (result, None)
                except Exception as ve:
                    logger.warning(f"{task_name}: extracted JSON failed validation: {ve}")
            logger.warning(f"JSON parse error in {task_name}: {e}")
            return (
                None,
                f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}. "
                "Ensure valid JSON with no trailing commas and double-quoted strings. "
                "Output ONLY the JSON object — no reasoning, preamble, or commentary. "
                f"Return a valid {model_class.__name__} JSON object."
            )
        except Exception as e:
            logger.warning(f"Failed to validate {model_class.__name__}: {e}")
            return (None, f"Failed to parse {model_class.__name__}: {e}")

    except Exception as e:
        return (None, f"{task_name} validation error: {str(e)}")


# ========================================
# PAIN POINT CREW: CONTENT CATEGORIZATION GUARDRAIL
# ========================================


def validate_content_categorization(task_output) -> tuple[bool, Any]:
    """
    Guardrail for categorize_content_task to validate ContentCategorizationReport.

    Validates:
    - JSON is parseable (via unified helper)
    - Has at least 4 theme_categories
    - Each theme has at least 3 anchor_keywords (for Task 4 vector search)
    - Has at least 3 user_segments

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    # Parse using unified helper
    result, error = _parse_pydantic_from_task_output(
        task_output, ContentCategorizationReport, "Content categorization"
    )
    if error:
        return (False, error)

    # Validate minimum theme_categories (at least 4)
    if not result.theme_categories or len(result.theme_categories) < 4:
        return (
            False,
            f"Need at least 4 theme_categories, got {len(result.theme_categories or [])}. "
            "Identify more thematic categories from the discussion content."
        )

    # Validate each theme has at least 3 anchor_keywords (for Task 4 vector search)
    for theme in result.theme_categories:
        if not theme.anchor_keywords or len(theme.anchor_keywords) < 3:
            return (
                False,
                f"Theme '{theme.category_name}' needs at least 3 anchor_keywords, "
                f"got {len(theme.anchor_keywords or [])}. "
                "Add short phrases (2-6 words) that users say when discussing this theme. "
                "These will be used by Task 4 for vector search."
            )

    # Validate minimum user_segments (at least 3)
    if not result.user_segments or len(result.user_segments) < 3:
        return (
            False,
            f"Need at least 3 user_segments, got {len(result.user_segments or [])}. "
            "Identify more distinct user types from the discussions."
        )

    logger.info(
        f"✓ Content categorization guardrail passed: "
        f"{len(result.theme_categories)} themes, {len(result.user_segments)} segments"
    )
    return (True, _guardrail_success_payload(task_output, result))


# ========================================
# UNIFIED SOLUTION CREW: RAW CONCEPTS GUARDRAIL
# ========================================


def _normalize_technique(technique: str) -> str:
    """Normalize technique names: spaces/hyphens → underscores, lowercase."""
    return re.sub(r'[\s-]', '_', technique.strip().lower())


def _tags_match(tag_a: str | None, tag_b: str | None) -> bool:
    """Fuzzy M/D/J tag equality: stem-token overlap ≥ 0.6.

    Tags are short hyphenated phrases anchored by a suggested vocabulary in the
    prompt; fuzzy matching catches synonym rewording ('scheduled-automated-checks'
    vs 'periodic-automated-monitoring' share 'automated' + stems) that exact
    equality misses while staying reliable on the canonical vocabulary.
    """
    if not tag_a or not tag_b:
        return False
    from ..text_stemmer import stem_tokens

    tokens_a = stem_tokens(set(re.sub(r'[-_/]', ' ', str(tag_a).lower()).split()))
    tokens_b = stem_tokens(set(re.sub(r'[-_/]', ' ', str(tag_b).lower()).split()))
    if not tokens_a or not tokens_b:
        return False
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b)) >= 0.6


_BANNED_WNO_PHRASES = [
    "unique approach", "nobody has built", "innovative solution",
    "first of its kind", "novel concept", "groundbreaking",
    "no one else does this", "completely new",
]


def raw_concept_quality_error(concept) -> str | None:
    """Per-concept quality check (name, one_liner, keywords, why_non_obvious).

    Returns an error string if the concept is below quality bar, else None.
    Reusable for per-sample validation of direct-LLM divergent calls.
    """
    if not concept.concept_name or len(concept.concept_name.strip()) < 3:
        return "missing or too short concept_name"
    if not concept.one_liner or len(concept.one_liner.strip()) < 20:
        return (
            f"'{concept.concept_name}' has missing/short one_liner "
            f"(needs 20+ chars, got {len(concept.one_liner or '')})"
        )
    if not concept.target_keywords or len(concept.target_keywords) < 2:
        return (
            f"'{concept.concept_name}' needs at least 2 target_keywords, "
            f"got {len(concept.target_keywords or [])}"
        )
    wno = (getattr(concept, 'why_non_obvious', None) or "").strip()
    if len(wno) < 50:
        return (
            f"'{concept.concept_name}' missing/short why_non_obvious "
            f"(needs 50+ chars, got {len(wno)})"
        )
    if len(wno) < 80:
        wno_lower = wno.lower()
        for phrase in _BANNED_WNO_PHRASES:
            if phrase in wno_lower:
                return f"'{concept.concept_name}' why_non_obvious too generic (contains '{phrase}')"
    return None


def validate_raw_concept_list(
    result, *, min_concepts: int = 6, check_technique_diversity: bool = True
) -> tuple[bool, str | None]:
    """Validate a PARSED RawConceptList. Returns (ok, error_or_None).

    Parametrized so it serves both the CrewAI guardrail (min 6 + technique diversity)
    and per-sample direct-LLM validation (lenient: min 1, no cross-concept diversity —
    a single lens may legitimately cluster techniques; diversity is enforced on the pool).
    """
    if not result.concepts or len(result.concepts) < min_concepts:
        return (
            False,
            f"Need at least {min_concepts} concepts, got {len(result.concepts or [])}. "
            "Generate more diverse solution concepts using different ideation techniques."
        )
    for concept in result.concepts:
        err = raw_concept_quality_error(concept)
        if err:
            return (False, err)
    if check_technique_diversity:
        techniques_used = {
            _normalize_technique(c.ideation_technique)
            for c in result.concepts if c.ideation_technique
        }
        if len(techniques_used) < 3:
            return (
                False,
                f"Technique diversity violation: only {len(techniques_used)} techniques "
                f"({', '.join(sorted(techniques_used))}). Need 3+. Available: niche_drilling, "
                "data_source_inversion, cross_industry_template, atomic_feature, "
                "community_flip, platform_leverage, ai_native."
            )
        if "platform_leverage" not in techniques_used:
            logger.warning("No platform_leverage concepts generated.")
    return (True, None)


def validate_raw_concepts(task_output) -> tuple[bool, Any]:
    """CrewAI guardrail for divergent_exploration_task (parses + full validation)."""
    result, error = _parse_pydantic_from_task_output(
        task_output, RawConceptList, "Divergent exploration"
    )
    if error:
        return (False, error)
    ok, err = validate_raw_concept_list(result, min_concepts=6, check_technique_diversity=True)
    if not ok:
        return (False, err)
    logger.info(f"✓ Raw concepts guardrail passed: {len(result.concepts)} concepts")
    return (True, _guardrail_success_payload(task_output, result))


# ========================================
# AUDIENCE MAPPING CREW: AUDIENCE MAPPING GUARDRAIL
# ========================================


def validate_audience_mapping(task_output) -> tuple[bool, Any]:
    """
    Guardrail for audience_mapping_task to validate AudienceMappingLLMResult.

    Influencers are computed in Python (not LLM-produced), so this validates only the
    qualitative fields. It is the single source of quality floors (the final model relaxed
    its Pydantic min_length to avoid a double-validation trap):
    - JSON is parseable (via unified helper)
    - >= 3 audience_segments (matches the task's 3-5 contract)
    - primary_target_segment present
    - >= 6 common_vocabulary terms (verbatim extraction is the hardest ask for small models;
      gating lower than the 10-15 prompt target avoids retry loops / fabricated vocab)
    - >= 2 community_hubs

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    # Parse using unified helper
    result, error = _parse_pydantic_from_task_output(
        task_output, AudienceMappingLLMResult, "Audience mapping"
    )
    if error:
        return (False, error)

    # Validate minimum audience_segments (at least 3, per the 3-5 contract)
    if not result.audience_segments or len(result.audience_segments) < 3:
        return (
            False,
            f"Need at least 3 audience_segments, got {len(result.audience_segments or [])}. "
            "Identify more distinct audience segments from the discussions."
        )

    # Validate primary_target_segment exists
    if not result.primary_target_segment or len(result.primary_target_segment.strip()) < 3:
        return (
            False,
            "Missing or empty primary_target_segment. "
            "Identify the recommended primary target segment name."
        )

    # Validate common_vocabulary (at least 6 verbatim terms)
    if not result.common_vocabulary or len(result.common_vocabulary) < 6:
        return (
            False,
            f"Need at least 6 common_vocabulary terms, got {len(result.common_vocabulary or [])}. "
            "Extract more verbatim terms/phrases the audience actually uses from the digest."
        )

    # Validate community_hubs (at least 2)
    if not result.community_hubs or len(result.community_hubs) < 2:
        return (
            False,
            f"Need at least 2 community_hubs, got {len(result.community_hubs or [])}. "
            "Identify subreddits, forums, or Discord servers where this audience gathers."
        )

    logger.info(
        f"✓ Audience mapping guardrail passed: "
        f"{len(result.audience_segments)} segments, {len(result.common_vocabulary)} vocab terms"
    )
    return (True, _guardrail_success_payload(task_output, result))


# ========================================
# DATA SOURCE CREW: SOURCE EVALUATION GUARDRAIL
# ========================================


def validate_data_source_evaluation(task_output) -> tuple[bool, Any]:
    """
    Guardrail for evaluate_data_sources_task to validate SourceEvaluationReport.

    Validates:
    - JSON is parseable (via unified helper)
    - high_priority_sources is not empty (at least 1)
    - Has evaluation_summary and overall_data_quality_risk

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    # Parse using unified helper
    result, error = _parse_pydantic_from_task_output(
        task_output, SourceEvaluationReport, "Data source evaluation"
    )
    if error:
        return (False, error)

    # Validate high_priority_sources is not empty
    if not result.high_priority_sources or len(result.high_priority_sources) < 1:
        return (
            False,
            "Need at least 1 high_priority_source. "
            "Identify the most critical data source for this solution."
        )

    # Validate each high-priority source has quality_metrics
    for source in result.high_priority_sources:
        if not source.quality_metrics:
            return (
                False,
                f"High-priority source '{source.provider}' missing quality_metrics. "
                "Include coverage, freshness, integration complexity, cost, and quality assessment."
            )

    # Validate evaluation_summary exists
    if not result.evaluation_summary or len(result.evaluation_summary) < 30:
        return (
            False,
            f"evaluation_summary too short ({len(result.evaluation_summary or '')} chars, minimum 30). "
            "Provide a 2-3 sentence summary of evaluation findings."
        )

    # Validate overall_data_quality_risk exists
    if not result.overall_data_quality_risk or len(result.overall_data_quality_risk) < 20:
        return (
            False,
            f"overall_data_quality_risk too short ({len(result.overall_data_quality_risk or '')} chars, minimum 20). "
            "Assess the overall risk level for data quality."
        )

    total_sources = (
        len(result.high_priority_sources) +
        len(result.medium_priority_sources or []) +
        len(result.low_priority_sources or [])
    )
    logger.info(
        f"✓ Data source evaluation guardrail passed: "
        f"{len(result.high_priority_sources)} high priority, {total_sources} total sources"
    )
    return (True, _guardrail_success_payload(task_output, result))


# ========================================
# LANDING PAGE CREW: HTML OUTPUT GUARDRAILS
# ========================================
# These guardrails catch JSON serialization errors caused by large HTML content
# in html_content fields. The HTML Developer, Animation Enhancer, and QA Reviewer
# agents produce ~20-30K character HTML outputs that frequently break JSON escaping.


def _parse_html_task_output(task_output, model_class, task_name: str) -> tuple[Any | None, str | None]:
    """
    Parse HTML-heavy task output with fallback to bracket-matching extraction.

    HTML content (~20-30K chars) frequently causes JSON parse errors due to
    unescaped characters. This helper tries:
    1. Standard pydantic parsing
    2. Clean + json.loads from .raw
    3. Bracket-matching extraction (handles broken escaping in strings)

    Args:
        task_output: CrewAI task output object
        model_class: Pydantic model class to validate against
        task_name: Name of the task for error messages

    Returns:
        tuple[result | None, error_message | None]
    """
    # Try the standard unified helper first
    result, error = _parse_pydantic_from_task_output(task_output, model_class, task_name)
    if result is not None:
        return (result, None)

    # Standard parsing failed - try bracket-matching extraction as fallback
    # This handles cases where HTML content breaks json.loads() but the
    # overall JSON structure is valid (bracket matching respects string literals)
    if hasattr(task_output, 'raw') and task_output.raw:
        try:
            cleaned_raw = clean_llm_response(task_output.raw)
            extracted = extract_json_object_from_text(cleaned_raw)
            if extracted:
                result = model_class.model_validate(extracted)
                logger.info(f"{task_name} guardrail: Recovered via bracket-matching extraction")
                return (result, None)
        except Exception as e:
            logger.debug(f"{task_name} bracket-matching fallback also failed: {e}")

    # Both methods failed - return the original error
    return (None, error)


def validate_html_page_result(task_output) -> tuple[bool, Any]:
    """
    Guardrail for generate_html_page_task (Task 5) to handle JSON errors
    from large HTML content.

    The HTML Developer agent produces ~20-30K chars of HTML wrapped in JSON.
    Common failure: unescaped characters in html_content break JSON parsing.

    Validates:
    - JSON is parseable (with bracket-matching fallback)
    - html_content is non-empty and looks like HTML
    - sections_included has at least 1 section

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    result, error = _parse_html_task_output(task_output, HTMLPageResult, "HTML page generation")
    if error:
        return (
            False,
            f"{error} "
            "IMPORTANT: The html_content field contains HTML that must be properly JSON-escaped. "
            "Ensure all double quotes inside HTML are escaped as \\\" and all backslashes as \\\\. "
            "Return a valid JSON object with keys: html_content, sections_included, design_notes."
        )

    # Validate html_content looks like HTML
    if not result.html_content or len(result.html_content) < 500:
        return (
            False,
            f"html_content too short ({len(result.html_content or '')} chars, minimum 500). "
            "Generate a complete HTML page with <!DOCTYPE html>, <head>, and <body>."
        )

    html_lower = result.html_content.lower()
    if '<!doctype html>' not in html_lower and '<html' not in html_lower:
        return (
            False,
            "html_content does not contain <!DOCTYPE html> or <html> tag. "
            "Generate a complete, standalone HTML file."
        )

    # Validate sections_included
    if not result.sections_included or len(result.sections_included) < 1:
        return (
            False,
            "sections_included is empty. List the section types included in the HTML "
            "(e.g., hero, problem, solution, pricing, cta)."
        )

    logger.info(
        f"✓ HTML page guardrail passed: "
        f"{len(result.html_content)} chars, {len(result.sections_included)} sections"
    )
    return (True, _guardrail_success_payload(task_output, result))


def validate_animated_html_result(task_output) -> tuple[bool, Any]:
    """
    Guardrail for enhance_animations_task (Task 6) to handle JSON errors
    from large animated HTML content.

    Validates:
    - JSON is parseable (with bracket-matching fallback)
    - html_content is non-empty and looks like HTML
    - animations_added has at least 1 animation type

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    result, error = _parse_html_task_output(task_output, AnimatedHTMLResult, "Animation enhancement")
    if error:
        return (
            False,
            f"{error} "
            "IMPORTANT: The html_content field contains HTML that must be properly JSON-escaped. "
            "Ensure all double quotes inside HTML are escaped as \\\" and all backslashes as \\\\. "
            "Return a valid JSON object with keys: html_content, animations_added, animation_notes."
        )

    # Validate html_content
    if not result.html_content or len(result.html_content) < 500:
        return (
            False,
            f"html_content too short ({len(result.html_content or '')} chars, minimum 500). "
            "Return the COMPLETE enhanced HTML, not just the changed parts."
        )

    html_lower = result.html_content.lower()
    if '<!doctype html>' not in html_lower and '<html' not in html_lower:
        return (
            False,
            "html_content does not contain <!DOCTYPE html> or <html> tag. "
            "Return the complete HTML file with animations added."
        )

    # Validate animations_added
    if not result.animations_added or len(result.animations_added) < 1:
        return (
            False,
            "animations_added is empty. List the animation types added "
            "(e.g., page_load, scroll, hover, micro)."
        )

    logger.info(
        f"✓ Animated HTML guardrail passed: "
        f"{len(result.html_content)} chars, animations: {result.animations_added}"
    )
    return (True, _guardrail_success_payload(task_output, result))


def validate_qa_review_result(task_output) -> tuple[bool, Any]:
    """
    Guardrail for qa_review_task (Task 7) to handle JSON errors
    from large QA-reviewed HTML content.

    Validates:
    - JSON is parseable (with bracket-matching fallback)
    - html_content is non-empty and looks like HTML
    - quality_score is within range
    - issues_fixed_count is present

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    result, error = _parse_html_task_output(task_output, QAReviewResult, "QA review")
    if error:
        return (
            False,
            f"{error} "
            "IMPORTANT: The html_content field contains HTML that must be properly JSON-escaped. "
            "Ensure all double quotes inside HTML are escaped as \\\" and all backslashes as \\\\. "
            "Return a valid JSON object with keys: html_content, issues_found, issues_fixed_count, "
            "quality_score, passes_qa, review_notes."
        )

    # Validate html_content
    if not result.html_content or len(result.html_content) < 500:
        return (
            False,
            f"html_content too short ({len(result.html_content or '')} chars, minimum 500). "
            "Return the COMPLETE QA-reviewed HTML, not just the changed parts."
        )

    html_lower = result.html_content.lower()
    if '<!doctype html>' not in html_lower and '<html' not in html_lower:
        return (
            False,
            "html_content does not contain <!DOCTYPE html> or <html> tag. "
            "Return the complete reviewed HTML file."
        )

    # quality_score range is enforced by Pydantic (ge=0, le=100), but validate here too
    if result.quality_score < 0 or result.quality_score > 100:
        return (
            False,
            f"quality_score must be 0-100, got {result.quality_score}."
        )

    logger.info(
        f"✓ QA review guardrail passed: "
        f"{len(result.html_content)} chars, score: {result.quality_score}/100, "
        f"issues fixed: {result.issues_fixed_count}"
    )
    return (True, _guardrail_success_payload(task_output, result))


# ========================================
# PAIN POINT CREW: QUOTE ENRICHMENT GUARDRAIL (TASK 4)
# ========================================





def validate_solution_selection(task_output) -> tuple[bool, Any]:
    """
    Guardrail for solution_selection_task to catch malformed JSON.

    CrewAI 1.8.1 Compatibility: When guardrails exist, pydantic=None by design.
    Must parse from .raw and return (True, raw_string) on success.

    Validates:
    1. JSON parses into SolutionSelection (catches malformed JSON crash)
    2. selected_solution_name present and >= 3 chars
    3. selection_rationale present and >= 100 chars
    4. recommended_focus present and non-empty

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, SolutionSelection, "Solution selection"
    )
    if error:
        return (False, error)

    if not result.selected_solution_name or len(result.selected_solution_name.strip()) < 3:
        return (False, "selected_solution_name must be at least 3 characters.")

    if not result.selection_rationale or len(result.selection_rationale) < 100:
        return (False, f"selection_rationale too short ({len(result.selection_rationale or '')} chars, minimum 100).")

    if not result.recommended_focus or len(result.recommended_focus.strip()) < 5:
        return (False, "recommended_focus is required.")

    logger.info(f"✓ Solution selection guardrail passed: '{result.selected_solution_name}'")
    return (True, _guardrail_success_payload(task_output, result))


def validate_traffic_monetization(task_output, traffic_ceiling_y1_high: int | None = None) -> tuple[bool, Any]:
    """
    Guardrail for traffic_monetization_analysis_task.

    Validates:
    1. JSON parses into TrafficMonetizationResult
    2. solution_name present
    3. Key revenue fields non-empty
    4. At least 1 recommended_ad_networks entry
    5. When the evidence-based ceiling is supplied: estimated_monthly_pageviews
       must not exceed it (the ceiling is shown in the prompt as a hard limit
       but was previously never enforced)

    The old mandatory ≥1 affiliate-program rule is gone — it forced the LLM to
    invent affiliate programs in niches where none realistically exist.
    """
    from .numeric_parsers import parse_dollar_amount

    result, error = _parse_pydantic_from_task_output(
        task_output, TrafficMonetizationResult, "Traffic monetization"
    )
    if error:
        return (False, error)

    if not result.solution_name or not result.solution_name.strip():
        return (False, "solution_name is required.")

    if not result.estimated_monthly_revenue_range or not result.estimated_monthly_revenue_range.strip():
        return (False, "estimated_monthly_revenue_range is required.")

    if not result.recommended_ad_networks:
        return (False, "recommended_ad_networks must contain at least 1 entry (e.g. 'Google AdSense').")

    if traffic_ceiling_y1_high and result.estimated_monthly_pageviews:
        # parse_dollar_amount handles plain numbers/ranges (returns midpoint)
        claimed = parse_dollar_amount(result.estimated_monthly_pageviews)
        if claimed and claimed > traffic_ceiling_y1_high * 1.1:  # 10% rounding tolerance
            return (
                False,
                f"estimated_monthly_pageviews ({result.estimated_monthly_pageviews}) exceeds the "
                f"evidence-based Year-1 ceiling of {traffic_ceiling_y1_high:,} visits/mo provided "
                "in the task. Revise the projection to respect the ceiling.",
            )

    logger.info(f"✓ Traffic monetization guardrail passed: '{result.solution_name}'")
    return (True, _guardrail_success_payload(task_output, result))


# Numeric fingerprints of the fictional example products in
# crews/config/pricing_strategy_tasks.yaml (DevFlowTracker subscription block,
# PlumbingCostCalc ad block). The LLM sometimes copies these values wholesale
# instead of deriving its own — observed 2026-06-11, when a report shipped the
# full DevFlowTracker tuple ($19/$49/$149 tiers, $32 ARPU, $384-$960 LTV).
# Matching is numeric with ±2% tolerance (not substring), so reformats and
# ±$1 tweaks still count. A single coincidental match is plausible for a real
# product; >= _EXAMPLE_REJECT_THRESHOLD independent signals is copying.
# tests/unit/test_numeric_guardrails.py has a sync test that fails if the YAML
# examples change without these fingerprints being updated.
_EXAMPLE_REJECT_THRESHOLD = 3


def _matches_example(text: str | None, target: float, tol: float = 0.02) -> bool:
    from .numeric_parsers import parse_dollar_amount

    parsed = parse_dollar_amount(text)
    return parsed is not None and abs(parsed - target) <= target * tol


def _collect_example_matches(result) -> list[tuple[str, str]]:
    """Count independent signals that pricing fields copy the YAML examples.

    Ranges compare by midpoint (parse_dollar_amount semantics): LTV
    "$384 - $960" → 672, ad "$400-600" → 500, affiliate "$150-300" → 225.
    """
    matches: list[tuple[str, str]] = []
    if _matches_example(result.recommended_starter_price, 19):
        matches.append(("recommended_starter_price", str(result.recommended_starter_price)))
    if _matches_example(result.recommended_pro_price, 49):
        matches.append(("recommended_pro_price", str(result.recommended_pro_price)))
    if _matches_example(result.recommended_enterprise_price, 149):
        matches.append(("recommended_enterprise_price", str(result.recommended_enterprise_price)))
    # Coupled pair: a legitimate $32 ARPU arithmetically forces LTV ≈
    # $384-$960 via the task's own ×12-30 formula, so ARPU+LTV matching the
    # example counts as ONE signal — and LTV alone is not counted.
    if _matches_example(result.estimated_arpu, 32) and _matches_example(result.estimated_ltv, 672):
        matches.append((
            "estimated_arpu+estimated_ltv",
            f"{result.estimated_arpu} / {result.estimated_ltv}",
        ))
    if _matches_example(result.estimated_monthly_ad_revenue, 500):
        matches.append(("estimated_monthly_ad_revenue", str(result.estimated_monthly_ad_revenue)))
    if _matches_example(result.estimated_monthly_affiliate_revenue, 225):
        matches.append(("estimated_monthly_affiliate_revenue", str(result.estimated_monthly_affiliate_revenue)))
    return matches


def validate_pricing_strategy(task_output, suggested_cac_range: str | None = None) -> tuple[bool, Any]:
    """
    Guardrail for pricing_strategy_analysis_task (Stage 7).

    Validates:
    1. JSON parses into PricingStrategyResult
    2. solution_name present and non-empty
    3. pricing_rationale >= 50 chars
    4. Ad-Supported-Free / Affiliate-Only models: at least one of the ad /
       affiliate revenue fields parses to a positive dollar amount. The
       subscription checks below are SKIPPED — the task YAML mandates
       "N/A - ..." for estimated_ltv and ltv_to_cac_ratio on these models.
    5. estimated_arpu / estimated_ltv parse to positive dollar amounts
    6. Unit-economics sanity: LTV >= ARPU (at least one month of retention)
    7. ltv_to_cac_ratio parses and meets the mandatory 2:1 floor
    8. When the pre-computed CAC anchor is supplied: the stated ratio must be
       within 2x of LTV ÷ CAC (catches fabricated ratios while tolerating the
       range formats both fields use)

    The previous version only checked these fields were non-empty strings —
    internally inconsistent dollar math shipped verbatim into the report.
    """
    from .numeric_parsers import parse_dollar_amount, parse_ratio

    result, error = _parse_pydantic_from_task_output(
        task_output, PricingStrategyResult, "Pricing strategy"
    )
    if error:
        return (False, error)

    if not result.solution_name or not result.solution_name.strip():
        return (False, "solution_name is required.")

    def _reject(field_name: str, field_value: Any, reason: str) -> tuple[bool, str]:
        # Failure observability: the retry prompt gets `reason`, but without
        # this line the log never shows WHAT the LLM produced — diagnosing
        # the 2026-06-11 ad-model failures required reconstructing it from
        # the task YAML.
        logger.warning(
            f"Pricing guardrail rejected '{result.solution_name}': "
            f"{field_name}={field_value!r} — {reason}"
        )
        return (False, reason)

    if len(result.pricing_rationale) < 50:
        return _reject(
            "pricing_rationale",
            result.pricing_rationale,
            f"pricing_rationale is only {len(result.pricing_rationale)} chars, need >= 50. "
            "Provide a detailed rationale explaining why this pricing strategy was chosen.",
        )

    # Example-anchoring check — applies to BOTH model branches. See
    # _collect_example_matches for the fingerprint rationale.
    example_matches = _collect_example_matches(result)
    if len(example_matches) >= _EXAMPLE_REJECT_THRESHOLD:
        fields_desc = "; ".join(f"{name}={value}" for name, value in example_matches)
        return _reject(
            "example-anchoring",
            fields_desc,
            f"{len(example_matches)} of your figures ({fields_desc}) match the "
            "fictional example products (DevFlowTracker / PlumbingCostCalc) in "
            "the task instructions. Those numbers are fabricated format "
            "illustrations for unrelated markets — slightly altered versions "
            "will also be rejected. Recompute ALL pricing figures from THIS "
            "task's inputs and show the arithmetic in your reasoning: "
            "(1) tier prices from the competitor pricing data and WTP scores, "
            "(2) ARPU from YOUR tier prices with a stated tier mix, "
            "(3) LTV = ARPU × 12-30 months, "
            "(4) ltv_to_cac_ratio = LTV ÷ the suggested CAC range provided.",
        )

    # Ad/affiliate models have no subscription unit economics — the task YAML
    # explicitly instructs "N/A - ..." for estimated_ltv and ltv_to_cac_ratio,
    # so requiring numerics there rejects prompt-compliant output (it cost 2/3
    # solutions their pricing analysis on 2026-06-11). The economically
    # meaningful number for these models is the ad/affiliate revenue estimate.
    if result.pricing_model in ("Ad-Supported-Free", "Affiliate-Only"):
        ad_rev = parse_dollar_amount(result.estimated_monthly_ad_revenue)
        affiliate_rev = parse_dollar_amount(result.estimated_monthly_affiliate_revenue)
        if not ((ad_rev and ad_rev > 0) or (affiliate_rev and affiliate_rev > 0)):
            return _reject(
                "estimated_monthly_ad_revenue / estimated_monthly_affiliate_revenue",
                (result.estimated_monthly_ad_revenue, result.estimated_monthly_affiliate_revenue),
                f"{result.pricing_model} model requires at least one of "
                "estimated_monthly_ad_revenue or estimated_monthly_affiliate_revenue "
                "to contain a positive dollar amount (e.g., '$350-700/month').",
            )
        logger.info(
            f"✓ Pricing strategy guardrail passed: '{result.solution_name}' "
            f"({result.pricing_model})"
        )
        return (True, _guardrail_success_payload(task_output, result))

    arpu = parse_dollar_amount(result.estimated_arpu)
    if arpu is None or arpu <= 0:
        return _reject(
            "estimated_arpu",
            result.estimated_arpu,
            "estimated_arpu must contain a positive dollar amount (e.g., '$24/month').",
        )

    ltv = parse_dollar_amount(result.estimated_ltv)
    if ltv is None or ltv <= 0:
        return _reject(
            "estimated_ltv",
            result.estimated_ltv,
            "estimated_ltv must contain a positive dollar amount (e.g., '$420 - $1,050').",
        )

    if ltv < arpu:
        return _reject(
            "estimated_ltv",
            result.estimated_ltv,
            f"Unit-economics error: estimated_ltv ({result.estimated_ltv}) is below "
            f"estimated_arpu ({result.estimated_arpu}). LTV = retention months × ARPU, "
            "so it cannot be less than one month of ARPU. State your LTV calculation "
            "explicitly and recompute.",
        )

    stated_ratio = parse_ratio(result.ltv_to_cac_ratio)
    if stated_ratio is None:
        return _reject(
            "ltv_to_cac_ratio",
            result.ltv_to_cac_ratio,
            "ltv_to_cac_ratio must contain a numeric ratio (e.g., '3:1').",
        )

    if stated_ratio < 2.0:
        return _reject(
            "ltv_to_cac_ratio",
            result.ltv_to_cac_ratio,
            f"ltv_to_cac_ratio ({result.ltv_to_cac_ratio}) is below the MANDATORY 2:1 minimum. "
            "Adjust pricing, retention assumptions, or acquisition strategy and recompute — "
            "state your LTV and CAC calculations explicitly before the final numbers.",
        )

    if suggested_cac_range:
        cac = parse_dollar_amount(suggested_cac_range)
        if cac and cac > 0:
            computed_ratio = ltv / cac
            # Tolerate range-midpoint noise; fail only on egregious fabrication
            if stated_ratio > computed_ratio * 2 or stated_ratio < computed_ratio / 2:
                return _reject(
                    "ltv_to_cac_ratio",
                    result.ltv_to_cac_ratio,
                    f"ltv_to_cac_ratio ({result.ltv_to_cac_ratio}) is inconsistent with your own "
                    f"numbers: LTV {result.estimated_ltv} ÷ suggested CAC {suggested_cac_range} "
                    f"≈ {computed_ratio:.1f}:1, but you stated {stated_ratio:.1f}:1. "
                    "Recompute the ratio from the LTV and CAC you used.",
                )

    logger.info(f"✓ Pricing strategy guardrail passed: '{result.solution_name}'")
    return (True, _guardrail_success_payload(task_output, result))


def validate_solution_refinement(task_output) -> tuple[bool, Any]:
    """
    Guardrail for refine_solution_strategy_task (Stage 10).

    Validates:
    1. JSON parses into SolutionRefinement
    2. geographic_priorities >= 1 entry
    3. feature_priorities >= 1 entry
    4. strategic_insights >= 3 entries
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, SolutionRefinement, "Solution refinement"
    )
    if error:
        return (False, error)

    if not result.geographic_priorities:
        return (False, "geographic_priorities must contain at least 1 entry.")

    if not result.feature_priorities:
        return (False, "feature_priorities must contain at least 1 entry.")

    if len(result.strategic_insights) < 3:
        return (
            False,
            f"strategic_insights has only {len(result.strategic_insights)} entries, need >= 3. "
            "Provide at least 3 actionable insights from keyword analysis.",
        )

    logger.info(f"✓ Solution refinement guardrail passed: {len(result.strategic_insights)} insights")
    return (True, _guardrail_success_payload(task_output, result))


def validate_trend_narrative(task_output) -> tuple[bool, Any]:
    """
    Guardrail for trend_longevity_analysis_task (Stage 11).

    Validates:
    1. JSON parses into TrendNarrativeOutput
    2. longevity_rationale >= 50 chars
    3. community_growth_indicators >= 3 entries
    4. trend_reversal_risks >= 3 entries
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, TrendNarrativeOutput, "Trend narrative"
    )
    if error:
        return (False, error)

    if len(result.longevity_rationale) < 50:
        return (
            False,
            f"longevity_rationale is only {len(result.longevity_rationale)} chars, need >= 50. "
            "Provide 2-3 sentences explaining the longevity verdict with specific trend data.",
        )

    if len(result.community_growth_indicators) < 3:
        return (
            False,
            f"community_growth_indicators has only {len(result.community_growth_indicators)} entries, need >= 3. "
            "Provide 3-5 signals of community growth or decline.",
        )

    if len(result.trend_reversal_risks) < 3:
        return (
            False,
            f"trend_reversal_risks has only {len(result.trend_reversal_risks)} entries, need >= 3. "
            "Provide 3-5 factors that could reverse positive trends.",
        )

    logger.info(f"✓ Trend narrative guardrail passed: verdict='{result.longevity_verdict}'")
    return (True, _guardrail_success_payload(task_output, result))


def validate_site_structure(task_output) -> tuple[bool, Any]:
    """
    Guardrail for site_structure_task (Stage 10.5, task 1).

    Validates:
    1. JSON parses into SiteStructure
    2. overview present and non-empty
    3. sections >= 2 entries
    4. mvp_page_count >= 1
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, SiteStructure, "Site structure"
    )
    if error:
        return (False, error)

    if not result.overview or not result.overview.strip():
        return (False, "overview is required (1-2 sentence architecture philosophy).")

    if len(result.sections) < 2:
        return (
            False,
            f"sections has only {len(result.sections)} entries, need >= 2. "
            "Provide at least 2 logical site sections with pages.",
        )

    if result.mvp_page_count < 1:
        return (False, "mvp_page_count must be >= 1.")

    logger.info(f"✓ Site structure guardrail passed: {len(result.sections)} sections, {result.mvp_page_count} MVP pages")
    return (True, _guardrail_success_payload(task_output, result))


def validate_user_flows(task_output) -> tuple[bool, Any]:
    """
    Guardrail for user_flows_task (Stage 10.5, task 2).

    Validates:
    1. JSON parses into UserFlowsSection
    2. flows >= 1 entry
    3. Each flow has steps >= 3
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, UserFlowsSection, "User flows"
    )
    if error:
        return (False, error)

    if not result.flows:
        return (False, "flows must contain at least 1 user journey flow.")

    for i, flow in enumerate(result.flows):
        if len(flow.steps) < 3:
            return (
                False,
                f"Flow '{flow.flow_name}' (index {i}) has only {len(flow.steps)} steps, need >= 3. "
                "Each user flow must have at least 3 sequential steps.",
            )

    logger.info(f"✓ User flows guardrail passed: {len(result.flows)} flows")
    return (True, _guardrail_success_payload(task_output, result))


def validate_data_implementation_plan(task_output) -> tuple[bool, Any]:
    """
    Guardrail for create_data_roadmap_task (Stage 13, task 3).

    Validates:
    1. JSON parses into DataImplementationPlan
    2. implementation_phases >= 1 entry
    3. estimated_monthly_cost present and non-empty
    4. implementation_roadmap >= 50 chars
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, DataImplementationPlan, "Data implementation plan"
    )
    if error:
        return (False, error)

    if not result.implementation_phases:
        return (False, "implementation_phases must contain at least 1 entry.")

    if not result.estimated_monthly_cost or not result.estimated_monthly_cost.strip():
        return (False, "estimated_monthly_cost is required (e.g., '$250-500/month').")

    if len(result.implementation_roadmap) < 50:
        return (
            False,
            f"implementation_roadmap is only {len(result.implementation_roadmap)} chars, need >= 50. "
            "Provide a detailed phased approach for data integration (2-3 paragraphs).",
        )

    logger.info(f"✓ Data implementation plan guardrail passed: {len(result.implementation_phases)} phases")
    return (True, _guardrail_success_payload(task_output, result))


def validate_keyword_summary(task_output) -> tuple[bool, Any]:
    """
    Guardrail for synthesize_keyword_summary_task / synthesize_keyword_summary_parallel_task (Stage 6).

    Validates:
    1. JSON parses into KeywordSummaryResult
    2. key_findings >= 1 entry
    3. competitive_positioning present and >= 50 chars
    """
    result, error = _parse_pydantic_from_task_output(
        task_output, KeywordSummaryResult, "Keyword summary"
    )
    if error:
        return (False, error)

    if not result.key_findings:
        return (False, "key_findings must contain at least 1 entry.")

    if not result.competitive_positioning or len(result.competitive_positioning) < 50:
        length = len(result.competitive_positioning) if result.competitive_positioning else 0
        return (
            False,
            f"competitive_positioning is only {length} chars, need >= 50. "
            "Provide keyword gaps to exploit and unique positioning angles (markdown, 2-4 sections).",
        )

    logger.info(f"✓ Keyword summary guardrail passed: {len(result.key_findings)} findings")
    return (True, _guardrail_success_payload(task_output, result))
