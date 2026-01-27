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
import re
from typing import Any

from loguru import logger

# Pre-compiled regex patterns for JSON error fixing (performance optimization)
_SINGLE_LINE_COMMENT_RE = re.compile(r'//[^\n]*')
_MULTI_LINE_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r',(\s*[}\]])')

from ...models.competitor import CompetitiveAnalysisResult
from ...models.data_source import SourceEvaluationReport
from ...models.pain_point import ContentCategorizationReport
from ...models.research_state import AudienceMappingResult
from ...models.seo_strategy import (
    CategoryLightResult,
    ContentStrategyResultLight,
    FinalSynthesis,
    GeographicLightResult,
    ImplementationPlanResult,
    StrategicLightResult,
)
from ...models.solution_idea import (
    FilteredConceptList,
    IdeaGenerationResult,
    RawConceptList,
)
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
        if not result.tier_4_category_groups or len(result.tier_4_category_groups) < 3:
            return (
                False,
                f"Need at least 3 category groups, got {len(result.tier_4_category_groups or [])}. "
                "Analyze the keywords and create meaningful thematic groups."
            )

        # Check for duplicate keywords across groups (sign of repetition issue)
        all_keywords = []
        for group in result.tier_4_category_groups:
            # CategoryLightEntry has keyword_name field
            all_keywords.extend(kw.keyword_name.lower().strip() for kw in group.keywords)

        unique_keywords = set(all_keywords)
        if len(unique_keywords) < len(all_keywords) * 0.7:  # >30% duplicates
            return (
                False,
                f"Too many duplicate keywords across groups ({len(all_keywords) - len(unique_keywords)} duplicates). "
                "Each keyword should appear in only ONE category group."
            )

        logger.info(f"✓ Category tier guardrail passed: {len(result.tier_4_category_groups)} groups")
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
                    f"Too many duplicate keywords in geographic groups. "
                    "Each location keyword should appear in only ONE region."
                )

        logger.info(f"✓ Geographic tier guardrail passed: {len(result.tier_3_geographic_groups or [])} regions")
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


# validate_implementation_guide_output and validate_implementation_guide_light_output
# removed - Task 5 deleted, technical SEO is now in Task 2's technical_seo_recommendations


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
    - conclusion_bottom_line has substantial content (minimum 50 chars)

    Note: competitive_advantages, critical_success_factors, and long_term_strategy
    were removed from FinalSynthesis model as they were redundant with other fields
    (competitive_positioning, implementation_roadmap, etc.)

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
                        "Generate a UNIQUE conclusion with key strategic insights."
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

        # Validate conclusion_bottom_line has substantial content (minimum 50 chars)
        if not result.conclusion_bottom_line or len(result.conclusion_bottom_line) < 50:
            return (
                False,
                f"conclusion_bottom_line too short ({len(result.conclusion_bottom_line or '')} chars, minimum 50). "
                "Provide a comprehensive summary of the SEO strategy and key recommendations."
            )

        logger.info(
            f"✓ Final synthesis guardrail passed: "
            f"conclusion has {len(result.conclusion_bottom_line)} chars"
        )
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Final synthesis validation error: {str(e)}")


# ========================================
# HELPER: FIX COMMON JSON ERRORS
# ========================================


def _fix_common_json_errors(raw_json: str) -> str:
    """
    Attempt to fix common JSON errors from LLM output.

    Fixes:
    - Trailing commas before } or ]
    - JavaScript-style comments

    Args:
        raw_json: Raw JSON string that may contain errors

    Returns:
        Cleaned JSON string
    """
    # Remove JavaScript-style comments using pre-compiled patterns
    cleaned = _SINGLE_LINE_COMMENT_RE.sub('', raw_json)
    cleaned = _MULTI_LINE_COMMENT_RE.sub('', cleaned)

    # Fix trailing commas before } or ]
    cleaned = _TRAILING_COMMA_RE.sub(r'\1', cleaned)

    return cleaned


def _parse_pydantic_from_task_output(task_output, model_class, task_name: str) -> tuple[Any | None, str | None]:
    """
    Unified helper to parse Pydantic model from task output.

    CrewAI 1.7.0 Compatibility: When guardrails exist, pydantic=None by design.
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

        # CrewAI 1.7.0: pydantic is None when guardrails exist, parse from .raw
        if not hasattr(task_output, 'raw') or not task_output.raw:
            return (None, f"{task_name} returned empty output (no pydantic or raw)")

        try:
            # Clean and fix common JSON errors
            cleaned_raw = clean_llm_response(task_output.raw)
            cleaned_raw = _fix_common_json_errors(cleaned_raw)
            raw_json = json.loads(cleaned_raw)
            result = model_class.model_validate(raw_json)
            logger.debug(f"{task_name} guardrail: Parsed {model_class.__name__} from .raw")
            return (result, None)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in {task_name}: {e}")
            return (
                None,
                f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}. "
                "Ensure valid JSON with no trailing commas and double-quoted strings. "
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
    - Each theme has at least 3 representative_quotes
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

    # Validate each theme has at least 3 representative_quotes
    # Note: Prompt targets 5-10 quotes, but guardrail minimum is 3 to avoid hallucination pressure
    for theme in result.theme_categories:
        if not theme.representative_quotes or len(theme.representative_quotes) < 3:
            return (
                False,
                f"Theme '{theme.category_name}' needs at least 3 representative_quotes, "
                f"got {len(theme.representative_quotes or [])}. "
                "Include quotes from discussions WITH [source: ID] tags to support this theme."
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
    return (True, task_output.raw)


# ========================================
# UNIFIED SOLUTION CREW: RAW CONCEPTS GUARDRAIL
# ========================================


def validate_raw_concepts(task_output) -> tuple[bool, Any]:
    """
    Guardrail for divergent_exploration_task to validate RawConceptList.

    Validates:
    - JSON is parseable (via unified helper)
    - Has 8-12 concepts (minimum 6)
    - Each concept has name, one_liner, target_keywords (2-5)

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    # Parse using unified helper
    result, error = _parse_pydantic_from_task_output(
        task_output, RawConceptList, "Divergent exploration"
    )
    if error:
        return (False, error)

    # Validate concept count (8-12 expected, minimum 6)
    if not result.concepts or len(result.concepts) < 6:
        return (
            False,
            f"Need at least 6 concepts (target 8-12), got {len(result.concepts or [])}. "
            "Generate more diverse solution concepts using different ideation techniques."
        )

    # Validate each concept has required fields
    for i, concept in enumerate(result.concepts):
        if not concept.concept_name or len(concept.concept_name.strip()) < 3:
            return (False, f"Concept {i+1} missing or too short concept_name")
        if not concept.one_liner or len(concept.one_liner.strip()) < 20:
            return (
                False,
                f"Concept '{concept.concept_name}' has missing or too short one_liner "
                f"(needs 20+ chars, got {len(concept.one_liner or '')}). "
                "Describe what the solution does and why it's interesting."
            )
        if not concept.target_keywords or len(concept.target_keywords) < 2:
            return (
                False,
                f"Concept '{concept.concept_name}' needs at least 2 target_keywords, "
                f"got {len(concept.target_keywords or [])}. "
                "Add specific SEO keywords this solution would target."
            )

    logger.info(f"✓ Raw concepts guardrail passed: {len(result.concepts)} concepts")
    return (True, task_output.raw)


# ========================================
# UNIFIED SOLUTION CREW: FILTERED CONCEPTS GUARDRAIL
# ========================================


def validate_filtered_concepts(task_output) -> tuple[bool, Any]:
    """
    Guardrail for diversity_filtering_task to validate FilteredConceptList.

    Validates:
    - JSON is parseable (via unified helper)
    - Has concepts list (3-8 expected, minimum 3)
    - Has removed_concepts with matching explanations

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    # Parse using unified helper
    result, error = _parse_pydantic_from_task_output(
        task_output, FilteredConceptList, "Diversity filtering"
    )
    if error:
        return (False, error)

    # Validate concept count (3-8 expected, minimum 3)
    if not result.concepts or len(result.concepts) < 3:
        return (
            False,
            f"Need at least 3 filtered concepts, got {len(result.concepts or [])}. "
            "Keep more diverse concepts that represent different approaches."
        )

    # Validate removed_concepts/removal_reasons consistency
    # Note: Both can be empty if all concepts are unique, but counts must match
    removed_count = len(result.removed_concepts or [])
    reasons_count = len(result.removal_reasons or [])
    if removed_count != reasons_count:
        return (
            False,
            f"Mismatch between removed_concepts ({removed_count}) "
            f"and removal_reasons ({reasons_count}). "
            "Each removed concept needs a corresponding reason."
        )

    # Validate diversity_summary exists
    if not result.diversity_summary or len(result.diversity_summary) < 30:
        return (
            False,
            f"diversity_summary too short ({len(result.diversity_summary or '')} chars, minimum 30). "
            "Summarize the project types and data sources represented."
        )

    logger.info(
        f"✓ Filtered concepts guardrail passed: "
        f"{len(result.concepts)} kept, {len(result.removed_concepts or [])} removed"
    )
    return (True, task_output.raw)


# ========================================
# AUDIENCE MAPPING CREW: AUDIENCE MAPPING GUARDRAIL
# ========================================


def validate_audience_mapping(task_output) -> tuple[bool, Any]:
    """
    Guardrail for audience_mapping_task to validate AudienceMappingResult.

    Validates:
    - JSON is parseable (via unified helper)
    - Has at least 2 audience_segments
    - Has required fields: primary_target_segment, key_influencers, community_hubs

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    # Parse using unified helper
    result, error = _parse_pydantic_from_task_output(
        task_output, AudienceMappingResult, "Audience mapping"
    )
    if error:
        return (False, error)

    # Validate minimum audience_segments (at least 2)
    if not result.audience_segments or len(result.audience_segments) < 2:
        return (
            False,
            f"Need at least 2 audience_segments, got {len(result.audience_segments or [])}. "
            "Identify more distinct audience segments from the discussions."
        )

    # Validate primary_target_segment exists
    if not result.primary_target_segment or len(result.primary_target_segment.strip()) < 3:
        return (
            False,
            "Missing or empty primary_target_segment. "
            "Identify the recommended primary target segment name."
        )

    # Validate key_influencers (at least 3)
    if not result.key_influencers or len(result.key_influencers) < 3:
        return (
            False,
            f"Need at least 3 key_influencers, got {len(result.key_influencers or [])}. "
            "Identify more influencers or active community members from discussions."
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
        f"{len(result.audience_segments)} segments, {len(result.key_influencers)} influencers"
    )
    return (True, task_output.raw)


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
    return (True, task_output.raw)
