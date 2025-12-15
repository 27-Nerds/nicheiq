"""
CachedSerperDevTool - Wrapper around SerperDevTool with session-level caching.
Reduces redundant API calls when multiple solutions have overlapping competitors.
"""

from crewai_tools import SerperDevTool
from loguru import logger


class CachedSerperDevTool(SerperDevTool):
    """
    Wrapper around SerperDevTool that caches search results within a session.
    Reduces redundant API calls when multiple solutions have overlapping competitors.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
        self._hits = 0
        self._misses = 0

    def run(self, search_query: str, **kwargs):
        """Execute search with caching."""
        cache_key = search_query.strip().lower()

        if cache_key in self._cache:
            self._hits += 1
            logger.debug(f"Cache hit for: {search_query[:50]}... (hits: {self._hits})")
            return self._cache[cache_key]

        self._misses += 1
        logger.debug(f"Cache miss for: {search_query[:50]}... (misses: {self._misses})")
        result = super().run(search_query, **kwargs)
        self._cache[cache_key] = result

        return result

    def get_cache_stats(self) -> dict:
        """Return cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "cached_queries": len(self._cache),
        }

    def clear_cache(self):
        """Clear the search cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
