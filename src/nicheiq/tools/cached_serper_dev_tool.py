"""
CachedSerperDevTool - Wrapper around SerperDevTool with session-level caching.
Reduces redundant API calls when multiple solutions have overlapping competitors.
"""

import os
from typing import Any

import requests
from crewai_tools import SerperDevTool
from loguru import logger


class CachedSerperDevTool(SerperDevTool):
    """
    Wrapper around SerperDevTool that caches search results within a session.
    Reduces redundant API calls when multiple solutions have overlapping competitors.

    Note: crewai_tools 1.8.1 uses _run(**kwargs) internally, so we override
    _run() to intercept all searches (both from CrewAI agents and direct calls).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
        self._raw_cache = {}
        self._hits = 0
        self._misses = 0

    def _run(self, **kwargs) -> Any:
        """Execute search with caching (internal CrewAI interface)."""
        search_query = kwargs.get("search_query", "")
        cache_key = search_query.strip().lower()

        if cache_key in self._cache:
            self._hits += 1
            logger.debug(f"Cache hit for: {search_query[:50]}... (hits: {self._hits})")
            return self._cache[cache_key]

        # No lock here (deliberate, 2026-07-10 parallelization audit): the check-then-fetch is
        # not atomic, so two threads racing on the SAME cache-miss key can both call
        # super()._run() and both write self._cache[cache_key] — a double-fetch. This is
        # cost-only (an extra Serper credit) and self-healing (the cache converges to whichever
        # write lands last); it never produces a wrong or stale result, so it isn't worth a lock
        # here or in batch_run/batch_run_raw's equivalent miss-check. See the same audit for the
        # locks that WERE warranted (`_ma_search`/`_ma_search_batch` budget bookkeeping).
        self._misses += 1
        logger.debug(f"Cache miss for: {search_query[:50]}... (misses: {self._misses})")
        result = super()._run(**kwargs)
        self._cache[cache_key] = result

        return result

    def run(self, search_query: str = "", **kwargs) -> Any:
        """Execute search with caching (public interface for direct calls)."""
        kwargs["search_query"] = search_query
        return self._run(**kwargs)

    def batch_run(self, queries: list[str]) -> dict[str, str]:
        """Batched search: Serper's POST /search accepts a JSON array of up to 100
        {"q": "..."} objects and returns an array of per-query results in the same
        order (same X-API-KEY header; each element still costs 1 credit). Cache hits
        are served without hitting the network; only cache misses are sent in the
        batch POST. Fail-soft: a request-level failure resolves whatever it can from
        the cache and returns '' for every unresolved query (logs a warning).

        Returns {original_query: result_string} for every query in `queries`
        (duplicates included), using the SAME stringified format as `_run`'s cache
        entries so downstream string parsing (links, snippets) keeps working.
        """
        # Normalize + dedupe, keeping the first-seen original string per key.
        key_to_original: dict[str, str] = {}
        for q in queries:
            key = q.strip().lower()
            key_to_original.setdefault(key, q)

        key_results: dict[str, str] = {}
        misses: list[str] = []
        for key in key_to_original:
            if key in self._cache:
                self._hits += 1
                key_results[key] = str(self._cache[key])
            else:
                misses.append(key)

        if misses:
            self._misses += len(misses)
            logger.debug(f"Batch cache miss for {len(misses)} queries (misses: {self._misses})")
            raw_results: list | None = None
            try:
                search_url = self._get_search_url(self.search_type)
                payload = [{"q": key_to_original[key]} for key in misses]
                headers = {
                    "X-API-KEY": os.environ["SERPER_API_KEY"],
                    "content-type": "application/json",
                }
                response = requests.post(search_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                raw_results = response.json()
                if not isinstance(raw_results, list):
                    raise ValueError(
                        f"Expected a list response from Serper batch API, got {type(raw_results)}"
                    )
            except Exception as e:
                logger.warning(f"Serper batch request failed for {len(misses)} queries: {e}")
                raw_results = None

            if raw_results is not None:
                for idx, key in enumerate(misses):
                    original = key_to_original[key]
                    try:
                        raw_item = raw_results[idx]
                        search_query = original
                        item_params = {}
                        if isinstance(raw_item, dict):
                            item_params = raw_item.get("searchParameters", {}) or {}
                            search_query = item_params.get("q", original)
                        formatted_results: dict[str, Any] = {
                            "searchParameters": {
                                "q": search_query,
                                "type": self.search_type,
                                **item_params,
                            }
                        }
                        formatted_results.update(
                            self._process_search_results(raw_item, self.search_type)
                        )
                        formatted_results["credits"] = (
                            raw_item.get("credits", 1) if isinstance(raw_item, dict) else 1
                        )
                        result_str = str(formatted_results)
                        self._cache[key] = result_str
                        key_results[key] = result_str
                    except Exception as e:
                        logger.warning(
                            f"Failed to process batch result for query '{original}': {e}"
                        )

        return {q: key_results.get(q.strip().lower(), "") for q in queries}

    def batch_run_raw(self, queries: list[str], tbs: str | None = None) -> dict[str, dict]:
        """Same batching/dedup/fail-soft semantics as `batch_run`, but returns the
        RAW result dicts (the same shape SerperDevTool._run produces) instead of
        stringified results. Callers that feed the response straight into
        SearchHelper.extract_results_from_serper need this: that helper hard-gates
        on `isinstance(search_results, dict)` and silently returns [] for a string,
        so batch_run's stringified format won't work there.

        Cached separately from `batch_run`/`run` (self._raw_cache) so raw dicts
        never collide with batch_run's stringified cache entries under the same key.

        `tbs` (optional) is Google's date-range filter param, applied uniformly to
        every query in this batch call (mirrors SearchHelper.serper_search_with_date_filter,
        which CrewAI's SerperDevTool doesn't expose). It's folded into the cache key
        so a date-filtered pass never serves a stale cache hit from an unfiltered
        pass over the same query text (or vice versa).

        Returns {original_query: result_dict} for every query in `queries`
        (duplicates included); unresolved queries map to {} (an empty dict), which
        extract_results_from_serper safely treats as zero results — same fail-soft
        effect as today's per-query exception path, just without raising.
        """
        def _cache_key(q: str) -> str:
            norm = q.strip().lower()
            return f"{norm}|tbs={tbs}" if tbs else norm

        key_to_original: dict[str, str] = {}
        for q in queries:
            key_to_original.setdefault(_cache_key(q), q)

        key_results: dict[str, dict] = {}
        misses: list[str] = []
        for key in key_to_original:
            if key in self._raw_cache:
                self._hits += 1
                key_results[key] = self._raw_cache[key]
            else:
                misses.append(key)

        if misses:
            self._misses += len(misses)
            logger.debug(f"Batch(raw) cache miss for {len(misses)} queries (misses: {self._misses})")
            raw_results: list | None = None
            try:
                search_url = self._get_search_url(self.search_type)
                payload = [
                    {"q": key_to_original[key], **({"tbs": tbs} if tbs else {})}
                    for key in misses
                ]
                headers = {
                    "X-API-KEY": os.environ["SERPER_API_KEY"],
                    "content-type": "application/json",
                }
                response = requests.post(search_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                raw_results = response.json()
                if not isinstance(raw_results, list):
                    raise ValueError(
                        f"Expected a list response from Serper batch API, got {type(raw_results)}"
                    )
            except Exception as e:
                logger.warning(f"Serper batch(raw) request failed for {len(misses)} queries: {e}")
                raw_results = None

            if raw_results is not None:
                for idx, key in enumerate(misses):
                    original = key_to_original[key]
                    try:
                        raw_item = raw_results[idx]
                        search_query = original
                        item_params = {}
                        if isinstance(raw_item, dict):
                            item_params = raw_item.get("searchParameters", {}) or {}
                            search_query = item_params.get("q", original)
                        formatted_results: dict[str, Any] = {
                            "searchParameters": {
                                "q": search_query,
                                "type": self.search_type,
                                **item_params,
                            }
                        }
                        formatted_results.update(
                            self._process_search_results(raw_item, self.search_type)
                        )
                        formatted_results["credits"] = (
                            raw_item.get("credits", 1) if isinstance(raw_item, dict) else 1
                        )
                        self._raw_cache[key] = formatted_results
                        key_results[key] = formatted_results
                    except Exception as e:
                        logger.warning(
                            f"Failed to process batch(raw) result for query '{original}': {e}"
                        )

        return {q: key_results.get(_cache_key(q), {}) for q in queries}

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
        self._raw_cache.clear()
        self._hits = 0
        self._misses = 0
