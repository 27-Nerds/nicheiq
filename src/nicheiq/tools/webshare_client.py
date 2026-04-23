"""Webshare proxy pool client.

Fetches direct-mode proxies via Webshare's management API and hands them
out round-robin to transcript-fetch workers. Single instantiation per
research job — no long-lived caching.
"""
from __future__ import annotations

import itertools
import random
import re
import threading
from dataclasses import dataclass, field

import requests
from loguru import logger

_API_URL = "https://proxy.webshare.io/api/v2/proxy/list/"
_DEFAULT_TIMEOUT = (5, 15)  # (connect, read) seconds


def _sanitize_proxy_url(text: str) -> str:
    """Strip embedded user:pass from proxy URLs in arbitrary strings."""
    return re.sub(r"://[^:/@\s]+:[^@/\s]+@", "://***:***@", text)


@dataclass(frozen=True)
class WebshareProxy:
    address: str
    port: int
    username: str = field(repr=False)
    password: str = field(repr=False)
    country_code: str | None = None

    def as_url(self) -> str:
        return f"http://{self.username}:{self.password}@{self.address}:{self.port}"


class WebshareProxyPool:
    """Thread-safe round-robin pool over Webshare direct-mode proxies."""

    def __init__(
        self,
        api_key: str,
        country_codes: list[str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._country_codes = country_codes
        self._lock = threading.Lock()
        self._proxies: list[WebshareProxy] = []
        self._iter: "itertools.cycle[WebshareProxy] | None" = None
        self._fetched = False

    def ensure_loaded(self) -> bool:
        """Fetch proxy list on first use. Returns True if pool is usable.

        Guards against transient Webshare outages retrying 25× per batch.
        """
        with self._lock:
            if self._fetched:
                return bool(self._proxies)
            self._fetched = True
            try:
                self._proxies = self._fetch()
                random.shuffle(self._proxies)
                self._iter = itertools.cycle(self._proxies) if self._proxies else None
            except Exception as exc:
                logger.warning(f"[Webshare] Pool init failed unexpectedly: {exc}")
                self._proxies = []
                self._iter = None
            return bool(self._proxies)

    def next_proxy(self) -> WebshareProxy | None:
        with self._lock:
            if not self._proxies or self._iter is None:
                return None
            return next(self._iter)

    def mark_blocked(self, proxy: WebshareProxy) -> None:
        with self._lock:
            if proxy in self._proxies:
                self._proxies.remove(proxy)
                self._iter = itertools.cycle(self._proxies) if self._proxies else None
                logger.info(
                    f"[Webshare] Retired blocked proxy {proxy.address}:{proxy.port} "
                    f"({len(self._proxies)} remaining)"
                )

    def size(self) -> int:
        with self._lock:
            return len(self._proxies)

    def _fetch(self) -> list[WebshareProxy]:
        params: dict[str, str | int] = {"mode": "direct", "page_size": 100}
        if self._country_codes:
            params["country_code__in"] = ",".join(self._country_codes)
        try:
            resp = requests.get(
                _API_URL,
                headers={"Authorization": f"Token {self._api_key}"},
                params=params,
                timeout=_DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning(f"[Webshare] Proxy list fetch failed: {exc}")
            return []

        if resp.status_code == 401:
            logger.warning("[Webshare] API key rejected (401). Falling back to direct fetch.")
            return []
        if resp.status_code != 200:
            logger.warning(
                f"[Webshare] Proxy list returned {resp.status_code}: {resp.text[:200]}"
            )
            return []

        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning(f"[Webshare] Non-JSON 200 response: {exc}")
            return []

        results = data.get("results", [])
        proxies = [
            WebshareProxy(
                address=item["proxy_address"],
                port=int(item["port"]),
                username=item["username"],
                password=item["password"],
                country_code=item.get("country_code"),
            )
            for item in results
            if item.get("valid", True) and item.get("proxy_address")
        ]
        if not proxies and results == []:
            logger.warning(
                f"[Webshare] API returned 0 proxies "
                f"(filter={self._country_codes!r}, mode=direct). "
                "Check plan type (residential/backbone users need a different integration path) "
                "or broaden the country filter."
            )
        else:
            logger.info(f"[Webshare] Loaded {len(proxies)} valid proxies from pool")
        return proxies
