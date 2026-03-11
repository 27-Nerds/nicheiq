"""
DataForSEO API endpoint-aware rate limiter.

Module-level singleton shared across all DataForSEO tool instances.
Avoids Pydantic model issues since DataForSEO tools extend BaseTool.
"""

import time
import threading
from collections import deque

from loguru import logger


class EndpointRateLimiter:
    """Sliding window rate limiter for DataForSEO API endpoints."""

    def __init__(self):
        self._windows: dict[str, deque] = {}
        self._lock = threading.Lock()
        self._limits = {
            "google_ads_live": (10, 60),   # 12/min limit, 10 for safety
            "dataforseo_labs": (25, 60),   # 30 simultaneous, conservative
            "default": (100, 60),
        }

    def _get_category(self, endpoint: str) -> str:
        if "/keywords_data/google_ads/" in endpoint and "/live" in endpoint:
            return "google_ads_live"
        if "/dataforseo_labs/" in endpoint:
            return "dataforseo_labs"
        return "default"

    def wait_if_needed(self, endpoint: str) -> float:
        """Block until request is allowed. Returns total seconds waited."""
        category = self._get_category(endpoint)
        max_requests, window_secs = self._limits[category]
        total_waited = 0.0

        while True:
            with self._lock:
                if category not in self._windows:
                    self._windows[category] = deque()
                window = self._windows[category]
                now = time.monotonic()
                while window and window[0] <= now - window_secs:
                    window.popleft()
                if len(window) < max_requests:
                    window.append(now)
                    return total_waited
                wait_time = window[0] + window_secs - now + 0.1

            # Sleep OUTSIDE lock to avoid RuntimeError on interrupt
            logger.info(
                f"[Rate Limit] {category}: waiting {wait_time:.1f}s "
                f"({len(window)}/{max_requests} in window)"
            )
            time.sleep(wait_time)
            total_waited += wait_time

    def reset(self):
        """Reset all windows. For testing only."""
        with self._lock:
            self._windows.clear()


# Module-level singleton
dataforseo_rate_limiter = EndpointRateLimiter()
