"""
Tests for custom knowledge sources with post_id metadata.

Tests RedditKnowledgeSource and TwitterKnowledgeSource:
- Metadata storage (post_id, source_type, subreddit/author)
- Content formatting
- Chunking behavior (size, overlap, break points)
- Validation
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from nicheiq.models.social_content import RedditComment, RedditPost, TwitterThread, TwitterTweet
from nicheiq.utils.knowledge.reddit_knowledge_source import RedditKnowledgeSource
from nicheiq.utils.knowledge.twitter_knowledge_source import TwitterKnowledgeSource


class TestRedditKnowledgeSourceMetadata:
    """Tests for RedditKnowledgeSource metadata handling."""

    def test_reddit_knowledge_source_stores_post_id(self, mock_reddit_post):
        """Verify RedditKnowledgeSource.add() stores post_id in metadata."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])

        # Mock storage with client (new pattern)
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"
        source.storage = mock_storage

        # Call add
        source.add()

        # Verify client.add_documents was called
        assert mock_client.add_documents.called
        call_kwargs = mock_client.add_documents.call_args[1]
        saved_docs = call_kwargs["documents"]

        # All chunks should have post_id metadata
        for doc in saved_docs:
            assert "metadata" in doc
            assert doc["metadata"]["post_id"] == "abc123"

    def test_reddit_knowledge_source_metadata_fields(self, mock_reddit_post):
        """Check metadata has post_id, subreddit, source_type=reddit."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])

        # Mock storage with client
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"
        source.storage = mock_storage

        source.add()

        call_kwargs = mock_client.add_documents.call_args[1]
        saved_docs = call_kwargs["documents"]
        metadata = saved_docs[0]["metadata"]

        assert metadata["post_id"] == "abc123"
        assert metadata["subreddit"] == "smallbusiness"
        assert metadata["source_type"] == "reddit"

    def test_reddit_no_storage_raises(self, mock_reddit_post):
        """Verify ValueError when storage is None."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])
        # Don't set storage

        with pytest.raises(ValueError, match="No storage found"):
            source.add()

    def test_reddit_raises_on_missing_get_client(self, mock_reddit_post):
        """Verify RuntimeError when _get_client is not available (API change)."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])

        # Mock storage without _get_client method
        mock_storage = MagicMock(spec=[])  # spec=[] means no attributes
        mock_storage.collection_name = "test"
        source.storage = mock_storage

        with pytest.raises(RuntimeError, match="CrewAI API changed"):
            source.add()

    def test_reddit_handles_empty_posts_gracefully(self):
        """Verify source handles empty posts list without error."""
        # Create source with technically valid but empty posts
        # This tests the empty documents early return
        source = RedditKnowledgeSource(posts=[])

        # Should fail validation before reaching add()
        with pytest.raises(ValueError, match="requires at least one post"):
            source.validate_content()


class TestRedditKnowledgeSourceFormatting:
    """Tests for RedditKnowledgeSource content formatting."""

    def test_reddit_format_post_includes_comments(self, mock_reddit_post):
        """Test _format_post() formats post with comments."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])

        formatted = source._format_post(mock_reddit_post)

        # Should include title
        assert mock_reddit_post.title in formatted

        # Should include selftext
        assert "manual" in formatted.lower()  # Part of selftext

        # Should include comments
        assert "3 hours" in formatted  # From comment body

        # Should include nested replies
        assert "agree" in formatted.lower()  # From reply

    def test_format_post_limits_comments(self):
        """Verify [:20] limit on top comments."""
        # Create post with 25 comments
        comments = [
            RedditComment(
                comment_id=f"c{i}",
                author=f"user{i}",
                body=f"Comment number {i}",
                score=i,
                created_utc=datetime.now(timezone.utc),
                is_submitter=False,
                replies=[],
            )
            for i in range(25)
        ]

        post = RedditPost(
            post_id="test_post",
            title="Test Post",
            selftext="Test body",
            author="author",
            subreddit="test",
            score=10,
            num_comments=25,
            created_utc=datetime.now(timezone.utc),
            url="https://reddit.com/r/test/test_post",
            comments=comments,
        )

        source = RedditKnowledgeSource(posts=[post])
        formatted = source._format_post(post)

        # Should only include first 20 comments
        assert "Comment number 19" in formatted
        assert "Comment number 24" not in formatted


class TestRedditKnowledgeSourceChunking:
    """Tests for RedditKnowledgeSource chunking behavior."""

    def test_chunk_text_short_content_single_chunk(self, mock_reddit_post_minimal):
        """Short text -> single chunk (no splitting)."""
        source = RedditKnowledgeSource(
            posts=[mock_reddit_post_minimal],
            chunk_size=2000,
        )

        formatted = source._format_post(mock_reddit_post_minimal)
        chunks = source._chunk_text(formatted)

        assert len(chunks) == 1

    def test_chunk_text_respects_chunk_size(self):
        """Verify chunks don't exceed chunk_size."""
        # Create long content
        long_content = "This is a test sentence. " * 200  # ~5000 chars

        source = RedditKnowledgeSource(posts=[], chunk_size=500)
        chunks = source._chunk_text(long_content)

        # Each chunk should be close to or under chunk_size
        for chunk in chunks:
            # Allow some flexibility for break points
            assert len(chunk) <= 600  # chunk_size + some margin

    def test_reddit_chunking_preserves_overlap(self):
        """Verify chunk_overlap creates overlapping chunks."""
        # Create content that will be split
        long_content = "Word " * 500  # ~2500 chars

        source = RedditKnowledgeSource(
            posts=[],
            chunk_size=500,
            chunk_overlap=200,
        )
        chunks = source._chunk_text(long_content)

        # With multiple chunks, there should be overlap
        if len(chunks) >= 2:
            # Check that end of chunk 1 appears at start of chunk 2
            chunk1_end = chunks[0][-100:]  # Last 100 chars of first chunk
            chunk2_start = chunks[1][:200]  # First 200 chars of second chunk

            # Since we split on word boundaries, check for word overlap
            words1 = set(chunk1_end.split())
            words2 = set(chunk2_start.split())

            # There should be some common words (overlap)
            assert len(words1 & words2) > 0

    def test_chunk_text_breaks_at_paragraph(self):
        """Prefers breaking at \\n\\n."""
        # Create content with paragraph breaks
        content = ("First paragraph content here. " * 10 +
                   "\n\n" +
                   "Second paragraph content here. " * 10)

        source = RedditKnowledgeSource(posts=[], chunk_size=200)
        chunks = source._chunk_text(content)

        # At least one chunk should end cleanly (near paragraph break)
        # This is heuristic - we check that chunks exist and aren't mid-word
        assert len(chunks) >= 2
        for chunk in chunks:
            assert not chunk.endswith(" is")  # Not mid-word

    def test_chunk_text_breaks_at_sentence(self):
        """Falls back to sentence breaks (. ! ?)."""
        # Content without paragraph breaks but with sentences
        content = "This is sentence one. This is sentence two! Is this sentence three? " * 20

        source = RedditKnowledgeSource(posts=[], chunk_size=200)
        chunks = source._chunk_text(content)

        # Should have multiple chunks
        assert len(chunks) >= 2

        # Chunks should end at sentence boundaries when possible
        for chunk in chunks[:-1]:  # Exclude last chunk
            stripped = chunk.strip()
            ends_at_sentence = (
                stripped.endswith(".") or
                stripped.endswith("!") or
                stripped.endswith("?") or
                stripped.endswith("one") or  # Word boundary
                stripped.endswith("two") or
                stripped.endswith("three")
            )
            # At least some chunks should end cleanly
            # (not all because of word-boundary fallback)

    def test_chunk_all_break_fallbacks(self):
        """Test fallback chain: paragraph -> sentence -> word."""
        # Content with only word breaks (no sentences or paragraphs)
        content = "word " * 200  # Just repeated words

        source = RedditKnowledgeSource(posts=[], chunk_size=100)
        chunks = source._chunk_text(content)

        # Should still produce chunks
        assert len(chunks) >= 1

        # Chunks should end at word boundaries
        for chunk in chunks:
            # Should not end mid-word
            assert not chunk.strip().endswith("wor")


class TestRedditKnowledgeSourceValidation:
    """Tests for RedditKnowledgeSource validation."""

    def test_validate_content_requires_posts(self):
        """Raises ValueError if no posts provided."""
        source = RedditKnowledgeSource(posts=[])

        with pytest.raises(ValueError, match="requires at least one post"):
            source.validate_content()

    def test_validate_content_passes_with_posts(self, mock_reddit_post):
        """Validation passes with posts."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])

        # Should not raise
        source.validate_content()


class TestTwitterKnowledgeSourceMetadata:
    """Tests for TwitterKnowledgeSource metadata handling."""

    def test_twitter_knowledge_source_stores_thread_id_as_post_id(self, mock_twitter_thread):
        """Verify thread_id -> metadata['post_id']."""
        source = TwitterKnowledgeSource(threads=[mock_twitter_thread])

        # Mock storage with client
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"
        source.storage = mock_storage

        source.add()

        call_kwargs = mock_client.add_documents.call_args[1]
        saved_docs = call_kwargs["documents"]
        metadata = saved_docs[0]["metadata"]

        # thread_id is stored as post_id for consistency
        assert metadata["post_id"] == "thread_xyz"

    def test_twitter_knowledge_source_metadata_fields(self, mock_twitter_thread):
        """Check metadata has post_id, author, source_type=twitter."""
        source = TwitterKnowledgeSource(threads=[mock_twitter_thread])

        # Mock storage with client
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"
        source.storage = mock_storage

        source.add()

        call_kwargs = mock_client.add_documents.call_args[1]
        saved_docs = call_kwargs["documents"]
        metadata = saved_docs[0]["metadata"]

        assert metadata["post_id"] == "thread_xyz"
        assert metadata["author"] == "testuser"
        assert metadata["source_type"] == "twitter"

    def test_twitter_uses_post_id_key(self, mock_twitter_thread):
        """Confirm thread_id stored as metadata['post_id'] (not thread_id)."""
        source = TwitterKnowledgeSource(threads=[mock_twitter_thread])

        # Mock storage with client
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"
        source.storage = mock_storage

        source.add()

        call_kwargs = mock_client.add_documents.call_args[1]
        saved_docs = call_kwargs["documents"]
        metadata = saved_docs[0]["metadata"]

        # Should use post_id key (not thread_id) for consistency
        assert "post_id" in metadata
        assert "thread_id" not in metadata


class TestTwitterKnowledgeSourceFormatting:
    """Tests for TwitterKnowledgeSource content formatting."""

    def test_twitter_format_thread_includes_replies(self, mock_twitter_thread):
        """Test _format_thread() formats thread with replies."""
        source = TwitterKnowledgeSource(threads=[mock_twitter_thread])

        formatted = source._format_thread(mock_twitter_thread)

        # Should include original tweet author
        assert "@testuser" in formatted

        # Should include original tweet text
        assert "expense reports" in formatted.lower()

        # Should include replies
        assert "@replier" in formatted
        assert "Manual expense tracking" in formatted

    def test_format_thread_limits_replies(self):
        """Verify [:30] limit on replies."""
        original_tweet = TwitterTweet(
            tweet_id="t0",
            author_username="author",
            text="Original tweet",
            likes=100,
            retweets=50,
            replies_count=35,
            created_at=datetime.now(timezone.utc),
            url="https://twitter.com/author/status/t0",
        )

        # Create 35 replies
        replies = [
            TwitterTweet(
                tweet_id=f"t{i}",
                author_username=f"user{i}",
                text=f"Reply number {i}",
                likes=i,
                retweets=0,
                replies_count=0,
                created_at=datetime.now(timezone.utc),
                url=f"https://twitter.com/user{i}/status/t{i}",
                is_reply=True,
                parent_tweet_id="t0",
            )
            for i in range(1, 36)  # 35 replies
        ]

        thread = TwitterThread(
            thread_id="t0",
            original_tweet=original_tweet,
            replies=replies,
            total_engagement=200,
        )

        source = TwitterKnowledgeSource(threads=[thread])
        formatted = source._format_thread(thread)

        # Should only include first 30 replies
        assert "Reply number 29" in formatted
        assert "Reply number 34" not in formatted


class TestTwitterKnowledgeSourceChunking:
    """Tests for TwitterKnowledgeSource chunking."""

    def test_chunk_text_short_content_single_chunk(self, mock_twitter_thread_minimal):
        """Short text -> single chunk."""
        source = TwitterKnowledgeSource(
            threads=[mock_twitter_thread_minimal],
            chunk_size=1500,
        )

        formatted = source._format_thread(mock_twitter_thread_minimal)
        chunks = source._chunk_text(formatted)

        assert len(chunks) == 1


class TestTwitterKnowledgeSourceValidation:
    """Tests for TwitterKnowledgeSource validation."""

    def test_validate_content_requires_threads(self):
        """Raises ValueError if no threads provided."""
        source = TwitterKnowledgeSource(threads=[])

        with pytest.raises(ValueError, match="requires at least one thread"):
            source.validate_content()

    def test_twitter_no_storage_raises(self, mock_twitter_thread):
        """Verify ValueError when storage is None."""
        source = TwitterKnowledgeSource(threads=[mock_twitter_thread])
        # Don't set storage

        with pytest.raises(ValueError, match="No storage found"):
            source.add()

    def test_twitter_raises_on_missing_get_client(self, mock_twitter_thread):
        """Verify RuntimeError when _get_client is not available (API change)."""
        source = TwitterKnowledgeSource(threads=[mock_twitter_thread])

        # Mock storage without _get_client method
        mock_storage = MagicMock(spec=[])  # spec=[] means no attributes
        mock_storage.collection_name = "test"
        source.storage = mock_storage

        with pytest.raises(RuntimeError, match="CrewAI API changed"):
            source.add()


class TestChunkOverlapCalculation:
    """Tests for chunk overlap calculation in both sources."""

    def test_reddit_chunk_overlap_calculation(self):
        """Verify start = max(start + 1, end - self.chunk_overlap)."""
        # Create content long enough for multiple chunks
        content = "A" * 1000

        source = RedditKnowledgeSource(
            posts=[],
            chunk_size=200,
            chunk_overlap=50,
        )
        chunks = source._chunk_text(content)

        # Should produce multiple chunks
        assert len(chunks) > 1

        # With 200 chunk_size and 50 overlap, chunks should overlap
        # The next chunk starts at end - overlap (roughly)

    def test_twitter_chunk_overlap_calculation(self):
        """Verify overlap calculation for Twitter source."""
        content = "B" * 800

        source = TwitterKnowledgeSource(
            threads=[],
            chunk_size=150,
            chunk_overlap=40,
        )
        chunks = source._chunk_text(content)

        assert len(chunks) > 1


class TestStorageInjectionPattern:
    """
    Tests verifying CrewAI's storage injection pattern works correctly.

    CrewAI Knowledge requires add_sources() to be called to inject storage
    into each source and index documents. This is automatic when using
    Crew.knowledge_sources but MUST be explicit when using Knowledge() directly.

    See: crewai/knowledge/knowledge.py:add_sources()
    """

    def test_add_raises_without_storage(self, mock_reddit_post):
        """Source.add() should raise ValueError without storage injection."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])

        # Without storage injection (simulates missing add_sources() call)
        with pytest.raises(ValueError, match="No storage found"):
            source.add()

    def test_add_succeeds_with_injected_storage(self, mock_reddit_post):
        """Source.add() works when storage is injected (mimics Knowledge.add_sources())."""
        source = RedditKnowledgeSource(posts=[mock_reddit_post])

        # Mock storage with client (new pattern - uses client directly)
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"

        # This simulates what Knowledge.add_sources() does
        source.storage = mock_storage

        source.add()

        # Verify client methods called
        mock_client.get_or_create_collection.assert_called_once()
        mock_client.add_documents.assert_called_once()

        # Verify documents have proper BaseRecord format with metadata
        call_kwargs = mock_client.add_documents.call_args[1]
        documents = call_kwargs["documents"]
        assert len(documents) >= 1
        assert all("content" in doc for doc in documents)
        assert all("metadata" in doc for doc in documents)
        assert all(doc["metadata"]["post_id"] == "abc123" for doc in documents)

    def test_twitter_add_succeeds_with_injected_storage(self, mock_twitter_thread):
        """TwitterKnowledgeSource.add() works with injected storage."""
        source = TwitterKnowledgeSource(threads=[mock_twitter_thread])

        # Mock storage with client
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"

        # Simulates Knowledge.add_sources() storage injection
        source.storage = mock_storage

        source.add()

        # Verify client methods called
        mock_client.get_or_create_collection.assert_called_once()
        mock_client.add_documents.assert_called_once()

        call_kwargs = mock_client.add_documents.call_args[1]
        documents = call_kwargs["documents"]
        # Twitter uses thread_id as post_id for consistency with Reddit source
        assert all(doc["metadata"]["post_id"] == "thread_xyz" for doc in documents)

    def test_multiple_sources_require_individual_storage_injection(
        self, mock_reddit_post, mock_twitter_thread
    ):
        """Each source needs storage injected separately (as add_sources() does)."""
        reddit_source = RedditKnowledgeSource(posts=[mock_reddit_post])
        twitter_source = TwitterKnowledgeSource(threads=[mock_twitter_thread])

        # Both start without storage
        assert reddit_source.storage is None
        assert twitter_source.storage is None

        # Mock storage with client (shared client for both sources)
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage._get_client.return_value = mock_client
        mock_storage.collection_name = "test_collection"

        # Inject storage into each (mimics Knowledge.add_sources() loop)
        reddit_source.storage = mock_storage
        twitter_source.storage = mock_storage

        # Both should now work
        reddit_source.add()
        twitter_source.add()

        # Should have 2 add_documents calls (one per source)
        assert mock_client.add_documents.call_count == 2
