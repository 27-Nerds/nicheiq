"""
Knowledge Helpers - Safe Knowledge creation with controlled embedding batch size.

CrewAI's KnowledgeStorage.__init__() creates a ChromaDBConfig with batch_size=100 (default).
With OpenAI's text-embedding-3-small and typical chunk sizes (~250 tokens per chunk),
100 chunks per batch totals ~25K tokens — exceeding the 8192 token-per-batch limit.

This module provides create_knowledge() which builds Knowledge with a custom batch_size
(default 20: 20 chunks x ~250 tokens = ~5K tokens, safely under 8192).
"""

from typing import Optional

from crewai.knowledge.knowledge import Knowledge
from crewai.knowledge.source.base_knowledge_source import BaseKnowledgeSource
from crewai.knowledge.storage.knowledge_storage import KnowledgeStorage
from crewai.rag.chromadb.config import ChromaDBConfig
from crewai.rag.embeddings.factory import build_embedder
from crewai.rag.embeddings.types import EmbedderConfig
from crewai.rag.factory import create_client
from loguru import logger


def create_knowledge(
    sources: list[BaseKnowledgeSource],
    embedder_config: EmbedderConfig,
    collection_name: str,
    batch_size: int = 20,
) -> Optional[Knowledge]:
    """Create Knowledge with a safe embedding batch size.

    Args:
        sources: List of knowledge sources (StringKnowledgeSource, etc.)
        embedder_config: Embedder configuration dict, e.g.
            {"provider": "openai", "config": {"model_name": "text-embedding-3-small"}}
        collection_name: ChromaDB collection name for isolation
        batch_size: Max chunks per embedding batch (default 20, safe for OpenAI 8192 limit)

    Returns:
        Configured Knowledge instance with sources indexed, or None if sources is empty.
    """
    if not sources:
        logger.debug("No knowledge sources provided, skipping knowledge creation")
        return None

    # Build the embedding function from config dict
    embedding_function = build_embedder(embedder_config)

    # Create ChromaDB config with custom batch_size
    config = ChromaDBConfig(
        embedding_function=embedding_function,
        batch_size=batch_size,
    )
    client = create_client(config)

    # Create storage with the custom client injected
    storage = KnowledgeStorage(collection_name=collection_name)
    storage._client = client

    # Create Knowledge with our pre-configured storage
    knowledge = Knowledge(
        collection_name=collection_name,
        sources=sources,
        storage=storage,
    )
    knowledge.add_sources()

    logger.info(
        f"Knowledge created: collection={collection_name}, "
        f"{len(sources)} sources, batch_size={batch_size}"
    )
    return knowledge
