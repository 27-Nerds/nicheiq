"""
Crew Guardrails - Validation functions for CrewAI task outputs.
Used as guardrail callbacks in task definitions.
"""

from typing import Any

from loguru import logger

from ...models.solution_idea import CompetitiveEnhancements, IdeaGenerationResult


def validate_no_field_loss(
    task_output, expected_count: int | None = None
) -> tuple[bool, Any]:
    """
    Guardrail for competitive_refinement_task to ensure no data loss.
    Validates solution count and required fields are preserved.

    Args:
        task_output: CrewAI task output object
        expected_count: Optional expected solution count

    Returns:
        tuple[bool, Any]: (success: bool, result_or_error: Any)
    """
    try:
        result = task_output.pydantic

        if not isinstance(result, IdeaGenerationResult):
            return (
                False,
                f"Invalid output type: expected IdeaGenerationResult, got {type(result)}",
            )

        # DETECT SCHEMA OUTPUT BUG: Agent returned JSON Schema instead of populated data
        if len(result.solution_ideas) == 0:
            logger.error(
                "Task 3 returned empty solution_ideas list - possible schema confusion"
            )
            logger.error(f"Output type: {type(result)}")

            # Check raw output for schema indicators
            if hasattr(task_output, "raw") and task_output.raw:
                raw_preview = str(task_output.raw)[:1000]
                logger.error(f"Raw output preview: {raw_preview}")

                # Detect schema structure patterns
                if any(
                    indicator in task_output.raw
                    for indicator in [
                        '"additionalProperties"',
                        '"properties":',
                        '"type": "object"',
                        '"required": [',
                    ]
                ):
                    return (
                        False,
                        "Agent returned JSON Schema definition instead of populated data. "
                        "Task prompt includes concrete examples - agent must extract actual values from context "
                        "and output populated IdeaGenerationResult with real solution data.",
                    )

            return (
                False,
                "Empty solution_ideas list - agent must extract solutions from context",
            )

        # Check solution count matches input if provided
        if expected_count is not None:
            actual_count = len(result.solution_ideas)
            if actual_count != expected_count:
                return (
                    False,
                    f"Solution count mismatch: expected {expected_count}, got {actual_count}",
                )

        # Validate required fields
        field_errors = []
        for idea in result.solution_ideas:
            missing_fields = []

            if not idea.solution_name or idea.solution_name.strip() == "":
                missing_fields.append("solution_name")
            if not idea.description or idea.description.strip() == "":
                missing_fields.append("description")
            if not idea.pain_points_addressed:
                missing_fields.append("pain_points_addressed")
            if not idea.core_features:
                missing_fields.append("core_features")
            if idea.market_fit_score is None:
                missing_fields.append("market_fit_score")
            if idea.technical_feasibility_score is None:
                missing_fields.append("technical_feasibility_score")

            if missing_fields:
                field_errors.append(
                    f"Solution '{idea.solution_name}': {', '.join(missing_fields)}"
                )

        if field_errors:
            return (False, "Required fields missing:\n" + "\n".join(field_errors))

        logger.info(
            f"✓ Guardrail passed: {len(result.solution_ideas)} solutions with all fields preserved"
        )
        return (True, result)

    except Exception as e:
        return (False, f"Guardrail validation error: {str(e)}")


def validate_enhancements_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for competitive_refinement_task to ensure valid enhancement output.

    Validates:
    - Pydantic output exists
    - solution_enhancements list is populated
    - Each enhancement has required fields

    Returns:
        tuple[bool, Any]: (success, result_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            return (False, "Competitive refinement returned None pydantic output")

        if not isinstance(result, CompetitiveEnhancements):
            return (
                False,
                f"Invalid output type: expected CompetitiveEnhancements, got {type(result)}",
            )

        # Validate solution_enhancements exists and has entries
        if not result.solution_enhancements:
            return (
                False,
                "solution_enhancements list cannot be empty - must have at least 1 enhancement",
            )

        # Validate each enhancement has required solution_name
        for i, enh in enumerate(result.solution_enhancements):
            if not enh.solution_name or enh.solution_name.strip() == "":
                return (False, f"Enhancement {i} missing solution_name")

        logger.info(
            f"✓ Enhancements guardrail passed: {len(result.solution_enhancements)} solution enhancements"
        )
        return (True, result)

    except Exception as e:
        return (False, f"Enhancement validation error: {str(e)}")


def validate_diversity(
    task_output, allowed_project_types: list[str] | None = None
) -> tuple[bool, Any]:
    """
    Guardrail for solution_refinement_task to enforce diversity.

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
        result = task_output.pydantic
        if result is None:
            return (False, "Solution refinement returned None pydantic output")

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
        return (True, result)

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
