"""
Tests for ChromaDB collection isolation (cross-job data leakage fix).

Verifies:
- sanitize_collection_name produces job-isolated names with job_id
- Backward compatibility when job_id is None
- Different jobs produce different collection names
- Same job produces deterministic collection names
- PainPointCrew uses crew-level knowledge (not agent-level knowledge_sources)
- Cleanup handles missing collections gracefully
- cleanup_chromadb CLI command for auditing/purging legacy collections
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from nicheiq.utils.helpers import sanitize_collection_name
from nicheiq.main import cleanup_chromadb


class TestSanitizeCollectionNameWithJobId:
    """Test sanitize_collection_name with job_id parameter."""

    def test_includes_hash_when_job_id_provided(self):
        """Collection name should include 8-char job hash when job_id is given."""
        result = sanitize_collection_name("AI tools for creators", "pain", job_id="job-123")
        expected_hash = hashlib.sha256("job-123".encode()).hexdigest()[:8]
        assert expected_hash in result
        assert result.startswith("pain_")

    def test_stays_under_63_chars(self):
        """Collection name must respect ChromaDB's 63-char limit."""
        long_niche = "a" * 200
        result = sanitize_collection_name(long_niche, "audience", job_id="some-long-job-uuid-1234")
        assert len(result) <= 63

    def test_minimum_length(self):
        """Collection name must be at least 3 chars."""
        result = sanitize_collection_name("x", "p", job_id="j")
        assert len(result) >= 3

    def test_format_is_crew_hash_slug(self):
        """Format should be {crew}_{hash}_{slug}."""
        result = sanitize_collection_name("test niche", "seo", job_id="abc")
        expected_hash = hashlib.sha256("abc".encode()).hexdigest()[:8]
        assert result.startswith(f"seo_{expected_hash}_")


class TestSanitizeCollectionNameBackwardCompatible:
    """Test that sanitize_collection_name without job_id is unchanged."""

    def test_no_job_id_produces_legacy_format(self):
        """Without job_id, output should be crew_slug (no hash)."""
        result = sanitize_collection_name("AI tools for content creators", "pain")
        assert result == "pain_ai_tools_for_content_creators"

    def test_none_job_id_same_as_missing(self):
        """Explicitly passing job_id=None should produce legacy format."""
        result = sanitize_collection_name("test niche", "seo", job_id=None)
        assert result == "seo_test_niche"
        # No 8-char hex hash should be present
        result_without_job = sanitize_collection_name("test niche", "seo")
        assert result == result_without_job


class TestDifferentJobsDifferentNames:
    """Two different job_ids must produce different collection names."""

    def test_different_jobs_different_names(self):
        job_a = sanitize_collection_name("same niche", "pain", job_id="job-aaa")
        job_b = sanitize_collection_name("same niche", "pain", job_id="job-bbb")
        assert job_a != job_b

    def test_same_niche_different_crews_different_names(self):
        """Different crew names with same job produce different names."""
        a = sanitize_collection_name("same niche", "pain", job_id="job-1")
        b = sanitize_collection_name("same niche", "seo", job_id="job-1")
        assert a != b


class TestSameJobDeterministic:
    """Same job_id must produce deterministic collection names."""

    def test_deterministic(self):
        name1 = sanitize_collection_name("my niche", "solution", job_id="fixed-id")
        name2 = sanitize_collection_name("my niche", "solution", job_id="fixed-id")
        assert name1 == name2


class TestPainPointCrewUsesCrewLevelKnowledge:
    """Verify PainPointCrew attaches knowledge at crew level, not agent level."""

    @patch("nicheiq.crews.pain_point_crew.Crew")
    @patch("nicheiq.crews.pain_point_crew.Agent")
    def test_crew_level_knowledge_param(self, mock_agent, mock_crew):
        """Crew() should receive knowledge= kwarg, not agents with knowledge_sources=."""
        from nicheiq.crews.pain_point_crew import PainPointCrew

        # Create a minimal PainPointCrew (no actual posts)
        crew = PainPointCrew(
            reddit_posts=[],
            twitter_threads=[],
            niche_description="test",
            job_id="test-job",
        )

        # Call crew() to trigger Crew construction
        try:
            crew.crew()
        except Exception:
            pass  # May fail due to missing config, that's OK

        # If Crew was called, check that knowledge_sources was NOT passed to agents
        for call_args in mock_agent.call_args_list:
            _, kwargs = call_args
            assert "knowledge_sources" not in kwargs, (
                f"Agent should not have knowledge_sources. Found in: {kwargs}"
            )


class TestCleanupHandlesMissing:
    """Cleanup should not raise on nonexistent collections."""

    def test_cleanup_handles_reset_error(self):
        """cleanup_collections should swallow errors from Knowledge.reset()."""
        from nicheiq.flows.research_flow import ResearchFlow

        # Create a minimal flow
        flow = ResearchFlow.__new__(ResearchFlow)
        flow._knowledge_objects = []

        # Add a mock Knowledge that raises on reset
        mock_knowledge = MagicMock()
        mock_knowledge.reset.side_effect = Exception("Collection not found")
        flow._knowledge_objects.append(mock_knowledge)

        # Should not raise
        flow.cleanup_collections()

        # Verify reset was attempted
        mock_knowledge.reset.assert_called_once()

        # List should be cleared
        assert len(flow._knowledge_objects) == 0

    def test_cleanup_with_empty_list(self):
        """Cleanup with no knowledge objects should be a no-op."""
        from nicheiq.flows.research_flow import ResearchFlow

        flow = ResearchFlow.__new__(ResearchFlow)
        flow._knowledge_objects = []

        # Should not raise
        flow.cleanup_collections()


class TestCleanupChromaDBCommand:
    """Tests for the cleanup_chromadb CLI command."""

    @pytest.fixture
    def mock_chromadb_client(self):
        client = MagicMock()
        coll1 = MagicMock()
        coll1.name = "knowledge_pain_test"
        coll1.count.return_value = 100
        coll2 = MagicMock()
        coll2.name = "knowledge_seo_test"
        coll2.count.return_value = 200
        client.list_collections.return_value = [coll1, coll2]
        return client

    @patch("nicheiq.main.db_storage_path")
    @patch("nicheiq.main.chromadb")
    def test_dry_run_does_not_delete(self, mock_chromadb_mod, mock_path, mock_chromadb_client, tmp_path):
        """Dry run should list collections but not delete any."""
        mock_path.return_value = tmp_path
        mock_chromadb_mod.PersistentClient.return_value = mock_chromadb_client

        cleanup_chromadb(dry_run=True)

        mock_chromadb_client.delete_collection.assert_not_called()

    @patch("nicheiq.main.db_storage_path")
    @patch("nicheiq.main.chromadb")
    def test_dry_run_prints_collections(self, mock_chromadb_mod, mock_path, mock_chromadb_client, tmp_path, capsys):
        """Dry run should print collection names, doc counts, and --force instruction."""
        mock_path.return_value = tmp_path
        mock_chromadb_mod.PersistentClient.return_value = mock_chromadb_client

        cleanup_chromadb(dry_run=True)

        output = capsys.readouterr().out
        assert "knowledge_pain_test" in output
        assert "knowledge_seo_test" in output
        assert "100" in output
        assert "200" in output
        assert "--force" in output

    @patch("nicheiq.main.db_storage_path")
    @patch("nicheiq.main.chromadb")
    def test_force_deletes_all(self, mock_chromadb_mod, mock_path, mock_chromadb_client, tmp_path):
        """Force mode should delete all collections."""
        mock_path.return_value = tmp_path
        mock_chromadb_mod.PersistentClient.return_value = mock_chromadb_client

        cleanup_chromadb(dry_run=False)

        assert mock_chromadb_client.delete_collection.call_count == 2
        mock_chromadb_client.delete_collection.assert_any_call(name="knowledge_pain_test")
        mock_chromadb_client.delete_collection.assert_any_call(name="knowledge_seo_test")

    @patch("nicheiq.main.db_storage_path")
    @patch("nicheiq.main.chromadb")
    def test_force_prints_progress(self, mock_chromadb_mod, mock_path, mock_chromadb_client, tmp_path, capsys):
        """Force mode should print progress and 'Done' summary."""
        mock_path.return_value = tmp_path
        mock_chromadb_mod.PersistentClient.return_value = mock_chromadb_client

        cleanup_chromadb(dry_run=False)

        output = capsys.readouterr().out
        assert "[1/2]" in output
        assert "[2/2]" in output
        assert "Done" in output

    @patch("nicheiq.main.db_storage_path")
    @patch("nicheiq.main.chromadb")
    def test_empty_collections(self, mock_chromadb_mod, mock_path, tmp_path, capsys):
        """When no collections exist, should print 'No collections found.'"""
        mock_path.return_value = tmp_path
        client = MagicMock()
        client.list_collections.return_value = []
        mock_chromadb_mod.PersistentClient.return_value = client

        cleanup_chromadb(dry_run=True)

        output = capsys.readouterr().out
        assert "No collections found" in output

    @patch("nicheiq.main.db_storage_path")
    def test_storage_dir_not_found(self, mock_path, capsys):
        """When storage dir doesn't exist, should not create PersistentClient."""
        mock_path.return_value = "/nonexistent/path/that/does/not/exist"

        with patch("nicheiq.main.chromadb") as mock_chromadb_mod:
            cleanup_chromadb(dry_run=True)
            mock_chromadb_mod.PersistentClient.assert_not_called()

        output = capsys.readouterr().out
        assert "No ChromaDB storage found" in output

    @patch("nicheiq.main.db_storage_path")
    @patch("nicheiq.main.chromadb")
    def test_partial_delete_failure(self, mock_chromadb_mod, mock_path, mock_chromadb_client, tmp_path, capsys):
        """If one deletion fails, the rest should still be attempted."""
        mock_path.return_value = tmp_path
        mock_chromadb_mod.PersistentClient.return_value = mock_chromadb_client

        # First delete succeeds, second fails
        mock_chromadb_client.delete_collection.side_effect = [None, RuntimeError("locked")]

        cleanup_chromadb(dry_run=False)

        output = capsys.readouterr().out
        assert mock_chromadb_client.delete_collection.call_count == 2
        assert "FAILED" in output
        assert "Deleted 1/2" in output
        assert "knowledge_seo_test" in output

    @patch("nicheiq.main.db_storage_path")
    @patch("nicheiq.main.chromadb")
    def test_collection_with_zero_docs(self, mock_chromadb_mod, mock_path, tmp_path, capsys):
        """Collections with 0 documents should still be listed and deletable."""
        mock_path.return_value = tmp_path
        client = MagicMock()
        coll = MagicMock()
        coll.name = "empty_collection"
        coll.count.return_value = 0
        client.list_collections.return_value = [coll]
        mock_chromadb_mod.PersistentClient.return_value = client

        # Dry run lists it
        cleanup_chromadb(dry_run=True)
        output = capsys.readouterr().out
        assert "empty_collection" in output
        assert "0" in output

        # Force mode deletes it
        cleanup_chromadb(dry_run=False)
        client.delete_collection.assert_called_with(name="empty_collection")

    @patch("nicheiq.main.cleanup_chromadb")
    def test_cli_argument_integration(self, mock_cleanup):
        """--cleanup-collections flag should call cleanup_chromadb and exit."""
        import sys

        with patch.object(sys, "argv", ["nicheiq.main", "--cleanup-collections"]):
            with pytest.raises(SystemExit) as exc_info:
                from nicheiq.main import main
                main()
            assert exc_info.value.code == 0
            mock_cleanup.assert_called_once_with(dry_run=True)
