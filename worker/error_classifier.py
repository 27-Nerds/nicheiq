"""
Error classifier for categorizing worker errors into user-friendly categories.

Classifies raw error messages into standardized error codes that can be
translated to user-friendly messages by the backend.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassifiedError:
    """Result of error classification."""
    code: str
    raw_message: str
    stage: Optional[int] = None


# Error patterns mapped to error codes
# Order matters - more specific patterns should come first
ERROR_PATTERNS: list[tuple[str, str]] = [
    # Upstream provider account exhaustion is not a product-credit error and is not fixed by
    # retrying immediately. Keep it ahead of generic auth/internal patterns so HTTP 402 remains
    # actionable all the way through the backend error translator.
    (
        r"\b402\b|payment.?required|openrouter.*(?:credit|billing)|provider.*(?:credit|billing)",
        "PROVIDER_BILLING_ERROR",
    ),

    # Rate limiting (check first as it's common)
    (r"rate.?limit|429|quota.?exceeded|too.?many.?requests|throttl", "RATE_LIMIT"),

    # Authentication/Authorization errors
    (r"unauthorized|401|403|invalid.*(api.?)?key|authentication.?fail|access.?denied|forbidden", "API_AUTH_ERROR"),

    # Network connectivity issues
    (r"connection.*(error|refused|reset|timeout)|ECONNREFUSED|ECONNRESET|ETIMEDOUT|network.?error|dns.?resolution|unreachable|socket.?error", "NETWORK_ERROR"),

    # Timeout errors (distinct from network timeouts)
    (r"timeout|timed?.?out|deadline.?exceeded|operation.?took.?too.?long", "TIMEOUT"),

    # Validation errors
    (r"validation.?error|pydantic|ValueError|invalid.?input|schema.?error|type.?error|missing.?field|required.?field", "VALIDATION_ERROR"),

    # Worker crash / process errors
    (r"worker.?shutdown|sigterm|sigint|sigkill|process.?killed|out.?of.?memory|oom|memory.?error|segmentation.?fault", "WORKER_CRASH"),

    # External service unavailable
    (r"service.?unavailable|503|502|504|bad.?gateway|upstream.?error", "SERVICE_UNAVAILABLE"),
]


def classify_error(
    error_message: str,
    error_stage: Optional[int] = None
) -> ClassifiedError:
    """
    Classify an error message into a standardized error code.

    Args:
        error_message: The raw error message/traceback
        error_stage: Optional stage number where the error occurred

    Returns:
        ClassifiedError with the error code and original message
    """
    if not error_message:
        return ClassifiedError(
            code="INTERNAL_ERROR",
            raw_message="Unknown error",
            stage=error_stage
        )

    # Normalize the message for pattern matching
    normalized = error_message.lower()

    # Try to match against known patterns
    for pattern, code in ERROR_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return ClassifiedError(
                code=code,
                raw_message=error_message,
                stage=error_stage
            )

    # Default to internal error if no pattern matches
    return ClassifiedError(
        code="INTERNAL_ERROR",
        raw_message=error_message,
        stage=error_stage
    )


def build_error_details(classified: ClassifiedError) -> dict:
    """
    Build the error details payload to send to the backend.

    Args:
        classified: The classified error

    Returns:
        Dictionary with error details for the backend
    """
    return {
        "code": classified.code,
        "rawMessage": classified.raw_message,
        "stage": classified.stage,
    }
