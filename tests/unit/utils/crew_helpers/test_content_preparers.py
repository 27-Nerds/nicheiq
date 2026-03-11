"""Tests for content_preparers - competitor intelligence sentence-level extraction."""

from datetime import datetime, timezone

import pytest

from nicheiq.models.social_content import (
    RedditComment,
    RedditPost,
    SocialContentCollection,
    TwitterThread,
    TwitterTweet,
)
from unittest.mock import patch, MagicMock

from nicheiq.utils.crew_helpers.content_preparers import (
    MAX_COMPETITOR_CONTENT_CHARS,
    ExtractedToolMention,
    ToolMentionExtractionResult,
    _INDICATOR_PATTERN,
    _boost_with_seed_list,
    _extract_relevant_sentences,
    _extract_tools_via_llm,
    _split_sentences,
    format_competitor_mentions_for_prompt,
    prepare_competitor_intelligence,
)


# ============================================================
# Helpers
# ============================================================

def _make_comment(body: str, comment_id: str = "c1", score: int = 5) -> RedditComment:
    return RedditComment(
        comment_id=comment_id,
        author="user",
        body=body,
        score=score,
        created_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_post(
    title: str = "Test Post",
    selftext: str = "",
    comments: list | None = None,
    score: int = 10,
    subreddit: str = "test",
    post_id: str = "p1",
) -> RedditPost:
    return RedditPost(
        post_id=post_id,
        title=title,
        selftext=selftext,
        author="poster",
        subreddit=subreddit,
        score=score,
        num_comments=len(comments) if comments else 0,
        created_utc=datetime(2025, 1, 15, tzinfo=timezone.utc),
        url=f"https://reddit.com/r/{subreddit}/comments/{post_id}",
        comments=comments or [],
    )


def _make_tweet(text: str, tweet_id: str = "t1", likes: int = 5) -> TwitterTweet:
    return TwitterTweet(
        tweet_id=tweet_id,
        author_username="tweeter",
        text=text,
        likes=likes,
        retweets=0,
        replies_count=0,
        created_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
        url=f"https://twitter.com/tweeter/status/{tweet_id}",
    )


def _make_thread(
    original_text: str,
    replies: list | None = None,
    thread_id: str = "th1",
    likes: int = 10,
) -> TwitterThread:
    original = _make_tweet(original_text, tweet_id=thread_id, likes=likes)
    reply_tweets = []
    for i, text in enumerate(replies or []):
        reply_tweets.append(_make_tweet(text, tweet_id=f"r{i}", likes=2))
    return TwitterThread(
        thread_id=thread_id,
        original_tweet=original,
        replies=reply_tweets,
        total_engagement=likes + sum(2 for _ in reply_tweets),
    )


def _make_collection(
    posts: list | None = None,
    threads: list | None = None,
) -> SocialContentCollection:
    return SocialContentCollection(
        reddit_posts=posts or [],
        twitter_threads=threads or [],
        total_reddit_comments=sum(len(p.comments) for p in (posts or [])),
        total_twitter_tweets=sum(1 + len(t.replies) for t in (threads or [])),
    )


# ============================================================
# _split_sentences tests
# ============================================================

class TestSplitSentences:
    def test_basic_splitting(self):
        text = "First sentence. Second sentence! Third sentence?"
        result = _split_sentences(text)
        assert len(result) == 3
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence!"
        assert result[2] == "Third sentence?"

    def test_newline_splitting(self):
        text = "First paragraph here.\n\nSecond paragraph here."
        result = _split_sentences(text)
        assert len(result) == 2

    def test_url_stripping(self):
        """URLs should be replaced with [URL] so dots don't cause bad splits."""
        text = "Check out https://www.example.com/path/to/page.html for more info. It works great."
        result = _split_sentences(text)
        # Should NOT split at each dot in the URL
        assert any("[URL]" in s for s in result)
        # Should still split at the period after "info"
        assert len(result) == 2

    def test_short_sentences_filtered(self):
        """Sentences shorter than 15 chars are skipped."""
        text = "OK. This is a longer sentence that should be kept."
        result = _split_sentences(text)
        assert len(result) == 1
        assert "longer sentence" in result[0]

    def test_empty_input(self):
        assert _split_sentences("") == []
        assert _split_sentences("   ") == []


# ============================================================
# _extract_relevant_sentences tests
# ============================================================

class TestExtractRelevantSentences:
    def test_basic_extraction(self):
        text = (
            "I love pottery. "
            "I tried this tool and it was amazing. "
            "The weather is nice."
        )
        result = _extract_relevant_sentences(text, _INDICATOR_PATTERN)
        assert "tried this tool" in result
        # Should NOT include the pottery or weather sentences without context overlap
        # (they may be included as context depending on proximity)

    def test_word_boundary_no_false_positive(self):
        """'app' should NOT match inside 'happy' due to \\b word boundaries."""
        text = "I am happy with my life. The sunset is beautiful over the mountains."
        result = _extract_relevant_sentences(text, _INDICATOR_PATTERN)
        assert result == ""

    def test_word_boundary_matches_app(self):
        """'app' SHOULD match as a standalone word."""
        text = "I found a great app for tracking expenses. It changed my workflow completely."
        result = _extract_relevant_sentences(text, _INDICATOR_PATTERN)
        assert "great app" in result

    def test_context_sentences_included(self):
        """Matching sentence should include surrounding context."""
        text = (
            "Background information here. "
            "More context about the topic. "
            "I switched from ToolA to ToolB last week. "
            "It was much better for my use case. "
            "Unrelated ending here."
        )
        result = _extract_relevant_sentences(text, _INDICATOR_PATTERN, context_sentences=2)
        # The matching sentence ("switched from") plus 2 before and 2 after
        assert "switched from" in result
        assert "Background information" in result  # 2 sentences before
        assert "better for my use case" in result  # 1 sentence after (context)

    def test_empty_text(self):
        assert _extract_relevant_sentences("", _INDICATOR_PATTERN) == ""
        assert _extract_relevant_sentences(None, _INDICATOR_PATTERN) == ""

    def test_no_matches(self):
        text = "The cat sat on the mat. It was a sunny day in the park."
        result = _extract_relevant_sentences(text, _INDICATOR_PATTERN)
        assert result == ""

    def test_adjacent_matches_grouped(self):
        """Multiple adjacent matches should be grouped into one excerpt."""
        text = (
            "This tool is expensive. "
            "The subscription costs too much. "
            "I found an alternative that is cheaper. "
            "Completely different topic here."
        )
        result = _extract_relevant_sentences(text, _INDICATOR_PATTERN)
        # All three matching sentences should be in one group, not separated by "..."
        assert "..." not in result or result.count("...") == 0


# ============================================================
# prepare_competitor_intelligence tests
# ============================================================

class TestPrepareCompetitorIntelligence:
    def test_empty_input(self):
        assert prepare_competitor_intelligence(None) == ""

    def test_no_posts(self):
        collection = _make_collection()
        assert prepare_competitor_intelligence(collection) == ""

    def test_no_matches_returns_empty(self):
        """Posts with no competitor mentions should return empty."""
        post = _make_post(
            title="My Garden",
            selftext="I planted tomatoes in my garden. The weather was perfect.",
        )
        collection = _make_collection(posts=[post])
        assert prepare_competitor_intelligence(collection) == ""

    def test_reddit_extraction(self):
        post = _make_post(
            title="Best project management tools",
            selftext="I currently use Jira but I'm looking for an alternative. The pricing is too expensive for my small team.",
            comments=[
                _make_comment("I switched from Jira to Linear. Much better experience."),
                _make_comment("Try Notion, it has a free tier that works well."),
            ],
        )
        collection = _make_collection(posts=[post])
        result = prepare_competitor_intelligence(collection)

        assert result != ""
        assert "r/test" in result
        assert "alternative" in result or "expensive" in result

    def test_twitter_extraction(self):
        thread = _make_thread(
            original_text="Just tried this new SaaS tool for email automation. Game changer!",
            replies=["I recommend checking out their pricing page first."],
        )
        collection = _make_collection(threads=[thread])
        result = prepare_competitor_intelligence(collection)

        assert result != ""
        assert "tool" in result.lower() or "recommend" in result.lower()

    def test_content_cap_enforcement(self):
        """Output should not exceed MAX_COMPETITOR_CONTENT_CHARS."""
        # Create many posts with long competitor-relevant content
        posts = []
        for i in range(100):
            posts.append(_make_post(
                post_id=f"p{i}",
                title=f"Tool comparison #{i}",
                selftext=(
                    "I have been using this software platform for years. "
                    "The subscription pricing is expensive compared to alternatives. "
                    "I recommend trying the free trial first before upgrading. "
                ) * 20,  # ~3K chars per post
                score=100 - i,
            ))
        collection = _make_collection(posts=posts)
        result = prepare_competitor_intelligence(collection)

        assert len(result) <= MAX_COMPETITOR_CONTENT_CHARS + 1000  # Some buffer for separators

    def test_comment_cap_per_post(self):
        """No more than MAX_COMMENT_EXCERPTS_PER_POST comment excerpts per post."""
        comments = [
            _make_comment(
                f"I recommend tool {i} as an alternative to the current software.",
                comment_id=f"c{i}",
            )
            for i in range(20)
        ]
        post = _make_post(
            title="Software recommendations",
            selftext="Looking for project management tools.",
            comments=comments,
        )
        collection = _make_collection(posts=[post])
        result = prepare_competitor_intelligence(collection)

        # Count comment excerpts (lines starting with "- ")
        comment_lines = [line for line in result.split("\n") if line.startswith("- ")]
        assert len(comment_lines) <= 8

    def test_mixed_reddit_twitter(self):
        post = _make_post(
            title="Tool recommendations",
            selftext="I need a good automation platform for my workflow.",
        )
        thread = _make_thread(
            original_text="This SaaS tool has the best pricing I've seen.",
        )
        collection = _make_collection(posts=[post], threads=[thread])
        result = prepare_competitor_intelligence(collection)

        assert result != ""
        assert "===" in result  # Separator between entries

    def test_domain_hint_matching(self):
        """Product URLs like slack.com should be detected."""
        post = _make_post(
            title="Communication tools",
            selftext="We moved our team to slack.com last month. The integration with other services is solid.",
        )
        collection = _make_collection(posts=[post])
        result = prepare_competitor_intelligence(collection)
        assert result != ""


# ============================================================
# _extract_tools_via_llm tests
# ============================================================

_MOCK_PATCH_LLM = "nicheiq.utils.llm_service.LLMService.invoke_structured"


def _mock_invoke_result(mentions):
    """Create a mock return value for LLMService.invoke_structured."""
    result = ToolMentionExtractionResult(mentions=mentions)
    usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return result, usage


class TestExtractToolsViaLLM:
    """Tests for LLM-based tool extraction."""

    @patch(_MOCK_PATCH_LLM)
    def test_basic_extraction(self, mock_invoke):
        mock_invoke.return_value = _mock_invoke_result([
            ExtractedToolMention(name="Notion", category="software"),
            ExtractedToolMention(name="Ahrefs", category="software"),
        ])

        mentions = [
            ("I switched from Notion to something else.", "r/test", 10),
            ("Ahrefs is great for SEO.", "r/seo", 20),
        ]
        result = _extract_tools_via_llm(mentions)
        assert len(result) == 2
        assert result[0].name == "Notion"

    @patch(_MOCK_PATCH_LLM)
    def test_deduplicates_sentences(self, mock_invoke):
        mock_invoke.return_value = _mock_invoke_result([])

        mentions = [
            ("I tried this tool today.", "r/test", 10),
            ("I tried this tool today.", "r/test", 5),  # duplicate
            ("Different sentence about a tool.", "r/test", 8),
        ]
        _extract_tools_via_llm(mentions)

        # Check the prompt sent to LLM has only 2 unique sentences
        call_args = mock_invoke.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert prompt.count("[1]") == 1
        assert prompt.count("[2]") == 1
        assert "[3]" not in prompt

    @patch(_MOCK_PATCH_LLM)
    def test_retries_on_failure(self, mock_invoke):
        """Should retry once on failure."""
        mock_invoke.side_effect = [
            Exception("API error"),
            _mock_invoke_result([
                ExtractedToolMention(name="Notion", category="software"),
            ]),
        ]

        mentions = [("I use Notion for notes.", "r/test", 10)]
        result = _extract_tools_via_llm(mentions)
        assert len(result) == 1
        assert mock_invoke.call_count == 2

    @patch(_MOCK_PATCH_LLM)
    def test_raises_after_two_failures(self, mock_invoke):
        mock_invoke.side_effect = Exception("API error")

        mentions = [("I use Notion for notes.", "r/test", 10)]
        with pytest.raises(Exception, match="API error"):
            _extract_tools_via_llm(mentions)
        assert mock_invoke.call_count == 2

    @patch(_MOCK_PATCH_LLM)
    def test_caps_at_80_sentences(self, mock_invoke):
        mock_invoke.return_value = _mock_invoke_result([])

        mentions = [
            (f"Sentence {i} about some tool.", "r/test", i)
            for i in range(200)
        ]
        _extract_tools_via_llm(mentions)

        call_args = mock_invoke.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "[80]" in prompt
        assert "[81]" not in prompt


# ============================================================
# _boost_with_seed_list tests
# ============================================================

class TestBoostWithSeedList:
    def test_adds_known_tools(self):
        tool_map: dict[str, list] = {}
        all_mentions = [
            ("I really like using Jira for project management.", "r/pm", 10),
            ("Linear is a great alternative.", "r/pm", 8),
        ]
        _boost_with_seed_list(tool_map, all_mentions, ["Jira", "Linear"])
        assert "Jira" in tool_map
        assert "Linear" in tool_map

    def test_skips_already_present(self):
        tool_map = {"Notion": [("I use Notion daily.", "r/test", 10)]}
        all_mentions = [("I use Notion daily.", "r/test", 10)]
        _boost_with_seed_list(tool_map, all_mentions, ["Notion"])
        # Should not duplicate
        assert len(tool_map["Notion"]) == 1

    def test_skips_unmatched_tools(self):
        tool_map: dict[str, list] = {}
        all_mentions = [("I use Notion daily.", "r/test", 10)]
        _boost_with_seed_list(tool_map, all_mentions, ["Ahrefs"])
        assert "Ahrefs" not in tool_map


# ============================================================
# format_competitor_mentions_for_prompt tests
# ============================================================

class TestFormatCompetitorMentionsForPrompt:
    def test_empty_input(self):
        assert format_competitor_mentions_for_prompt(None) == "No competitor data available"

    def test_no_posts(self):
        collection = _make_collection()
        assert format_competitor_mentions_for_prompt(collection) == "No competitor data available"

    @patch("nicheiq.utils.crew_helpers.content_preparers._extract_tools_via_llm")
    def test_llm_extraction_used(self, mock_extract):
        """Should call LLM extraction and format results."""
        mock_extract.return_value = [
            ExtractedToolMention(name="Notion", category="software"),
        ]
        post = _make_post(
            title="Best tools for work",
            selftext="I currently use Notion for project management. Looking for an alternative.",
        )
        collection = _make_collection(posts=[post])
        result = format_competitor_mentions_for_prompt(collection)

        mock_extract.assert_called_once()
        assert "Notion" in result
        assert "No competitor data available" not in result

    @patch("nicheiq.utils.crew_helpers.content_preparers._extract_tools_via_llm")
    def test_llm_failure_falls_back_to_seed_list(self, mock_extract):
        """When LLM fails, should fall back to seed list."""
        mock_extract.side_effect = Exception("API error")
        post = _make_post(
            title="Best tools for work",
            selftext="I currently use Jira for tracking. Looking for an alternative to Jira.",
            comments=[
                _make_comment("Jira is expensive, try Linear instead."),
            ],
        )
        collection = _make_collection(posts=[post])
        result = format_competitor_mentions_for_prompt(
            collection, known_tools=["Jira", "Linear"]
        )

        assert "Jira" in result

    @patch("nicheiq.utils.crew_helpers.content_preparers._extract_tools_via_llm")
    def test_seed_list_boosts_missing_tools(self, mock_extract):
        """Seed list should add tools that LLM missed."""
        mock_extract.return_value = [
            ExtractedToolMention(name="Notion", category="software"),
        ]
        post = _make_post(
            title="Best tools for work",
            selftext="I currently use Notion and Linear as my main tools. Looking for an alternative to both.",
        )
        collection = _make_collection(posts=[post])
        result = format_competitor_mentions_for_prompt(
            collection, known_tools=["Linear"]
        )

        assert "Notion" in result
        assert "Linear" in result

    @patch("nicheiq.utils.crew_helpers.content_preparers._extract_tools_via_llm")
    def test_frequent_vs_occasional_grouping(self, mock_extract):
        """Tools with 3+ mentions should be in 'Frequently mentioned' group."""
        mock_extract.return_value = [
            ExtractedToolMention(name="Notion", category="software"),
        ]
        posts = [
            _make_post(
                post_id=f"p{i}",
                title="Best tools",
                selftext="I currently use Notion. It's a great tool for my workflow.",
                score=10,
            )
            for i in range(5)
        ]
        collection = _make_collection(posts=posts)
        result = format_competitor_mentions_for_prompt(collection)

        assert "Frequently mentioned" in result
        assert "Notion" in result

    @patch("nicheiq.utils.crew_helpers.content_preparers._extract_tools_via_llm")
    def test_max_entries_respected(self, mock_extract):
        """Should not exceed max_entries."""
        mock_extract.return_value = [
            ExtractedToolMention(name=f"Tool{i}", category="software")
            for i in range(20)
        ]
        post = _make_post(
            title="Tools comparison",
            selftext=" ".join(
                f"I tried Tool{i} and it's interesting." for i in range(20)
            ),
        )
        collection = _make_collection(posts=[post])
        result = format_competitor_mentions_for_prompt(collection, max_entries=5)

        # Count bullet points
        bullets = [l for l in result.split("\n") if l.startswith("- ")]
        assert len(bullets) <= 5

    @patch("nicheiq.utils.crew_helpers.content_preparers._extract_tools_via_llm")
    def test_no_matches_returns_no_data(self, mock_extract):
        """If no indicator sentences match, return no data."""
        post = _make_post(
            title="My garden",
            selftext="I planted tomatoes in my garden. The weather was perfect.",
        )
        collection = _make_collection(posts=[post])
        result = format_competitor_mentions_for_prompt(collection)

        assert result == "No competitor data available"
        mock_extract.assert_not_called()
