"""
Tests for token monitoring utilities.
"""

import pytest
from unittest.mock import MagicMock, patch
from nicheiq.utils.token_monitor import ContentTokenMonitor


class TestContentTokenMonitor:
    """Tests for ContentTokenMonitor class."""

    def test_initialization_with_tiktoken(self):
        """Test that monitor initializes with tiktoken if available."""
        with patch('nicheiq.utils.token_monitor.logger'):
            monitor = ContentTokenMonitor()
            # Should attempt to import tiktoken (may or may not succeed)
            assert hasattr(monitor, 'tiktoken')
            assert hasattr(monitor, 'encoding_cache')

    def test_initialization_without_tiktoken(self):
        """Test that monitor handles missing tiktoken gracefully."""
        with patch.dict('sys.modules', {'tiktoken': None}):
            with patch('nicheiq.utils.token_monitor.logger') as mock_logger:
                monitor = ContentTokenMonitor()
                assert monitor.tiktoken is None
                assert monitor.encoding_cache == {}

    def test_count_tokens_with_tiktoken(self):
        """Test token counting when tiktoken is available."""
        # Create mock encoding
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens

        # Create mock tiktoken module
        mock_tiktoken = MagicMock()
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        monitor = ContentTokenMonitor()
        monitor.tiktoken = mock_tiktoken

        count = monitor.count_tokens("test text", model="gpt-4o")

        assert count == 5
        mock_encoding.encode.assert_called_once_with("test text")

    def test_count_tokens_without_tiktoken(self):
        """Test token counting fallback when tiktoken unavailable."""
        monitor = ContentTokenMonitor()
        monitor.tiktoken = None

        count = monitor.count_tokens("test text")

        assert count == 0  # Returns 0 when tiktoken not available

    def test_count_tokens_caches_encoding(self):
        """Test that encoding is cached for repeated use."""
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3]

        mock_tiktoken = MagicMock()
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        monitor = ContentTokenMonitor()
        monitor.tiktoken = mock_tiktoken

        # First call should create encoding
        monitor.count_tokens("text 1", model="gpt-4o")
        # Second call should use cached encoding
        monitor.count_tokens("text 2", model="gpt-4o")

        # encoding_for_model should only be called once
        assert mock_tiktoken.encoding_for_model.call_count == 1

    def test_count_tokens_uses_fallback_on_error(self):
        """Test fallback to character-based estimation on error."""
        mock_tiktoken = MagicMock()
        mock_tiktoken.encoding_for_model.side_effect = Exception("Encoding error")

        monitor = ContentTokenMonitor()
        monitor.tiktoken = mock_tiktoken

        # 20 characters = ~5 tokens (1 token ≈ 4 chars)
        count = monitor.count_tokens("a" * 20, model="gpt-4o")

        assert count == 5

    def test_estimate_cost_gpt4o(self):
        """Test cost estimation for GPT-4o model."""
        monitor = ContentTokenMonitor()

        # 1 million tokens at $2.50 per million = $2.50
        cost = monitor.estimate_cost(1_000_000, model="gpt-4o")
        assert cost == 2.50

        # 500K tokens = $1.25
        cost = monitor.estimate_cost(500_000, model="gpt-4o")
        assert cost == 1.25

    def test_estimate_cost_gpt4o_mini(self):
        """Test cost estimation for GPT-4o-mini model."""
        monitor = ContentTokenMonitor()

        # 1 million tokens at $0.15 per million
        cost = monitor.estimate_cost(1_000_000, model="gpt-4o-mini")
        assert cost == 0.15

    def test_estimate_cost_unknown_model_uses_default(self):
        """Test that unknown model uses default GPT-4o pricing."""
        monitor = ContentTokenMonitor()

        # Unknown model should use default gpt-4o pricing ($2.50)
        cost = monitor.estimate_cost(1_000_000, model="unknown-model")
        assert cost == 2.50

    def test_estimate_cost_various_models(self):
        """Test cost estimation for various model types."""
        monitor = ContentTokenMonitor()
        tokens = 1_000_000

        # GPT-5 series
        assert monitor.estimate_cost(tokens, "gpt-5") == 1.25
        assert monitor.estimate_cost(tokens, "gpt-5-mini") == 0.25

        # o-series
        assert monitor.estimate_cost(tokens, "o3") == 2.00
        assert monitor.estimate_cost(tokens, "o3-mini") == 1.10

        # Legacy
        assert monitor.estimate_cost(tokens, "gpt-4-turbo") == 10.00
        assert monitor.estimate_cost(tokens, "gpt-3.5-turbo") == 0.50

    @patch('nicheiq.utils.token_monitor.settings')
    @patch('nicheiq.utils.token_monitor.logger')
    @patch.object(ContentTokenMonitor, 'count_tokens', return_value=100_000)
    @patch.object(ContentTokenMonitor, 'estimate_cost', return_value=0.25)
    def test_log_content_stats_when_enabled(self, mock_cost, mock_count, mock_logger, mock_settings):
        """Test log_content_stats when monitoring is enabled."""
        mock_settings.token_monitoring_enabled = True

        monitor = ContentTokenMonitor()
        token_count = monitor.log_content_stats(
            content="test content",
            label="Test Label",
            model="gpt-4o",
            context_limit=1_000_000
        )

        assert token_count == 100_000
        mock_logger.info.assert_called_once()
        # Check that log message contains expected info
        log_call = mock_logger.info.call_args[0][0]
        assert "Test Label" in log_call
        assert "100,000" in log_call
        assert "$0.25" in log_call

    @patch('nicheiq.utils.token_monitor.settings')
    def test_log_content_stats_when_disabled(self, mock_settings):
        """Test that log_content_stats returns 0 when monitoring disabled."""
        mock_settings.token_monitoring_enabled = False

        monitor = ContentTokenMonitor()
        token_count = monitor.log_content_stats(
            content="test content",
            label="Test Label"
        )

        assert token_count == 0

    @patch('nicheiq.utils.token_monitor.settings')
    @patch('nicheiq.utils.token_monitor.logger')
    @patch.object(ContentTokenMonitor, 'estimate_cost', return_value=0.50)
    def test_check_soft_cap_warning_threshold(self, mock_cost, mock_logger, mock_settings):
        """Test that warning is logged when exceeding warning threshold."""
        mock_settings.token_warning_threshold = 200_000
        mock_settings.token_soft_cap_enabled = False

        monitor = ContentTokenMonitor()
        result = monitor.check_soft_cap(
            tokens=250_000,  # Exceeds warning threshold
            label="Test",
            model="gpt-4o"
        )

        assert result is False  # Soft cap not enabled
        # Warning should be logged
        assert mock_logger.warning.called

    @patch('nicheiq.utils.token_monitor.settings')
    @patch('nicheiq.utils.token_monitor.logger')
    @patch.object(ContentTokenMonitor, 'estimate_cost', return_value=1.00)
    def test_check_soft_cap_when_enabled_and_exceeded(self, mock_cost, mock_logger, mock_settings):
        """Test critical warning when soft cap is enabled and exceeded."""
        mock_settings.token_warning_threshold = 200_000
        mock_settings.token_soft_cap_enabled = True
        mock_settings.token_soft_cap = 400_000

        monitor = ContentTokenMonitor()
        result = monitor.check_soft_cap(
            tokens=500_000,  # Exceeds soft cap
            label="Test",
            model="gpt-4o"
        )

        assert result is True
        # Critical warning should be logged
        assert mock_logger.critical.called

    @patch('nicheiq.utils.token_monitor.settings')
    @patch('nicheiq.utils.token_monitor.logger')
    def test_check_soft_cap_under_threshold(self, mock_logger, mock_settings):
        """Test no warnings when under all thresholds."""
        mock_settings.token_warning_threshold = 200_000
        mock_settings.token_soft_cap_enabled = True
        mock_settings.token_soft_cap = 400_000

        monitor = ContentTokenMonitor()
        result = monitor.check_soft_cap(
            tokens=100_000,  # Under all thresholds
            label="Test"
        )

        assert result is False
        # No warnings should be logged
        assert not mock_logger.warning.called
        assert not mock_logger.critical.called
