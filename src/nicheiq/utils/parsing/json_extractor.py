"""
JSON extraction utilities for LLM output processing.

Provides robust extraction of JSON arrays from LLM responses.
"""

import json
import re

from loguru import logger


def clean_llm_response(raw_text: str) -> str:
    """
    Clean LLM response by removing XML-like tags that may contain brackets.

    LLM responses may include tags like <verification>, <brief_explanation>, etc.
    that contain bracket patterns (e.g., [emotion]) which confuse JSON parsing.

    Args:
        raw_text: Raw LLM response text

    Returns:
        Cleaned text with XML-like tags removed
    """
    # Remove paired tags and their content (e.g., <verification>...</verification>)
    cleaned = re.sub(r'<[^>]+>.*?</[^>]+>', '', raw_text, flags=re.DOTALL)
    # Remove any remaining single tags (e.g., <tag>)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    return cleaned.strip()


def extract_json_object_from_text(text: str) -> dict | None:
    """
    Extract first complete JSON object from text using bracket matching.

    Handles cases where LLM output contains markdown or explanation text
    surrounding a JSON object.

    Args:
        text: Raw text potentially containing a JSON object

    Returns:
        Parsed JSON dict or None if extraction fails
    """
    cleaned_text = clean_llm_response(text)

    # Fast path: text is already clean JSON
    text_stripped = cleaned_text.strip()
    if text_stripped.startswith('{'):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass  # Fall through to bracket matching

    # Find the first '{' and use bracket matching
    start_idx = cleaned_text.find('{')
    if start_idx == -1:
        return None

    bracket_count = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(cleaned_text[start_idx:], start=start_idx):
        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string

        if not in_string:
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0:
                    candidate = cleaned_text[start_idx:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON object extraction failed at bracket close: {e}")
                        return None

    logger.warning("No matching closing brace found for JSON object")
    return None


def extract_json_array_from_text(text: str) -> list | None:
    """
    Extract first complete JSON array from text (shared utility).

    Performance optimization: Try direct parsing first, then regex, then bracket matching.

    Args:
        text: Raw text containing JSON array

    Returns:
        Parsed JSON array or None if extraction fails
    """
    # Pre-process: Strip common LLM response tags that may contain brackets
    cleaned_text = clean_llm_response(text)

    # Fast path: Try direct JSON parse if text is clean
    text_stripped = cleaned_text.strip()
    if text_stripped.startswith('['):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass  # Fall through to extraction methods

    # Medium path: Look for JSON array starting with [{ pattern (more specific than generic [)
    json_match = re.search(r'\[\s*\{.*\}\s*\]', cleaned_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass  # Fall through to bracket matching

    # Fallback: Generic array pattern
    json_match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass  # Fall through to bracket matching

    # Slow path: Manual bracket matching for complex cases (brackets in strings, etc.)
    start_idx = cleaned_text.find('[')
    if start_idx == -1:
        return None

    bracket_count = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(cleaned_text[start_idx:], start=start_idx):
        # Handle string literals (ignore brackets inside strings)
        if char == '"' and not escape_next:
            in_string = not in_string
        elif char == '\\' and in_string:
            escape_next = not escape_next
            continue

        if not in_string:
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    try:
                        return json.loads(cleaned_text[start_idx:i+1])
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON parse failed at bracket close: {e}")
                        return None

        escape_next = False

    logger.warning("No matching closing bracket found")
    return None
