"""
Text validation utilities for report generation.

This module provides validators for text processing, keyword matching,
and formatting operations used throughout report generation.
"""

import re
from typing import Optional


class TextValidator:
    """
    Reusable text validation and processing utilities.

    Provides word-aware matching, truncation, and other text operations
    used in report generation.
    """

    @staticmethod
    def has_score_keywords(text: str) -> bool:
        """
        Check if text contains score-related keywords using word boundaries.

        Prevents false positives from substring matches (e.g., "score" in "underscore").

        Args:
            text: Text to search for keywords

        Returns:
            True if any score-related keyword is found
        """
        if not text:
            return False

        text_lower = text.lower()

        # Use word boundaries to prevent false matches
        score_patterns = [
            r"\bmarket\s+fit\b",  # "market fit" (two words)
            r"\bcompetitive\b",
            r"\bfeasibility\b",
            r"\bseo\b",
            r"\bscore\b",
        ]

        return any(
            re.search(pattern, text_lower, re.IGNORECASE) for pattern in score_patterns
        )

    @staticmethod
    def has_numeric_score(text: str) -> bool:
        """
        Check if text contains numeric score pattern (0.XX or 1.00).

        Args:
            text: Text to search for numeric scores

        Returns:
            True if numeric score pattern found
        """
        if not text:
            return False

        # Match scores like 0.75, 0.80, 1.00 (positive values only)
        return bool(re.search(r"(?<![-.0-9])[01]\.\d{2}\b", text))

    @staticmethod
    def truncate_at_word_boundary(
        text: str,
        max_length: int,
        suffix: str = "...",
    ) -> str:
        """
        Truncate text at word boundary for clean appearance.

        Args:
            text: Text to truncate
            max_length: Maximum character length (including suffix)
            suffix: String to append when truncated (default: "...")

        Returns:
            Truncated text ending at word boundary, or original if within limit
        """
        if not text or len(text) <= max_length:
            return text

        # Reserve space for suffix
        truncate_at = max_length - len(suffix)

        # Find last space before truncate point
        last_space = text.rfind(" ", 0, truncate_at)

        if last_space > 0:
            # Truncate at word boundary
            return text[:last_space] + suffix
        else:
            # No space found, truncate at character limit
            return text[:truncate_at] + suffix

    @staticmethod
    def extract_solution_name_base(solution_name: str) -> str:
        """
        Extract base solution name without punctuation or formatting.

        Handles cases like:
        - "ReliabilityRank: Description" -> "reliabilityrank"
        - "AI-Powered@Solution#1" -> "aipoweredsolution1"

        Args:
            solution_name: Full solution name

        Returns:
            Lowercase alphanumeric base name
        """
        if not solution_name:
            return ""

        # For names with colon or dash separator, take only the part before separator
        if ":" in solution_name:
            base = solution_name.split(":")[0]
        elif " - " in solution_name:
            base = solution_name.split(" - ")[0]
        else:
            # Otherwise use the full name
            base = solution_name

        # Remove all non-alphanumeric characters and convert to lowercase
        return re.sub(r"[^a-zA-Z0-9]", "", base).lower()

    @staticmethod
    def validate_keyword_density(
        text: str,
        keywords: list[str],
        max_density: float = 0.03,
    ) -> tuple[bool, float, Optional[str]]:
        """
        Validate that keyword density doesn't exceed threshold.

        Args:
            text: Text to analyze
            keywords: List of keywords to check
            max_density: Maximum allowed density (default: 3%)

        Returns:
            Tuple of (passes_validation, actual_density, warning_message)
        """
        if not text or not keywords:
            return (True, 0.0, None)

        # Count total words
        words = text.lower().split()
        total_words = len(words)

        if total_words == 0:
            return (True, 0.0, None)

        # Count keyword occurrences
        keyword_count = sum(
            words.count(keyword.lower()) for keyword in keywords
        )

        # Calculate density
        density = keyword_count / total_words

        # Validate
        passes = density <= max_density
        warning = None if passes else f"Keyword density {density:.1%} exceeds {max_density:.1%}"

        return (passes, density, warning)
