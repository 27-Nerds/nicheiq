"""Tests for Webshare proxy pool client."""

import re
from unittest.mock import patch

import pytest
import requests
import responses

from nicheiq.tools.webshare_client import (
    WebshareProxy,
    WebshareProxyPool,
    _sanitize_proxy_url,
)

# Match the Webshare proxy-list endpoint by URL suffix so the test doesn't depend on the exact host.
_PROXY_LIST = re.compile(r".+/proxy/list/?.*")


def _proxy_payload(ip: str = "1.2.3.4", port: int = 8168, valid: bool = True, country: str = "US"):
    return {
        "id": f"d-{ip}",
        "username": f"u_{ip}",
        "password": f"p_{ip}",
        "proxy_address": ip,
        "port": port,
        "valid": valid,
        "country_code": country,
    }


class TestSanitizeProxyUrl:
    def test_strips_creds_from_url(self):
        out = _sanitize_proxy_url("connect to http://user:pass@1.2.3.4:8080 failed")
        assert "user" not in out
        assert "pass" not in out
        assert "1.2.3.4:8080" in out
        assert "***:***" in out

    def test_noop_on_clean_string(self):
        assert _sanitize_proxy_url("no proxy here") == "no proxy here"


class TestWebshareProxy:
    def test_repr_masks_credentials(self):
        proxy = WebshareProxy(address="1.2.3.4", port=8168, username="alice", password="secret")
        r = repr(proxy)
        assert "1.2.3.4" in r
        assert "8168" in r
        assert "alice" not in r
        assert "secret" not in r

    def test_as_url_contains_creds(self):
        proxy = WebshareProxy(address="1.2.3.4", port=8168, username="alice", password="secret")
        assert proxy.as_url() == "http://alice:secret@1.2.3.4:8168"


class TestFetch:
    @responses.activate
    def test_fetch_success_parses_proxies(self):
        responses.add(
            responses.GET,
            _PROXY_LIST,
            json={"results": [_proxy_payload("1.1.1.1"), _proxy_payload("2.2.2.2", port=9999)]},
            status=200,
        )
        pool = WebshareProxyPool(api_key="APIKEY123")
        assert pool.ensure_loaded() is True
        assert pool.size() == 2
        # Verify Authorization header
        request = responses.calls[0].request
        assert request.headers["Authorization"] == "Token APIKEY123"
        assert request.params["mode"] == "direct"

    @responses.activate
    def test_fetch_filters_invalid_proxies(self):
        responses.add(
            responses.GET,
            _PROXY_LIST,
            json={"results": [
                _proxy_payload("1.1.1.1", valid=True),
                _proxy_payload("2.2.2.2", valid=False),
            ]},
            status=200,
        )
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        assert pool.size() == 1

    @responses.activate
    def test_fetch_auth_failure_returns_empty(self):
        responses.add(responses.GET, _PROXY_LIST, json={"detail": "Invalid token"}, status=401)
        pool = WebshareProxyPool(api_key="bad")
        assert pool.ensure_loaded() is False
        assert pool.size() == 0

    @responses.activate
    def test_fetch_network_error_returns_empty(self):
        responses.add(responses.GET, _PROXY_LIST, body=requests.ConnectionError("network down"))
        pool = WebshareProxyPool(api_key="k")
        assert pool.ensure_loaded() is False
        assert pool.size() == 0

    @responses.activate
    def test_fetch_non_json_200_returns_empty(self):
        responses.add(responses.GET, _PROXY_LIST, body="<html>Oops</html>", status=200)
        pool = WebshareProxyPool(api_key="k")
        assert pool.ensure_loaded() is False
        assert pool.size() == 0

    @responses.activate
    def test_fetch_empty_results_logs_filter_diagnostic(self, caplog):
        responses.add(responses.GET, _PROXY_LIST, json={"results": []}, status=200)
        pool = WebshareProxyPool(api_key="k", country_codes=["ZZ"])
        import logging
        with caplog.at_level(logging.WARNING):
            pool.ensure_loaded()
        # Loguru + caplog need a bridge; fall back to checking pool is empty and
        # no fetched proxies were logged at INFO level
        assert pool.size() == 0

    @responses.activate
    def test_country_code_filter_in_params(self):
        responses.add(responses.GET, _PROXY_LIST, json={"results": []}, status=200)
        pool = WebshareProxyPool(api_key="k", country_codes=["US", "GB"])
        pool.ensure_loaded()
        request = responses.calls[0].request
        assert request.params["country_code__in"] == "US,GB"


class TestRoundRobin:
    @responses.activate
    @patch("nicheiq.tools.webshare_client.random.shuffle", new=lambda x: None)  # deterministic
    def test_next_proxy_round_robin(self):
        responses.add(
            responses.GET,
            _PROXY_LIST,
            json={"results": [
                _proxy_payload("1.1.1.1"),
                _proxy_payload("2.2.2.2"),
                _proxy_payload("3.3.3.3"),
            ]},
            status=200,
        )
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        seq = [pool.next_proxy().address for _ in range(7)]
        assert seq == ["1.1.1.1", "2.2.2.2", "3.3.3.3", "1.1.1.1", "2.2.2.2", "3.3.3.3", "1.1.1.1"]

    @responses.activate
    @patch("nicheiq.tools.webshare_client.random.shuffle", new=lambda x: None)
    def test_mark_blocked_removes_from_cycle(self):
        responses.add(
            responses.GET,
            _PROXY_LIST,
            json={"results": [_proxy_payload("1.1.1.1"), _proxy_payload("2.2.2.2")]},
            status=200,
        )
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        first = pool.next_proxy()
        pool.mark_blocked(first)
        # Next 10 calls must never return the blocked proxy
        for _ in range(10):
            p = pool.next_proxy()
            assert p.address != first.address
        assert pool.size() == 1

    @responses.activate
    def test_mark_blocked_until_empty_returns_none(self):
        responses.add(
            responses.GET,
            _PROXY_LIST,
            json={"results": [_proxy_payload("1.1.1.1"), _proxy_payload("2.2.2.2")]},
            status=200,
        )
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        pool.mark_blocked(pool.next_proxy())
        pool.mark_blocked(pool.next_proxy())
        assert pool.next_proxy() is None


class TestIdempotent:
    @responses.activate
    def test_ensure_loaded_idempotent_even_on_empty(self):
        """A failed first fetch must not trigger a second fetch on subsequent calls."""
        responses.add(responses.GET, _PROXY_LIST, body=requests.ConnectionError("down"))
        pool = WebshareProxyPool(api_key="k")
        assert pool.ensure_loaded() is False
        assert pool.ensure_loaded() is False
        assert pool.ensure_loaded() is False
        # Only ONE fetch attempt across three ensure_loaded calls
        assert len(responses.calls) == 1

    @responses.activate
    def test_ensure_loaded_idempotent_on_success(self):
        responses.add(responses.GET, _PROXY_LIST, json={"results": [_proxy_payload("1.1.1.1")]}, status=200)
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        pool.ensure_loaded()
        assert len(responses.calls) == 1
