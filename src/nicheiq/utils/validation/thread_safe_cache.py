"""
Thread-safe cache for parallel validation operations.

Provides thread-safe read/write access to validation cache using threading.Lock.
Used by KeywordRelevanceValidator for parallel batch processing.
"""

import threading
from typing import Any


class ThreadSafeValidationCache:
    """
    Thread-safe cache for validation results.

    Wraps a dict with a threading.Lock to prevent race conditions during
    concurrent validation operations.

    Example:
        >>> cache = ThreadSafeValidationCache()
        >>> cache.set("keyword", (True, 0.95))
        >>> is_relevant, score = cache.get("keyword")
    """

    def __init__(self, initial_cache: dict[str, tuple] | None = None):
        """
        Initialize thread-safe cache.

        Args:
            initial_cache: Optional dict to initialize cache with
        """
        self._cache = initial_cache.copy() if initial_cache else {}
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple | None:
        """
        Thread-safe get operation.

        Args:
            key: Cache key (lowercase keyword)

        Returns:
            Cached tuple (is_relevant, score) or None if not found
        """
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: tuple) -> None:
        """
        Thread-safe set operation.

        Args:
            key: Cache key (lowercase keyword)
            value: Tuple of (is_relevant, score)
        """
        with self._lock:
            self._cache[key] = value

    def get_all(self) -> dict[str, tuple]:
        """
        Thread-safe get all operation.

        Returns:
            Copy of entire cache dict
        """
        with self._lock:
            return self._cache.copy()

    def __len__(self) -> int:
        """Thread-safe length operation."""
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Thread-safe contains operation."""
        with self._lock:
            return key in self._cache
