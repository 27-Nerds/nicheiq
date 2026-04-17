"""
Tests for new accessor methods added during refactoring.

This module tests:
1. ScoreAccessor.get_confidence_score() - confidence score calculation
2. StateAccessor.get_competitor_count() - competitor counting
3. Channel identification methods - Reddit, SEO, Twitter channel detection
"""

import pytest
from unittest.mock import Mock, MagicMock

from nicheiq.report.utils.score_accessor import ScoreAccessor
from nicheiq.report.utils.state_accessors import StateAccessor
from nicheiq.report.report_generator import ReportGenerator
from nicheiq.models.marketing_blueprint import MarketingChannel


# ==================================================================================
# Fixtures
# ==================================================================================

@pytest.fixture
def mock_solution_scores():
    """Create mock SolutionScores with all scores present."""
    scores = Mock()
    scores.solution_name = "TestSolution"
    scores.market_fit_score = 0.8
    scores.competitive_advantage_score = 0.6
    scores.technical_feasibility_score = 0.7
    scores.seo_growth_potential_score = 0.9
    return scores


@pytest.fixture
def mock_solution_selection_with_scores(mock_solution_scores):
    """Create SolutionSelection with complete scores."""
    selection = Mock()
    selection.all_solution_scores = [mock_solution_scores]
    selection.selected_solution_name = "TestSolution"
    return selection


@pytest.fixture
def mock_solution_selection_without_scores():
    """Create SolutionSelection with no scores."""
    selection = Mock()
    selection.all_solution_scores = None
    selection.selected_solution_name = "TestSolution"
    return selection


@pytest.fixture
def mock_solution_idea():
    """Create mock SolutionIdea with scores in fields."""
    solution = Mock()
    solution.solution_name = "TestSolution"
    solution.market_fit_score = 0.7
    solution.technical_feasibility_score = 0.5
    solution.seo_scalability_score = 0.6
    return solution


@pytest.fixture
def mock_competitive_landscape():
    """Create mock CompetitiveLandscape."""
    landscape = Mock()
    landscape.solution_name = "TestSolution"
    landscape.competitors = [Mock(), Mock(), Mock()]  # 3 competitors
    landscape.market_gaps = ["Gap 1", "Gap 2"]
    return landscape


@pytest.fixture
def mock_state_with_competitors(mock_competitive_landscape):
    """Create ResearchState with competitive analysis."""
    state = Mock()
    state.competitive_analysis = Mock()
    state.competitive_analysis.solution_landscapes = [mock_competitive_landscape]
    state.solution_selection = Mock()
    state.solution_selection.selected_solution_name = "TestSolution"
    return state


@pytest.fixture
def mock_reddit_posts():
    """Create mock Reddit posts."""
    posts = []
    for i in range(5):
        post = Mock()
        post.subreddit = "testsubreddit" if i < 3 else "othersubreddit"
        posts.append(post)
    return posts


@pytest.fixture
def mock_enriched_keywords():
    """Create mock enriched keywords for SEO."""
    keywords = []
    for i in range(10):
        kw = Mock()
        kw.keyword = f"test keyword {i}"
        kw.search_volume = 1000 + (i * 100)
        kw.competition = 30.0
        keywords.append(kw)
    return keywords


@pytest.fixture
def mock_twitter_threads():
    """Create mock Twitter threads."""
    threads = [Mock() for _ in range(7)]
    return threads


# ==================================================================================
# ScoreAccessor.get_confidence_score() Tests
# ==================================================================================

class TestScoreAccessorConfidenceScore:
    """Test suite for ScoreAccessor.get_confidence_score()."""

    def test_with_full_scores_returns_correct_average(
        self, mock_solution_selection_with_scores, mock_solution_idea
    ):
        """Test confidence score with complete SolutionScores data."""
        accessor = ScoreAccessor(mock_solution_selection_with_scores)

        result = accessor.get_confidence_score(mock_solution_idea)

        # Should average market_fit (0.8) and competitive_advantage (0.6)
        expected = (0.8 + 0.6) / 2
        assert result == expected, f"Expected {expected}, got {result}"

    def test_without_solution_scores_uses_fallback(
        self, mock_solution_selection_without_scores
    ):
        """Test confidence score falls back to SolutionIdea fields."""
        accessor = ScoreAccessor(mock_solution_selection_without_scores)

        solution = Mock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.9
        # No competitive_advantage in SolutionIdea, should use market_fit as proxy

        result = accessor.get_confidence_score(solution)

        # Should average market_fit (0.9) and market_fit again (0.9) as proxy
        expected = (0.9 + 0.9) / 2
        assert result == expected, f"Expected {expected}, got {result}"

    def test_with_none_values_returns_none(self):
        """Test confidence score with all None values returns None."""
        accessor = ScoreAccessor(None)

        solution = Mock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None

        result = accessor.get_confidence_score(solution)

        # Should return None when underlying scores are None
        assert result is None, f"Expected None with missing scores, got {result}"

    def test_with_boundary_values_min(self):
        """Test confidence score with minimum boundary values (0.0, 0.0)."""
        selection = Mock()
        selection.all_solution_scores = [
            Mock(
                solution_name="Test",
                market_fit_score=0.0,
                competitive_advantage_score=0.0,
            )
        ]
        accessor = ScoreAccessor(selection)
        solution = Mock(solution_name="Test")

        result = accessor.get_confidence_score(solution)

        assert result == 0.0, f"Expected 0.0, got {result}"

    def test_with_boundary_values_max(self):
        """Test confidence score with maximum boundary values (1.0, 1.0)."""
        selection = Mock()
        selection.all_solution_scores = [
            Mock(
                solution_name="Test",
                market_fit_score=1.0,
                competitive_advantage_score=1.0,
            )
        ]
        accessor = ScoreAccessor(selection)
        solution = Mock(solution_name="Test")

        result = accessor.get_confidence_score(solution)

        assert result == 1.0, f"Expected 1.0, got {result}"

    def test_with_asymmetric_values(self):
        """Test confidence score with asymmetric values (0.0, 1.0)."""
        selection = Mock()
        selection.all_solution_scores = [
            Mock(
                solution_name="Test",
                market_fit_score=0.0,
                competitive_advantage_score=1.0,
            )
        ]
        accessor = ScoreAccessor(selection)
        solution = Mock(solution_name="Test")

        result = accessor.get_confidence_score(solution)

        expected = (0.0 + 1.0) / 2
        assert result == expected, f"Expected {expected}, got {result}"

    def test_calculation_precision(self):
        """Test confidence score calculation precision."""
        selection = Mock()
        selection.all_solution_scores = [
            Mock(
                solution_name="Test",
                market_fit_score=0.7777,
                competitive_advantage_score=0.3333,
            )
        ]
        accessor = ScoreAccessor(selection)
        solution = Mock(solution_name="Test")

        result = accessor.get_confidence_score(solution)

        expected = (0.7777 + 0.3333) / 2
        assert abs(result - expected) < 0.0001, f"Expected {expected}, got {result}"


# ==================================================================================
# StateAccessor.get_competitor_count() Tests
# ==================================================================================

class TestStateAccessorCompetitorCount:
    """Test suite for StateAccessor.get_competitor_count()."""

    def test_with_valid_landscape_returns_count(self, mock_state_with_competitors):
        """Test competitor count with valid landscape."""
        accessor = StateAccessor(mock_state_with_competitors)

        result = accessor.get_competitor_count()

        assert result == 3, f"Expected 3 competitors, got {result}"

    def test_with_empty_competitors_returns_zero(self):
        """Test competitor count with empty competitors list."""
        state = Mock()
        state.competitive_analysis = Mock()
        landscape = Mock()
        landscape.solution_name = "Test"
        landscape.competitors = []  # Empty list
        state.competitive_analysis.solution_landscapes = [landscape]
        state.solution_selection = Mock()
        state.solution_selection.selected_solution_name = "Test"

        accessor = StateAccessor(state)
        result = accessor.get_competitor_count()

        assert result == 0, f"Expected 0 for empty list, got {result}"

    def test_with_none_competitors_returns_zero(self):
        """Test competitor count when competitors is None."""
        state = Mock()
        state.competitive_analysis = Mock()
        landscape = Mock()
        landscape.solution_name = "Test"
        landscape.competitors = None  # None instead of list
        state.competitive_analysis.solution_landscapes = [landscape]
        state.solution_selection = Mock()
        state.solution_selection.selected_solution_name = "Test"

        accessor = StateAccessor(state)
        result = accessor.get_competitor_count()

        assert result == 0, f"Expected 0 for None competitors, got {result}"

    def test_with_no_landscape_returns_zero(self):
        """Test competitor count when no landscape found."""
        state = Mock()
        state.competitive_analysis = Mock()
        state.competitive_analysis.solution_landscapes = []  # No landscapes
        state.solution_selection = Mock()
        state.solution_selection.selected_solution_name = "Test"

        accessor = StateAccessor(state)
        result = accessor.get_competitor_count()

        assert result == 0, f"Expected 0 when no landscape, got {result}"

    def test_with_no_competitive_analysis_returns_zero(self):
        """Test competitor count when no competitive_analysis in state."""
        state = Mock()
        state.competitive_analysis = None
        state.solution_selection = Mock()

        accessor = StateAccessor(state)
        result = accessor.get_competitor_count()

        assert result == 0, f"Expected 0 when no analysis, got {result}"

    def test_with_no_solution_selection_returns_zero(self):
        """Test competitor count when no solution_selection in state."""
        state = Mock()
        state.competitive_analysis = Mock()
        state.solution_selection = None

        accessor = StateAccessor(state)
        result = accessor.get_competitor_count()

        assert result == 0, f"Expected 0 when no selection, got {result}"

    def test_with_large_competitor_count(self):
        """Test competitor count with many competitors."""
        state = Mock()
        state.competitive_analysis = Mock()
        landscape = Mock()
        landscape.solution_name = "Test"
        landscape.competitors = [Mock() for _ in range(15)]  # 15 competitors
        state.competitive_analysis.solution_landscapes = [landscape]
        state.solution_selection = Mock()
        state.solution_selection.selected_solution_name = "Test"

        accessor = StateAccessor(state)
        result = accessor.get_competitor_count()

        assert result == 15, f"Expected 15 competitors, got {result}"


# ==================================================================================
# Channel Identification Tests
# ==================================================================================

class TestRedditChannelIdentification:
    """Test suite for _identify_reddit_channel()."""

    def test_with_valid_reddit_data_returns_channel(self, mock_reddit_posts):
        """Test Reddit channel identification with valid data."""
        state = Mock()
        state.social_content = Mock()
        state.social_content.reddit_posts = mock_reddit_posts

        generator = ReportGenerator(state)
        result = generator._identify_reddit_channel()

        assert result is not None, "Should return MarketingChannel"
        assert isinstance(result, MarketingChannel)
        assert result.channel_name == "Reddit r/testsubreddit"
        assert result.channel_type == "Community"
        assert result.priority == "High"
        assert "3 relevant discussions" in result.target_audience_size

    def test_with_no_social_content_returns_none(self):
        """Test Reddit channel when no social_content."""
        state = Mock()
        state.social_content = None

        generator = ReportGenerator(state)
        result = generator._identify_reddit_channel()

        assert result is None, "Should return None when no social_content"

    def test_with_no_reddit_posts_returns_none(self):
        """Test Reddit channel when no reddit_posts."""
        state = Mock()
        state.social_content = Mock()
        state.social_content.reddit_posts = None

        generator = ReportGenerator(state)
        result = generator._identify_reddit_channel()

        assert result is None, "Should return None when no reddit_posts"

    def test_with_empty_subreddit_counts_returns_none(self):
        """Test Reddit channel when subreddit breakdown is empty."""
        state = Mock()
        state.social_content = Mock()
        state.social_content.reddit_posts = []  # Empty list

        generator = ReportGenerator(state)
        result = generator._identify_reddit_channel()

        assert result is None, "Should return None when no subreddit counts"


class TestSEOChannelIdentification:
    """Test suite for _identify_seo_channel()."""

    def test_with_valid_seo_data_returns_channel(self, mock_enriched_keywords):
        """Test SEO channel identification with valid keywords."""
        state = Mock()
        state.seo_strategy_report = Mock()
        state.seo_strategy_report.tier_1_keywords = mock_enriched_keywords

        generator = ReportGenerator(state)
        result = generator._identify_seo_channel()

        assert result is not None, "Should return MarketingChannel"
        assert isinstance(result, MarketingChannel)
        assert result.channel_name == "SEO Blog / Content Marketing"
        assert result.channel_type == "SEO"
        assert result.priority == "High"
        # Total volume = 1000+1100+1200+...+1900 = 14500
        assert "14,500" in result.target_audience_size
        assert "10 Tier 1 keywords" in result.target_audience_size

    def test_with_no_seo_report_returns_none(self):
        """Test SEO channel when no seo_strategy_report."""
        state = Mock()
        state.seo_strategy_report = None

        generator = ReportGenerator(state)
        result = generator._identify_seo_channel()

        assert result is None, "Should return None when no SEO report"

    def test_with_no_tier1_keywords_returns_none(self):
        """Test SEO channel when no tier_1_keywords."""
        state = Mock()
        state.seo_strategy_report = Mock()
        state.seo_strategy_report.tier_1_keywords = None

        generator = ReportGenerator(state)
        result = generator._identify_seo_channel()

        assert result is None, "Should return None when no tier_1_keywords"

    def test_with_empty_tier1_keywords_returns_none(self):
        """Test SEO channel when tier_1_keywords is empty."""
        state = Mock()
        state.seo_strategy_report = Mock()
        state.seo_strategy_report.tier_1_keywords = []

        generator = ReportGenerator(state)
        result = generator._identify_seo_channel()

        assert result is None, "Should return None when tier_1_keywords empty"


class TestTwitterChannelIdentification:
    """Test suite for _identify_twitter_channel()."""

    def test_with_valid_twitter_data_returns_channel(self, mock_twitter_threads):
        """Test Twitter channel identification with valid data."""
        state = Mock()
        state.social_content = Mock()
        state.social_content.twitter_threads = mock_twitter_threads

        generator = ReportGenerator(state)
        result = generator._identify_twitter_channel()

        assert result is not None, "Should return MarketingChannel"
        assert isinstance(result, MarketingChannel)
        assert result.channel_name == "Twitter / X"
        assert result.channel_type == "Social"
        assert result.priority == "Medium"
        assert "7 relevant conversations" in result.target_audience_size

    def test_with_no_social_content_returns_none(self):
        """Test Twitter channel when no social_content."""
        state = Mock()
        state.social_content = None

        generator = ReportGenerator(state)
        result = generator._identify_twitter_channel()

        assert result is None, "Should return None when no social_content"

    def test_with_no_twitter_threads_returns_none(self):
        """Test Twitter channel when no twitter_threads."""
        state = Mock()
        state.social_content = Mock()
        state.social_content.twitter_threads = None

        generator = ReportGenerator(state)
        result = generator._identify_twitter_channel()

        assert result is None, "Should return None when no twitter_threads"


class TestMarketingChannelOrchestration:
    """Test suite for _identify_marketing_channels() orchestrator."""

    def test_with_all_channels_returns_three(
        self, mock_reddit_posts, mock_enriched_keywords, mock_twitter_threads
    ):
        """Test orchestrator with all 3 channels available."""
        state = Mock()
        state.social_content = Mock()
        state.social_content.reddit_posts = mock_reddit_posts
        state.social_content.twitter_threads = mock_twitter_threads
        state.seo_strategy_report = Mock()
        state.seo_strategy_report.tier_1_keywords = mock_enriched_keywords
        state.sources_searched = None  # No source coverage tracking in this test

        generator = ReportGenerator(state)
        result = generator._identify_marketing_channels()

        assert len(result) == 3, f"Expected 3 channels, got {len(result)}"
        assert result[0].channel_type == "Community"  # Reddit first
        assert result[1].channel_type == "SEO"  # SEO second
        assert result[2].channel_type == "Social"  # Twitter third

    def test_with_partial_channels_returns_available(self, mock_reddit_posts):
        """Test orchestrator with only some channels available."""
        state = Mock()
        state.social_content = Mock()
        state.social_content.reddit_posts = mock_reddit_posts
        state.social_content.twitter_threads = None
        state.seo_strategy_report = None
        state.sources_searched = None

        generator = ReportGenerator(state)
        result = generator._identify_marketing_channels()

        assert len(result) == 1, f"Expected 1 channel, got {len(result)}"
        assert result[0].channel_type == "Community"

    def test_with_no_channels_returns_empty_list(self):
        """Test orchestrator with no channels available."""
        state = Mock()
        state.social_content = None
        state.seo_strategy_report = None
        state.sources_searched = None

        generator = ReportGenerator(state)
        result = generator._identify_marketing_channels()

        assert result == [], "Should return empty list when no channels"

    def test_exception_handling_returns_empty_list(self):
        """Test orchestrator exception handling."""
        state = Mock()
        # Create a mock that raises exception on attribute access
        state.social_content = Mock()
        state.social_content.reddit_posts = Mock(side_effect=Exception("Test error"))

        generator = ReportGenerator(state)
        result = generator._identify_marketing_channels()

        assert result == [], "Should return empty list on exception"
