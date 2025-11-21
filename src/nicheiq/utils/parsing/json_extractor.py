"""
JSON extraction utilities for LLM output processing.

Provides robust extraction of JSON arrays from LLM responses.
"""

import json
import re

from loguru import logger


def extract_json_array_from_text(text: str) -> list | None:
    """
    Extract first complete JSON array from text (shared utility).

    Performance optimization: Try direct parsing first, then regex, then bracket matching.

    Args:
        text: Raw text containing JSON array

    Returns:
        Parsed JSON array or None if extraction fails
    """
    # Fast path: Try direct JSON parse if text is clean
    text_stripped = text.strip()
    if text_stripped.startswith('['):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass  # Fall through to extraction methods

    # Medium path: Extract JSON with regex (handles common cases like "Here's the list: [...]")
    json_match = re.search(r'\[.*\]', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass  # Fall through to bracket matching

    # Slow path: Manual bracket matching for complex cases (brackets in strings, etc.)
    start_idx = text.find('[')
    if start_idx == -1:
        return None

    bracket_count = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start_idx:], start=start_idx):
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
                        return json.loads(text[start_idx:i+1])
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON parse failed at bracket close: {e}")
                        return None

        escape_next = False

    logger.warning("No matching closing bracket found")
    return None
