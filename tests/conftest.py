"""
Pytest configuration and shared fixtures.
"""

# Disable CrewAI / OpenTelemetry background analytics BEFORE any import pulls in crewai — otherwise it
# spawns a background thread that POSTs telemetry to a live endpoint, which the HTTP guard flags
# (intermittently, against whichever test happens to be running). Must precede the nicheiq imports.
import os

os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from pydantic import BaseModel, Field

from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult, OpportunityLevel
from nicheiq.models.social_content import RedditPost, RedditComment, TwitterTweet, TwitterThread
from nicheiq.models.research_state import ResearchState


@pytest.fixture
def sample_pain_point():
    """Fixture providing a sample PainPoint."""
    return PainPoint(
        title="Manual data entry consuming hours daily",
        description="Users report spending 3-5 hours on repetitive manual data entry tasks",
        mention_count=25,
        severity_score=0.85,
        commercial_intent=0.75,
        representative_quotes=[
            "I waste 4 hours daily on data entry",
            "This manual process is killing my productivity",
            "Would pay for good automation here",
        ],
        source_platforms=["reddit", "twitter"],
        categories=["workflow inefficiency", "time waste"],
        opportunity_level=OpportunityLevel.HIGH,
    )


@pytest.fixture
def sample_reddit_post():
    """Fixture providing a sample RedditPost."""
    comment = RedditComment(
        comment_id="comment1",
        author="testuser",
        body="This is a test comment discussing the problem",
        score=10,
        created_utc=datetime.now(),
        is_submitter=False,
        replies=[],
    )

    return RedditPost(
        post_id="post123",
        title="Looking for solutions to manual data entry",
        selftext="I spend hours every day manually entering data. Any recommendations?",
        author="originaluser",
        subreddit="productivity",
        score=50,
        num_comments=15,
        created_utc=datetime.now(),
        url="https://reddit.com/r/productivity/comments/post123",
        comments=[comment],
    )


@pytest.fixture
def sample_twitter_thread():
    """Fixture providing a sample TwitterThread."""
    tweet = TwitterTweet(
        tweet_id="123456789",
        author_username="testuser",
        text="Spent 3 hours on manual data entry today. There has to be a better way! #productivity",
        likes=100,
        retweets=25,
        replies_count=10,
        created_at=datetime.now(),
        url="https://twitter.com/testuser/status/123456789",
        is_reply=False,
        parent_tweet_id=None,
    )

    return TwitterThread(
        thread_id="123456789",
        original_tweet=tweet,
        replies=[],
        total_engagement=125,
    )


@pytest.fixture
def sample_pain_point_analysis():
    """Fixture providing a sample PainPointAnalysisResult."""
    pain_points = [
        PainPoint(
            title="Manual data entry time waste",
            description="Users spend excessive time on manual entry",
            mention_count=30,
            severity_score=0.85,
            commercial_intent=0.75,
            representative_quotes=["Quote 1", "Quote 2"],
            source_platforms=["reddit"],
            categories=["workflow"],
            opportunity_level=OpportunityLevel.HIGH,
        ),
        PainPoint(
            title="Poor integration between tools",
            description="Tools don't talk to each other",
            mention_count=20,
            severity_score=0.70,
            commercial_intent=0.65,
            representative_quotes=["Quote 3"],
            source_platforms=["twitter"],
            categories=["integration"],
            opportunity_level=OpportunityLevel.MEDIUM,
        ),
    ]

    return PainPointAnalysisResult(
        niche="test niche",
        pain_points=pain_points,
        total_mentions=50,
        top_categories=["workflow", "integration"],
        analysis_summary="Identified 2 key pain points with strong market signals",
    )


# LLM Testing Fixtures
class TestLLMModel(BaseModel):
    """Simple Pydantic model for LLM testing."""
    text: str = Field(..., description="Test text field")
    count: int = Field(..., description="Test count field")


@pytest.fixture
def mock_chat_openai():
    """Mock ChatOpenAI for LLM testing."""
    with patch('nicheiq.utils.llm_service.ChatOpenAI') as mock:
        # Mock for invoke_structured
        mock_structured_result = TestLLMModel(text="test response", count=42)
        mock_structured_llm = Mock()
        mock_structured_llm.invoke.return_value = mock_structured_result
        mock.return_value.with_structured_output.return_value = mock_structured_llm

        # Mock for invoke_plain
        mock_plain_result = Mock()
        mock_plain_result.content = "test plain response"
        mock.return_value.invoke.return_value = mock_plain_result

        yield mock


@pytest.fixture
def mock_llm_logger():
    """Mock logger for LLM testing."""
    with patch('nicheiq.utils.llm_service.logger') as mock:
        yield mock


@pytest.fixture
def mock_llm_settings():
    """Mock settings for LLM testing."""
    with patch('nicheiq.utils.llm_service.settings') as mock:
        mock.openai_model_name = "gpt-4o"
        mock.openai_api_key = "sk-test-key-12345"
        mock.thread_validation_llm = "gpt-4o-mini"
        mock.keyword_validation_llm = "gpt-4o-mini"
        yield mock


# Checkpoint Testing Fixtures
@pytest.fixture
def checkpoint_temp_dir(tmp_path):
    """Create temporary checkpoint directory structure."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


@pytest.fixture
def valid_checkpoint_metadata():
    """Fixture providing valid checkpoint metadata."""
    return {
        "niche_description": "AI-powered productivity tools for remote teams",
        "allowed_project_types": None,
        "started_at": "2025-01-15T10:30:00",
        "current_stage": 3,
        "completed_stages": ["stage_2_social_content", "stage_3_pain_points"],
        "errors": [],
        "last_checkpoint_at": "2025-01-15T11:00:00",
        "environment": {"python_version": "3.11.0"}
    }


@pytest.fixture
def invalid_metadata_missing_fields():
    """Checkpoint metadata missing required fields."""
    return {
        "niche_description": "Test niche",
        # Missing: started_at, current_stage
    }


@pytest.fixture
def invalid_metadata_wrong_types():
    """Checkpoint metadata with incorrect field types."""
    return {
        "niche_description": 12345,  # Should be string
        "started_at": "2025-01-15T10:30:00",
        "current_stage": "invalid",  # Should be numeric
    }


@pytest.fixture
def invalid_metadata_out_of_range():
    """Checkpoint metadata with out-of-range stage."""
    return {
        "niche_description": "Test niche",
        "started_at": "2025-01-15T10:30:00",
        "current_stage": 99,  # Out of valid range (1-14)
    }


@pytest.fixture
def valid_stage_data_dict():
    """Valid stage data as dictionary."""
    return {
        "pain_points": [
            {
                "title": "Manual data entry",
                "description": "Time-consuming process",
                "mention_count": 25,
                "severity_score": 0.85
            }
        ],
        "total_mentions": 25
    }


@pytest.fixture
def valid_stage_data_list():
    """Valid stage data as list."""
    return [
        {"keyword": "productivity tool", "volume": 5000, "difficulty": 0.45},
        {"keyword": "remote collaboration", "volume": 3200, "difficulty": 0.55}
    ]


@pytest.fixture
def sample_research_state():
    """Fixture providing a sample ResearchState."""
    return ResearchState()


@pytest.fixture
def populated_checkpoint_folder(checkpoint_temp_dir, valid_checkpoint_metadata, valid_stage_data_dict):
    """Create a fully populated checkpoint folder."""
    niche_slug = "ai_powered_productivity_tools"
    checkpoint_folder = checkpoint_temp_dir / f"checkpoint_{niche_slug}_20250115_103000"
    checkpoint_folder.mkdir()

    # Write metadata
    metadata_file = checkpoint_folder / "metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(valid_checkpoint_metadata, f, indent=2)

    # Write stage files
    stage_files = {
        "stage_2_social_content.json": {"posts": [], "tweets": []},
        "stage_3_pain_points.json": valid_stage_data_dict
    }

    for filename, data in stage_files.items():
        stage_file = checkpoint_folder / filename
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    return checkpoint_folder


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test (requires API keys)")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# ── Hermeticity guards (TREE-WIDE) ──────────────────────────────────────────────────────────────
# Defined here (tests/ root), not in tests/unit/, so NO test anywhere under tests/ can make a live
# LLM/HTTP call — a future tests/integration/ dir or a stray top-level test can't silently escape.
# A test that genuinely needs the network opts out explicitly with @pytest.mark.integration.

@pytest.fixture(autouse=True)
def _no_live_llm(request, monkeypatch):
    """No test may make a LIVE LLM call. Patches the OpenAI SDK network methods (the floor for BOTH
    the direct-SDK path and langchain ChatOpenAI) to RECORD the attempt and raise. Recording + a
    teardown assertion is essential because the production code fail-opens (``except Exception``) and
    would otherwise swallow a plain raise, leaving a leaking test silently green. Tests that mock the
    LLM never reach these methods. @pytest.mark.integration tests opt out (they require API keys)."""
    if request.node.get_closest_marker("integration"):
        yield
        return
    hits: list[str] = []

    def _blocker(surface: str):
        def _f(*_a, **_k):
            hits.append(surface)
            raise RuntimeError(f"Live LLM call ({surface}) in {request.node.nodeid} — add a mock.")
        return _f

    import openai.resources.chat.completions as _cc
    import openai.resources.beta.chat.completions as _bcc   # json_schema structured path uses .parse
    import openai.resources.embeddings as _emb
    import openai.resources.responses as _resp               # codex_llm Responses API (latent)

    for cls, meth, name in [
        (_cc.Completions, "create", "chat.completions.create"),
        (_cc.AsyncCompletions, "create", "chat.completions.acreate"),
        (_bcc.Completions, "parse", "beta.chat.completions.parse"),
        (_bcc.AsyncCompletions, "parse", "beta.chat.completions.aparse"),
        (_emb.Embeddings, "create", "embeddings.create"),
        (_emb.AsyncEmbeddings, "create", "embeddings.acreate"),
        (_resp.Responses, "create", "responses.create"),
        (_resp.AsyncResponses, "create", "responses.acreate"),
    ]:
        monkeypatch.setattr(cls, meth, _blocker(name), raising=False)

    # langchain floor (defined on BaseChatOpenAI) — clearer error, fires before beta.parse.
    try:
        from langchain_openai.chat_models.base import BaseChatOpenAI
        monkeypatch.setattr(BaseChatOpenAI, "_generate", _blocker("ChatOpenAI._generate"), raising=False)
        monkeypatch.setattr(BaseChatOpenAI, "_agenerate", _blocker("ChatOpenAI._agenerate"), raising=False)
    except Exception:
        pass

    # Exposed so the guard's own drift self-test (test_no_live_llm_guard.py) can clear it after
    # intentionally tripping the guard to prove it still blocks.
    request.node._llm_guard_hits = hits

    yield

    if hits:
        pytest.fail(
            f"{request.node.nodeid} attempted live LLM call(s): {sorted(set(hits))} — add a mock."
        )


@pytest.fixture(autouse=True)
def _no_live_http(request, monkeypatch):
    """No test may make a LIVE HTTP call. Blocks the TRANSPORT layer of ``requests`` (HTTPAdapter.send)
    and ``httpx`` (sync + async transports) — the floor every Serper / DataForSEO / Reddit / Webshare /
    backend call funnels through. Tests that patch a higher-level symbol never reach the transport.
    Records + fails in teardown (a swallowed exception can't hide a leak). Integration tests opt out."""
    if request.node.get_closest_marker("integration"):
        yield
        return
    hits: list[str] = []

    def _blocker(surface: str):
        def _f(_self, *a, **k):
            req = a[0] if a else k.get("request")
            url = getattr(req, "url", None)
            target = f" -> {str(url).split('?')[0]}" if url else ""
            hits.append(surface + target)
            raise RuntimeError(f"Live HTTP call ({surface}{target}) in {request.node.nodeid} — add a mock.")
        return _f

    try:
        import requests.adapters
        monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", _blocker("requests"), raising=False)
    except Exception:
        pass
    try:
        import httpx
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocker("httpx.sync"), raising=False)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _blocker("httpx.async"), raising=False)
    except Exception:
        pass

    # Exposed so the guard's own drift self-test can clear it after intentionally tripping the guard.
    request.node._http_guard_hits = hits

    yield

    if hits:
        pytest.fail(
            f"{request.node.nodeid} attempted live HTTP call(s): {sorted(set(hits))} — add a mock."
        )
