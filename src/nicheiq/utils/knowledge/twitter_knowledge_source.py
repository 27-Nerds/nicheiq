"""
Custom knowledge source for Twitter threads with thread_id metadata.

This ensures reliable source attribution by storing thread_id in vector DB metadata,
rather than relying on [source: ID] tags in text that LLMs may not correctly preserve.
"""

from typing import TYPE_CHECKING

from crewai.knowledge.source.base_knowledge_source import BaseKnowledgeSource
from loguru import logger
from pydantic import Field

from ...models.social_content import TwitterThread

if TYPE_CHECKING:
    from crewai.rag.types import BaseRecord


class TwitterKnowledgeSource(BaseKnowledgeSource):
    """Knowledge source that indexes Twitter threads with thread_id metadata."""

    threads: list[TwitterThread] = Field(default_factory=list)
    chunk_size: int = Field(default=1500)
    chunk_overlap: int = Field(default=400)

    def validate_content(self) -> None:
        """Validate that we have threads to index."""
        if not self.threads:
            raise ValueError("TwitterKnowledgeSource requires at least one thread")

    def add(self) -> None:
        """Chunk each thread and store with thread_id metadata.

        Uses the RAG client directly to preserve metadata, since KnowledgeStorage.save()
        only accepts list[str] and wraps them, losing our metadata structure.
        """
        from crewai.rag.types import BaseRecord

        documents: list[BaseRecord] = []

        for thread in self.threads:
            # Format thread content
            content = self._format_thread(thread)

            # Chunk the content
            chunks = self._chunk_text(content)

            # Add each chunk with thread_id metadata (use post_id for consistency)
            for chunk in chunks:
                documents.append({
                    "content": chunk,
                    "metadata": {
                        "post_id": thread.thread_id,  # Use post_id for consistency with Reddit
                        "author": thread.original_tweet.author_username,
                        "source_type": "twitter",
                    }
                })

        if not self.storage:
            raise ValueError("No storage found to save documents.")

        # Handle empty documents
        if not documents:
            logger.warning("TwitterKnowledgeSource: No documents to index (empty threads)")
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
                f"TwitterKnowledgeSource: Indexed {len(documents)} chunks "
                f"from {len(self.threads)} threads into '{collection_name}'"
            )
        except Exception as e:
            logger.error(f"TwitterKnowledgeSource: Failed to save documents: {e}")
            raise

    def _format_thread(self, thread: TwitterThread) -> str:
        """Format a single thread for indexing."""
        lines = [
            f"## @{thread.original_tweet.author_username}:",
            "",
            thread.original_tweet.text,
            "",
            "---",
            f"Replies ({len(thread.replies)}):",
            "",
        ]

        # Include replies (limit for chunk size)
        for reply in thread.replies[:30]:
            lines.append(
                f"- @{reply.author_username} [{reply.likes} likes]: {reply.text}"
            )

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
