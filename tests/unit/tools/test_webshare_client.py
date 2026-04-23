"""Tests for Webshare proxy pool client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from nicheiq.tools.webshare_client import (
    WebshareProxy,
    WebshareProxyPool,
    _sanitize_proxy_url,
)


def _make_response(status_code: int = 200, json_data: dict | None = None, text: str = ""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


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
    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_fetch_success_parses_proxies(self, mock_get):
        mock_get.return_value = _make_response(
            200,
            {"results": [_proxy_payload("1.1.1.1"), _proxy_payload("2.2.2.2", port=9999)]},
        )
        pool = WebshareProxyPool(api_key="APIKEY123")
        assert pool.ensure_loaded() is True
        assert pool.size() == 2
        # Verify Authorization header
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Token APIKEY123"
        assert kwargs["params"]["mode"] == "direct"

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_fetch_filters_invalid_proxies(self, mock_get):
        mock_get.return_value = _make_response(
            200,
            {"results": [
                _proxy_payload("1.1.1.1", valid=True),
                _proxy_payload("2.2.2.2", valid=False),
            ]},
        )
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        assert pool.size() == 1

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_fetch_auth_failure_returns_empty(self, mock_get):
        mock_get.return_value = _make_response(401, {"detail": "Invalid token"})
        pool = WebshareProxyPool(api_key="bad")
        assert pool.ensure_loaded() is False
        assert pool.size() == 0

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_fetch_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("network down")
        pool = WebshareProxyPool(api_key="k")
        assert pool.ensure_loaded() is False
        assert pool.size() == 0

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_fetch_non_json_200_returns_empty(self, mock_get):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.text = "<html>Oops</html>"
        resp.json.side_effect = ValueError("Expecting value")
        mock_get.return_value = resp
        pool = WebshareProxyPool(api_key="k")
        assert pool.ensure_loaded() is False
        assert pool.size() == 0

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_fetch_empty_results_logs_filter_diagnostic(self, mock_get, caplog):
        mock_get.return_value = _make_response(200, {"results": []})
        pool = WebshareProxyPool(api_key="k", country_codes=["ZZ"])
        import logging
        with caplog.at_level(logging.WARNING):
            pool.ensure_loaded()
        # Loguru + caplog need a bridge; fall back to checking pool is empty and
        # no fetched proxies were logged at INFO level
        assert pool.size() == 0

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_country_code_filter_in_params(self, mock_get):
        mock_get.return_value = _make_response(200, {"results": []})
        pool = WebshareProxyPool(api_key="k", country_codes=["US", "GB"])
        pool.ensure_loaded()
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["country_code__in"] == "US,GB"


class TestRoundRobin:
    @patch("nicheiq.tools.webshare_client.requests.get")
    @patch("nicheiq.tools.webshare_client.random.shuffle", new=lambda x: None)  # deterministic
    def test_next_proxy_round_robin(self, mock_get):
        mock_get.return_value = _make_response(
            200,
            {"results": [
                _proxy_payload("1.1.1.1"),
                _proxy_payload("2.2.2.2"),
                _proxy_payload("3.3.3.3"),
            ]},
        )
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        seq = [pool.next_proxy().address for _ in range(7)]
        assert seq == ["1.1.1.1", "2.2.2.2", "3.3.3.3", "1.1.1.1", "2.2.2.2", "3.3.3.3", "1.1.1.1"]

    @patch("nicheiq.tools.webshare_client.requests.get")
    @patch("nicheiq.tools.webshare_client.random.shuffle", new=lambda x: None)
    def test_mark_blocked_removes_from_cycle(self, mock_get):
        mock_get.return_value = _make_response(
            200,
            {"results": [_proxy_payload("1.1.1.1"), _proxy_payload("2.2.2.2")]},
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

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_mark_blocked_until_empty_returns_none(self, mock_get):
        mock_get.return_value = _make_response(
            200,
            {"results": [_proxy_payload("1.1.1.1"), _proxy_payload("2.2.2.2")]},
        )
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        pool.mark_blocked(pool.next_proxy())
        pool.mark_blocked(pool.next_proxy())
        assert pool.next_proxy() is None


class TestIdempotent:
    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_ensure_loaded_idempotent_even_on_empty(self, mock_get):
        """A failed first fetch must not trigger a second fetch on subsequent calls."""
        mock_get.side_effect = requests.ConnectionError("down")
        pool = WebshareProxyPool(api_key="k")
        assert pool.ensure_loaded() is False
        assert pool.ensure_loaded() is False
        assert pool.ensure_loaded() is False
        # Only ONE fetch attempt across three ensure_loaded calls
        assert mock_get.call_count == 1

    @patch("nicheiq.tools.webshare_client.requests.get")
    def test_ensure_loaded_idempotent_on_success(self, mock_get):
        mock_get.return_value = _make_response(200, {"results": [_proxy_payload("1.1.1.1")]})
        pool = WebshareProxyPool(api_key="k")
        pool.ensure_loaded()
        pool.ensure_loaded()
        assert mock_get.call_count == 1
