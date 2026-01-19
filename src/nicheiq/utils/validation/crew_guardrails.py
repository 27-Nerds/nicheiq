"""
Crew Guardrails - Validation functions for CrewAI task outputs.

NOTE: CrewAI 1.7.0 intentionally sets task_output.pydantic = None when guardrails exist.
Most validation has been migrated to Pydantic model validators (the recommended approach).
Only complex cross-solution comparisons remain here as guardrails.
"""

import json
from typing import Any

from loguru import logger

from ...models.competitor import CompetitiveAnalysisResult
from ...models.solution_idea import IdeaGenerationResult
from ..parsing.json_extractor import clean_llm_response


def validate_diversity(
    task_output, allowed_project_types: list[str] | None = None
) -> tuple[bool, Any]:
    """
    Guardrail for solution_refinement_task to enforce diversity.

    NOTE: This guardrail must remain (not moved to Pydantic) because it performs
    cross-solution comparisons that cannot be expressed as single-field validators.

    CrewAI 1.7.0 Compatibility: When guardrails exist, pydantic=None by design.
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
        # CrewAI 1.7.0: When guardrails exist, pydantic is intentionally None
        # Try pydantic first, then fall back to parsing .raw
        result = task_output.pydantic
        if result is None:
            # CrewAI 1.7.0 behavior: parse from .raw
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Solution refinement returned empty output (no pydantic or raw)")

            try:
                # Clean LLM response to remove XML-like tags that may confuse JSON parsing
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = IdeaGenerationResult.model_validate(raw_json)
                logger.debug("Diversity guardrail: Parsed IdeaGenerationResult from .raw")
            except json.JSONDecodeError as e:
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

        # Rule 1: If multiple types allowed, require at least 2 different types
        if len(allowed_types) >= 2:
            used_types = set(idea.project_type for idea in ideas if idea.project_type)
            if len(used_types) < 2:
                return (
                    False,
                    f"Diversity violation: Need 2+ different project types, got only: {used_types}. "
                    f"Generate solutions with different architectures (e.g., directory + aggregator, not just directories).",
                )
            logger.info(f"✓ Project type diversity check passed: {used_types}")

        # Rule 2: If single type allowed, require diversity WITHIN that type
        elif len(allowed_types) == 1:
            # Check data sources diversity
            data_sources_list = [set(idea.data_sources or []) for idea in ideas]
            unique_sources = len(
                set(tuple(sorted(ds)) for ds in data_sources_list if ds)
            )
            # At least 50% should have different data sources
            if unique_sources < len(ideas) * 0.5:
                return (
                    False,
                    f"Diversity violation within {allowed_types[0]}: "
                    f"Solutions too similar - need different data sources or mechanisms. "
                    f"Only {unique_sources}/{len(ideas)} have unique data sources.",
                )
            logger.info(
                f"✓ Within-type diversity check passed: {unique_sources} unique data source combinations"
            )

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
        # CrewAI 1.7.0: Return raw string for CrewAI to re-parse
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Diversity validation error: {str(e)}")


def detect_similarity(idea_a, idea_b) -> bool:
    """
    Detect if two solution ideas are too similar.

    Checks:
    1. Same data sources = likely similar mechanism
    2. Value proposition keyword overlap > 60%
    3. Identical target personas

    Returns:
        bool: True if ideas are too similar
    """
    # Check 1: Same data sources = likely similar mechanism
    sources_a = set(idea_a.data_sources or [])
    sources_b = set(idea_b.data_sources or [])
    if sources_a and sources_b and sources_a == sources_b:
        logger.debug(f"Similarity detected: Same data sources ({sources_a})")
        return True

    # Check 2: Value proposition keyword overlap
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

        vp_a = set(idea_a.value_proposition.lower().split()) - stop_words
        vp_b = set(idea_b.value_proposition.lower().split()) - stop_words

        if vp_a and vp_b:
            overlap = len(vp_a & vp_b) / min(len(vp_a), len(vp_b))
            if overlap > 0.6:  # >60% overlap in value prop
                logger.debug(
                    f"Similarity detected: {overlap:.0%} value proposition overlap"
                )
                return True

    # Check 3: Same target personas (exact match = likely duplicate)
    if idea_a.target_personas and idea_b.target_personas:
        if set(idea_a.target_personas) == set(idea_b.target_personas):
            logger.debug("Similarity detected: Identical target personas")
            return True

    return False


def create_diversity_guardrail(allowed_project_types: list[str] | None = None):
    """
    Factory function to create a diversity guardrail with specific project types.

    Args:
        allowed_project_types: List of allowed project types

    Returns:
        Guardrail function with project types bound
    """

    def guardrail(task_output) -> tuple[bool, Any]:
        return validate_diversity(task_output, allowed_project_types)

    return guardrail


def validate_competitive_analysis(task_output) -> tuple[bool, Any]:
    """
    Guardrail for competitive_analysis_task to detect truncated JSON output.

    CrewAI 1.7.0 Compatibility: When guardrails exist, pydantic=None by design.
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
        # CrewAI 1.7.0: When guardrails exist, pydantic is intentionally None
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
            if len(landscape.competitors) < 2:
                return (
                    False,
                    f"Landscape '{landscape.solution_name}' needs at least 2 competitors, got {len(landscape.competitors)}"
                )
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
        # CrewAI 1.7.0: Return raw string for CrewAI to re-parse
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Competitive analysis validation error: {str(e)}")
