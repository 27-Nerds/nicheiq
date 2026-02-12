"""Tests for knowledge_helpers - safe Knowledge creation with batch_size control."""

from unittest.mock import MagicMock, patch

import pytest

from nicheiq.utils.crew_helpers.knowledge_helpers import create_knowledge


class TestCreateKnowledge:
    """Test create_knowledge() helper."""

    def test_empty_sources_returns_none(self):
        """No sources should return None without attempting any creation."""
        result = create_knowledge(
            sources=[],
            embedder_config={"provider": "openai", "config": {"model_name": "text-embedding-3-small"}},
            collection_name="test",
        )
        assert result is None

    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.create_client")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.build_embedder")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.KnowledgeStorage")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.Knowledge")
    def test_batch_size_flows_to_config(
        self, mock_knowledge_cls, mock_storage_cls, mock_build_embedder, mock_create_client
    ):
        """Verify batch_size is passed through to ChromaDBConfig."""
        mock_source = MagicMock()
        mock_embedding_fn = MagicMock()
        mock_build_embedder.return_value = mock_embedding_fn
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_knowledge = MagicMock()
        mock_knowledge_cls.return_value = mock_knowledge

        result = create_knowledge(
            sources=[mock_source],
            embedder_config={"provider": "openai", "config": {"model_name": "text-embedding-3-small"}},
            collection_name="test_collection",
            batch_size=15,
        )

        # Verify build_embedder was called with the config
        mock_build_embedder.assert_called_once()

        # Verify create_client was called with a config that has batch_size=15
        mock_create_client.assert_called_once()
        config_arg = mock_create_client.call_args[0][0]
        assert config_arg.batch_size == 15

        # Verify storage was created and client was injected
        mock_storage_cls.assert_called_once_with(collection_name="test_collection")
        assert mock_storage._client == mock_client

        # Verify Knowledge was created with the storage
        mock_knowledge_cls.assert_called_once_with(
            collection_name="test_collection",
            sources=[mock_source],
            storage=mock_storage,
        )

        # Verify add_sources was called
        mock_knowledge.add_sources.assert_called_once()

        assert result == mock_knowledge

    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.create_client")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.build_embedder")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.KnowledgeStorage")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.Knowledge")
    def test_default_batch_size_is_20(
        self, mock_knowledge_cls, mock_storage_cls, mock_build_embedder, mock_create_client
    ):
        """Default batch_size should be 20, not the CrewAI default of 100."""
        mock_source = MagicMock()
        mock_build_embedder.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_storage_cls.return_value = MagicMock()
        mock_knowledge_cls.return_value = MagicMock()

        create_knowledge(
            sources=[mock_source],
            embedder_config={"provider": "openai", "config": {"model_name": "text-embedding-3-small"}},
            collection_name="test",
        )

        config_arg = mock_create_client.call_args[0][0]
        assert config_arg.batch_size == 20

    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.create_client")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.build_embedder")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.KnowledgeStorage")
    @patch("nicheiq.utils.crew_helpers.knowledge_helpers.Knowledge")
    def test_multiple_sources(
        self, mock_knowledge_cls, mock_storage_cls, mock_build_embedder, mock_create_client
    ):
        """Multiple sources should all be passed to Knowledge."""
        sources = [MagicMock(), MagicMock(), MagicMock()]
        mock_build_embedder.return_value = MagicMock()
        mock_create_client.return_value = MagicMock()
        mock_storage_cls.return_value = MagicMock()
        mock_knowledge_cls.return_value = MagicMock()

        create_knowledge(
            sources=sources,
            embedder_config={"provider": "openai", "config": {"model_name": "text-embedding-3-small"}},
            collection_name="multi",
        )

        call_kwargs = mock_knowledge_cls.call_args[1]
        assert len(call_kwargs["sources"]) == 3
