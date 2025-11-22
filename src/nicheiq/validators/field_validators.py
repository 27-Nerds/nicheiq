"""
Reusable Pydantic field validators.

This module provides commonly used validators that can be reused across
Pydantic models to ensure data quality and consistency.
"""

from typing import Any, Optional


def validate_score_range(v: Any) -> float:
    """
    Validate that score is in range 0.0-1.0 and not None.

    Args:
        v: Value to validate

    Returns:
        Validated float score

    Raises:
        ValueError: If score is None or out of range
    """
    if v is None:
        raise ValueError("Score cannot be None")

    try:
        score = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"Score must be numeric, got {type(v).__name__}")

    if not 0.0 <= score <= 1.0:
        raise ValueError(f"Score must be between 0.0 and 1.0, got {score}")

    return score


def validate_optional_score_range(v: Any) -> Optional[float]:
    """
    Validate optional score is in range 0.0-1.0 (allows None).

    Args:
        v: Value to validate

    Returns:
        Validated float score or None

    Raises:
        ValueError: If score is present but out of range
    """
    if v is None:
        return None

    try:
        score = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"Score must be numeric, got {type(v).__name__}")

    if not 0.0 <= score <= 1.0:
        raise ValueError(f"Score must be between 0.0 and 1.0, got {score}")

    return score


def validate_non_negative_int(v: Any) -> int:
    """
    Validate that value is a non-negative integer.

    Args:
        v: Value to validate

    Returns:
        Validated non-negative integer

    Raises:
        ValueError: If value is negative or not an integer
    """
    if v is None:
        raise ValueError("Value cannot be None")

    try:
        count = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"Value must be integer, got {type(v).__name__}")

    if count < 0:
        raise ValueError(f"Value must be non-negative, got {count}")

    return count


def validate_non_empty_string(v: Any) -> str:
    """
    Validate that string is not None or empty.

    Args:
        v: Value to validate

    Returns:
        Validated non-empty string

    Raises:
        ValueError: If string is None, empty, or whitespace-only
    """
    if v is None:
        raise ValueError("String cannot be None")

    if not isinstance(v, str):
        raise ValueError(f"Value must be string, got {type(v).__name__}")

    if not v.strip():
        raise ValueError("String cannot be empty or whitespace-only")

    return v.strip()


def validate_optional_non_empty_string(v: Any) -> Optional[str]:
    """
    Validate optional string is not empty if present.

    Args:
        v: Value to validate

    Returns:
        Validated non-empty string or None

    Raises:
        ValueError: If string is empty or whitespace-only
    """
    if v is None:
        return None

    if not isinstance(v, str):
        raise ValueError(f"Value must be string, got {type(v).__name__}")

    stripped = v.strip()
    if not stripped:
        raise ValueError("String cannot be empty or whitespace-only")

    return stripped


def validate_percentage(v: Any) -> float:
    """
    Validate that value is a valid percentage (0.0-100.0).

    Args:
        v: Value to validate

    Returns:
        Validated percentage

    Raises:
        ValueError: If value is out of range or not numeric
    """
    if v is None:
        raise ValueError("Percentage cannot be None")

    try:
        pct = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"Percentage must be numeric, got {type(v).__name__}")

    if not 0.0 <= pct <= 100.0:
        raise ValueError(f"Percentage must be between 0.0 and 100.0, got {pct}")

    return pct


def validate_url(v: Any) -> str:
    """
    Validate that string is a valid URL.

    Args:
        v: Value to validate

    Returns:
        Validated URL string

    Raises:
        ValueError: If URL is invalid
    """
    if v is None:
        raise ValueError("URL cannot be None")

    if not isinstance(v, str):
        raise ValueError(f"URL must be string, got {type(v).__name__}")

    url = v.strip()

    if not url:
        raise ValueError("URL cannot be empty")

    # Basic URL validation (starts with http:// or https://)
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL must start with http:// or https://, got {url}")

    return url


def validate_optional_url(v: Any) -> Optional[str]:
    """
    Validate optional URL (allows None).

    Args:
        v: Value to validate

    Returns:
        Validated URL string or None

    Raises:
        ValueError: If URL is present but invalid
    """
    if v is None:
        return None

    return validate_url(v)
