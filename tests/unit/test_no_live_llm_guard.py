"""Drift self-test for the hermeticity guards (tests/unit/conftest.py::_no_live_llm / _no_live_http).

The guards use ``raising=False``, so a future ``openai``/``requests``/``httpx`` release that moved a
module path would make a surface a SILENT no-op. These tests intentionally trip the guards via the real
client/transport surfaces and assert the sentinel fires — if a path drifts, the real network call runs
and the expected RuntimeError never appears, failing loudly here. Each test clears the recorded hit so
the autouse teardown stays green.
"""

import pytest


def test_guard_blocks_openai_sdk(request):
    import openai
    client = openai.OpenAI(api_key="x", base_url="https://example.invalid/v1")
    with pytest.raises(RuntimeError, match="Live LLM call"):
        client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "hi"}]
        )
    getattr(request.node, "_llm_guard_hits", []).clear()


def test_guard_blocks_openai_embeddings(request):
    import openai
    client = openai.OpenAI(api_key="x", base_url="https://example.invalid/v1")
    with pytest.raises(RuntimeError, match="Live LLM call"):
        client.embeddings.create(model="text-embedding-3-small", input="hi")
    getattr(request.node, "_llm_guard_hits", []).clear()


def test_guard_blocks_langchain_chatopenai(request):
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(api_key="x", model="gpt-4o")
    with pytest.raises(Exception) as exc_info:
        llm.invoke("hi")
    assert "Live LLM call" in str(exc_info.value)
    getattr(request.node, "_llm_guard_hits", []).clear()


def test_guard_blocks_requests(request):
    import requests
    with pytest.raises(Exception) as exc_info:
        requests.get("https://example.invalid/path", timeout=5)
    assert "Live HTTP call" in str(exc_info.value)
    getattr(request.node, "_http_guard_hits", []).clear()


def test_guard_blocks_httpx(request):
    import httpx
    with pytest.raises(Exception) as exc_info:
        httpx.get("https://example.invalid/path")
    assert "Live HTTP call" in str(exc_info.value)
    getattr(request.node, "_http_guard_hits", []).clear()
