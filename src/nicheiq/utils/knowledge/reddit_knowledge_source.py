"""
Custom knowledge source for Reddit posts with post_id metadata.

This ensures reliable source attribution by storing post_id in vector DB metadata,
rather than relying on [source: ID] tags in text that LLMs may not correctly preserve.
"""

from typing import TYPE_CHECKING

from crewai.knowledge.source.base_knowledge_source import BaseKnowledgeSource
from loguru import logger
from pydantic import Field

from ...models.social_content import RedditPost

if TYPE_CHECKING:
    from crewai.rag.types import BaseRecord


class RedditKnowledgeSource(BaseKnowledgeSource):
    """Knowledge source that indexes Reddit posts with post_id metadata."""

    posts: list[RedditPost] = Field(default_factory=list)
    chunk_size: int = Field(default=2000)
    chunk_overlap: int = Field(default=600)

    def validate_content(self) -> None:
        """Validate that we have posts to index."""
        if not self.posts:
            raise ValueError("RedditKnowledgeSource requires at least one post")

    def add(self) -> None:
        """Chunk each post and store with post_id metadata.

        Uses the RAG client directly to preserve metadata, since KnowledgeStorage.save()
        only accepts list[str] and wraps them, losing our metadata structure.
        """
        from crewai.rag.types import BaseRecord

        documents: list[BaseRecord] = []

        for post in self.posts:
            # Format post content
            content = self._format_post(post)

            # Chunk the content
            chunks = self._chunk_text(content)

            # Add each chunk with post_id metadata
            for chunk in chunks:
                documents.append({
                    "content": chunk,
                    "metadata": {
                        "post_id": post.post_id,
                        "subreddit": post.subreddit,
                        "source_type": "reddit",
                    }
                })

        if not self.storage:
            raise ValueError("No storage found to save documents.")

        # Handle empty documents
        if not documents:
            logger.warning("RedditKnowledgeSource: No documents to index (empty posts)")
            return

        # Use client directly to preserve metadata (storage.save() doesn't support it)
        collection_name = (
            f"knowledge_{self.storage.collection_name}"
            if self.storage.collection_name
            else "knowledge"
        )

        # Defensive check for API compatibility
        if not hasattr(self.storage, '_get_client'):
            raise RuntimeError(
                "CrewAI API changed: KnowledgeStorage._get_client() not found. "
                "Please check CrewAI version compatibility."
            )

        try:
            client = self.storage._get_client()
            client.get_or_create_collection(collection_name=collection_name)
            client.add_documents(
                collection_name=collection_name,
                documents=documents,
            )
            logger.info(
                f"RedditKnowledgeSource: Indexed {len(documents)} chunks "
                f"from {len(self.posts)} posts into '{collection_name}'"
            )
        except Exception as e:
            logger.error(f"RedditKnowledgeSource: Failed to save documents: {e}")
            raise

    def _format_post(self, post: RedditPost) -> str:
        """Format a single post with comments for indexing."""
        lines = [
            f"### {post.title}",
            "",
            post.selftext or "",
            "",
            "---",
            f"Discussion ({len(post.comments)} comments):",
            "",
        ]

        # Include top comments with nested replies (limit for chunk size)
        for comment in post.comments[:20]:
            lines.append(f"- [{comment.score} pts] {comment.body}")
            # Include nested replies
            for reply in comment.replies[:5]:
                lines.append(f"  - [{reply.score} pts] {reply.body}")

        return "\n".join(lines)

    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks.

        Uses simple character-based splitting with overlap to preserve context.
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            # Find end of chunk
            end = start + self.chunk_size

            # If not at end, try to break at paragraph or sentence
            if end < len(text):
                # Try to break at paragraph
                paragraph_break = text.rfind("\n\n", start, end)
                if paragraph_break > start + self.chunk_size // 2:
                    end = paragraph_break + 2
                else:
                    # Try to break at sentence
                    sentence_break = max(
                        text.rfind(". ", start, end),
                        text.rfind("! ", start, end),
                        text.rfind("? ", start, end),
                    )
                    if sentence_break > start + self.chunk_size // 2:
                        end = sentence_break + 2
                    else:
                        # Try to break at word
                        word_break = text.rfind(" ", start, end)
                        if word_break > start + self.chunk_size // 2:
                            end = word_break + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start, accounting for overlap
            start = max(start + 1, end - self.chunk_overlap)

        return chunks

    async def aadd(self) -> None:
        """Async version - delegates to sync implementation."""
        self.add()
