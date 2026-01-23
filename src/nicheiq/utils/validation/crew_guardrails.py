"""
Crew Guardrails - Validation functions for CrewAI task outputs.

NOTE: CrewAI 1.7.0 intentionally sets task_output.pydantic = None when guardrails exist.
Most validation has been migrated to Pydantic model validators (the recommended approach).
Only complex cross-solution comparisons remain here as guardrails.

Guardrail Return Convention:
- (True, task_output.raw) - Validation passed, return raw for CrewAI to re-parse
- (False, error_message) - Validation failed, CrewAI will retry up to guardrail_max_retries times
"""

import json
from typing import Any

from loguru import logger

from ...models.competitor import CompetitiveAnalysisResult
from ...models.seo_strategy import (
    CategoryLightResult,
    ContentStrategyResultLight,
    FinalSynthesis,
    GeographicLightResult,
    ImplementationGuide,
    ImplementationGuideLight,
    ImplementationPlanResult,
    StrategicLightResult,
)
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
        if not result.category_groups or len(result.category_groups) < 3:
            return (
                False,
                f"Need at least 3 category groups, got {len(result.category_groups or [])}. "
                "Analyze the keywords and create meaningful thematic groups."
            )

        # Check for duplicate keywords across groups (sign of repetition issue)
        all_keywords = []
        for group in result.category_groups:
            all_keywords.extend(kw.lower().strip() for kw in group.keywords)

        unique_keywords = set(all_keywords)
        if len(unique_keywords) < len(all_keywords) * 0.7:  # >30% duplicates
            return (
                False,
                f"Too many duplicate keywords across groups ({len(all_keywords) - len(unique_keywords)} duplicates). "
                "Each keyword should appear in only ONE category group."
            )

        logger.info(f"✓ Category tier guardrail passed: {len(result.category_groups)} groups")
        return (True, task_output.raw)

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
        if result.geographic_groups:
            # Check for duplicate keywords
            all_keywords = []
            for group in result.geographic_groups:
                all_keywords.extend(kw.lower().strip() for kw in group.keywords)

            unique_keywords = set(all_keywords)
            if len(all_keywords) > 5 and len(unique_keywords) < len(all_keywords) * 0.8:
                return (
                    False,
                    f"Too many duplicate keywords in geographic groups. "
                    "Each location keyword should appear in only ONE region."
                )

        logger.info(f"✓ Geographic tier guardrail passed: {len(result.geographic_groups or [])} regions")
        return (True, task_output.raw)

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
        return (True, task_output.raw)

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


def validate_implementation_guide_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for create_implementation_guide_task (Task 5 - CRITICAL).

    Validates:
    - 4+ page_type_implementations
    - 6+ schema_examples in schema_markup_strategy
    - Valid JSON-LD in each schema example
    - No template variables like [solution_name] or {variable} in JSON-LD
    - h2_structure is array, not string

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Implementation guide returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = ImplementationGuide.model_validate(raw_json)
                logger.debug("Implementation guide guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                # Check for repetition loop pattern
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED in implementation guide. "
                        "Generate UNIQUE page types and schema examples. "
                        "Do NOT repeat the same JSON-LD structure multiple times."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output: 4-5 page types max, 6-8 schema examples with shorter descriptions."
                )
            except Exception as e:
                return (False, f"Failed to parse ImplementationGuide: {e}")

        if not isinstance(result, ImplementationGuide):
            return (False, f"Invalid type: expected ImplementationGuide, got {type(result)}")

        # Validate page_type_implementations (minimum 4)
        if not result.page_type_implementations or len(result.page_type_implementations) < 4:
            return (
                False,
                f"Need at least 4 page_type_implementations, got {len(result.page_type_implementations or [])}. "
                "Create templates for Homepage, Location Pages, Profile Pages, and Content Pages."
            )

        # Validate h2_structure is array for each page type
        for page_type in result.page_type_implementations:
            if not isinstance(page_type.h2_structure, list):
                return (
                    False,
                    f"h2_structure for '{page_type.page_type}' must be a list of strings, "
                    f"got {type(page_type.h2_structure).__name__}. "
                    "Use format: [\"H2 Section 1\", \"H2 Section 2\", ...]"
                )

        # Validate schema_markup_strategy
        if not result.schema_markup_strategy:
            return (False, "Missing schema_markup_strategy - required for implementation guide")

        schema_examples = result.schema_markup_strategy.schema_examples or []
        if len(schema_examples) < 6:
            return (
                False,
                f"Need at least 6 schema_examples, got {len(schema_examples)}. "
                "Include Organization, Service, FAQ, Article, BreadcrumbList, and Person/Review schemas."
            )

        # Validate each JSON-LD example
        for schema in schema_examples:
            # Check for template variables in JSON-LD
            template_vars = _detect_template_variables(schema.json_ld_code)
            if template_vars:
                return (
                    False,
                    f"Template variables found in {schema.schema_type} JSON-LD: {template_vars}. "
                    "Replace placeholders with realistic example values "
                    "(e.g., use 'Acme Translation Services' instead of '[solution_name]')."
                )

            # Validate JSON-LD structure
            is_valid, error = _validate_json_ld(schema.json_ld_code)
            if not is_valid:
                return (
                    False,
                    f"Invalid JSON-LD for {schema.schema_type}: {error}. "
                    "Ensure JSON is complete with proper @context and closing brackets."
                )

        logger.info(
            f"✓ Implementation guide guardrail passed: "
            f"{len(result.page_type_implementations)} page types, "
            f"{len(schema_examples)} schema examples"
        )
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Implementation guide validation error: {str(e)}")


# ========================================
# TASK 5: IMPLEMENTATION GUIDE LIGHT GUARDRAIL (NEW)
# ========================================
# Validates lightweight output with schema type selections instead of JSON-LD code


def validate_implementation_guide_light_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for create_implementation_guide_task (Task 5 - LIGHTWEIGHT VERSION).

    This validates the lightweight output model where:
    - LLM provides schema TYPE selections + strategic rationale
    - Python generates actual JSON-LD code from templates after this task

    Validates:
    - 4+ page_type_implementations
    - 4+ selected_schemas in schema_markup_strategy (NOT json_ld_code)
    - Each schema selection has schema_type, priority, and strategic_rationale
    - h2_structure is array, not string

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Implementation guide returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = ImplementationGuideLight.model_validate(raw_json)
                logger.debug("Implementation guide light guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                # Check for repetition loop pattern
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED in implementation guide. "
                        "Generate UNIQUE page types and schema selections. "
                        "Do NOT repeat the same schema type multiple times."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output: 4-5 page types max, 4-8 schema selections with concise rationale."
                )
            except Exception as e:
                return (False, f"Failed to parse ImplementationGuideLight: {e}")

        if not isinstance(result, ImplementationGuideLight):
            return (False, f"Invalid type: expected ImplementationGuideLight, got {type(result)}")

        # Validate page_type_implementations (minimum 4)
        if not result.page_type_implementations or len(result.page_type_implementations) < 4:
            return (
                False,
                f"Need at least 4 page_type_implementations, got {len(result.page_type_implementations or [])}. "
                "Create templates for Homepage, Location Pages, Profile Pages, and Content Pages."
            )

        # Validate h2_structure is array for each page type
        for page_type in result.page_type_implementations:
            if not isinstance(page_type.h2_structure, list):
                return (
                    False,
                    f"h2_structure for '{page_type.page_type}' must be a list of strings, "
                    f"got {type(page_type.h2_structure).__name__}. "
                    "Use format: [\"H2 Section 1\", \"H2 Section 2\", ...]"
                )

        # Validate schema_markup_strategy (light version)
        if not result.schema_markup_strategy:
            return (False, "Missing schema_markup_strategy - required for implementation guide")

        selected_schemas = result.schema_markup_strategy.selected_schemas or []
        if len(selected_schemas) < 4:
            return (
                False,
                f"Need at least 4 selected_schemas, got {len(selected_schemas)}. "
                "Include Organization, Service, FAQPage, BreadcrumbList at minimum."
            )

        # Validate each schema selection has required fields
        seen_types = set()
        for schema in selected_schemas:
            # Check required fields
            if not schema.schema_type:
                return (False, "Schema selection missing schema_type field")
            if schema.priority is None or not (1 <= schema.priority <= 5):
                return (
                    False,
                    f"Schema '{schema.schema_type}' has invalid priority {schema.priority}. "
                    "Priority must be 1-5 (1=critical, 5=nice-to-have)."
                )
            if not schema.strategic_rationale or len(schema.strategic_rationale) < 10:
                return (
                    False,
                    f"Schema '{schema.schema_type}' needs strategic_rationale (min 10 chars), "
                    f"got '{schema.strategic_rationale or ''}'. "
                    "Explain why this schema matters for SEO."
                )

            # Check for duplicate schema types
            if schema.schema_type.lower() in seen_types:
                return (
                    False,
                    f"Duplicate schema type '{schema.schema_type}' detected. "
                    "Each schema type should appear only once in selected_schemas."
                )
            seen_types.add(schema.schema_type.lower())

        # Validate why_schema_matters narrative
        if not result.schema_markup_strategy.why_schema_matters or \
           len(result.schema_markup_strategy.why_schema_matters) < 50:
            return (
                False,
                "why_schema_matters too short (minimum 50 chars). "
                "Explain the benefits of schema markup for SEO."
            )

        logger.info(
            f"✓ Implementation guide light guardrail passed: "
            f"{len(result.page_type_implementations)} page types, "
            f"{len(selected_schemas)} schema selections"
        )
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Implementation guide light validation error: {str(e)}")


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

        # Validate technical_seo_recommendations has content
        if not result.technical_seo_recommendations or len(result.technical_seo_recommendations) < 50:
            return (
                False,
                f"technical_seo_recommendations too short ({len(result.technical_seo_recommendations or '')} chars, minimum 50). "
                "Include URL structure, schema markup, and technical recommendations."
            )

        logger.info(
            f"✓ Content strategy guardrail passed: "
            f"{len(result.topic_clusters or [])} clusters, "
            f"{len(result.keyword_based_page_types or [])} page types"
        )
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Content strategy validation error: {str(e)}")


# ========================================
# TASK 3: IMPLEMENTATION PLAN GUARDRAIL (HIGH)
# ========================================


def validate_implementation_plan_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for create_implementation_plan_task (Task 3 - HIGH).

    Validates:
    - 4+ key_metrics_to_track
    - 5+ next_steps_checklist items
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

        # Validate key_metrics_to_track (minimum 4)
        if not result.key_metrics_to_track or len(result.key_metrics_to_track) < 4:
            return (
                False,
                f"Need at least 4 key_metrics_to_track, got {len(result.key_metrics_to_track or [])}. "
                "Include SEO metrics (rankings, traffic) and business metrics (conversions, revenue)."
            )

        # Validate next_steps_checklist (minimum 5)
        if not result.next_steps_checklist or len(result.next_steps_checklist) < 5:
            return (
                False,
                f"Need at least 5 next_steps_checklist items, got {len(result.next_steps_checklist or [])}. "
                "Include actionable items for immediate implementation."
            )

        # Validate implementation_roadmap has content
        if not result.implementation_roadmap or len(result.implementation_roadmap) < 100:
            return (
                False,
                f"implementation_roadmap too short ({len(result.implementation_roadmap or '')} chars, minimum 100). "
                "Include phased plan with timelines and specific targets."
            )

        logger.info(
            f"✓ Implementation plan guardrail passed: "
            f"{len(result.key_metrics_to_track)} metrics, "
            f"{len(result.next_steps_checklist)} checklist items"
        )
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Implementation plan validation error: {str(e)}")


# ========================================
# TASK 4: FINAL SYNTHESIS GUARDRAIL (MEDIUM)
# ========================================


def validate_final_synthesis_output(task_output) -> tuple[bool, Any]:
    """
    Guardrail for synthesize_final_seo_strategy_task (Task 4 - MEDIUM).

    Validates:
    - 2+ competitive_advantages
    - 3+ critical_success_factors
    - long_term_strategy has substantial content

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Final synthesis returned empty output (no pydantic or raw)")

            try:
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = FinalSynthesis.model_validate(raw_json)
                logger.debug("Final synthesis guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                raw_sample = task_output.raw[:2000] if task_output.raw else ""
                if _detect_repetition_pattern(raw_sample):
                    return (
                        False,
                        "REPETITION LOOP DETECTED in final synthesis. "
                        "Generate UNIQUE competitive advantages and success factors."
                    )
                return (
                    False,
                    f"JSON truncated/malformed at line {e.lineno}: {e.msg}. "
                    "Reduce output: focus on key strategic insights."
                )
            except Exception as e:
                return (False, f"Failed to parse FinalSynthesis: {e}")

        if not isinstance(result, FinalSynthesis):
            return (False, f"Invalid type: expected FinalSynthesis, got {type(result)}")

        # Validate competitive_advantages (minimum 2)
        if not result.competitive_advantages or len(result.competitive_advantages) < 2:
            return (
                False,
                f"Need at least 2 competitive_advantages, got {len(result.competitive_advantages or [])}. "
                "Identify unique SEO opportunities and market positioning advantages."
            )

        # Validate critical_success_factors (minimum 3)
        if not result.critical_success_factors or len(result.critical_success_factors) < 3:
            return (
                False,
                f"Need at least 3 critical_success_factors, got {len(result.critical_success_factors or [])}. "
                "Include factors for content, technical SEO, and market execution."
            )

        # Validate long_term_strategy has content
        if not result.long_term_strategy or len(result.long_term_strategy) < 50:
            return (
                False,
                f"long_term_strategy too short ({len(result.long_term_strategy or '')} chars, minimum 50). "
                "Include Year 1/2/3 strategic milestones."
            )

        logger.info(
            f"✓ Final synthesis guardrail passed: "
            f"{len(result.competitive_advantages)} advantages, "
            f"{len(result.critical_success_factors)} success factors"
        )
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Final synthesis validation error: {str(e)}")
