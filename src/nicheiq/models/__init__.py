"""
Pydantic models for NicheIQ data structures.
"""

from .competitor import (
    CompetitiveAnalysisResult,
    CompetitiveLandscape,
    Competitor,
    CompetitorType,
    MarketSaturation,
)
from .keyword_data import (
    GeographicBreakdown,
    Keyword,
    KeywordCluster,
    KeywordIntent,
    KeywordResearchReport,
    KeywordValidationResult,
    OpportunityLevel,
)
from .pain_point import PainPoint, PainPointAnalysisResult
from .research_state import (
    FinalReport,
    NicheContext,
    ResearchState,
    SearchQuery,
)
from .social_content import (
    RedditComment,
    RedditPost,
    SocialContentCollection,
    TwitterThread,
    TwitterTweet,
)
from .solution_idea import BaseSolutionIdea, IdeaGenerationResult, SolutionIdea
from .solution_refinement import SolutionRefinement
from .solution_selection import SolutionSelection
from .seo_strategy import SEOStrategyReport

__all__ = [
    # Pain Points
    "PainPoint",
    "PainPointAnalysisResult",
    # Solution Ideas
    "BaseSolutionIdea",
    "SolutionIdea",
    "IdeaGenerationResult",
    # Competitors
    "Competitor",
    "CompetitorType",
    "MarketSaturation",
    "CompetitiveLandscape",
    "CompetitiveAnalysisResult",
    # Keywords
    "Keyword",
    "KeywordIntent",
    "OpportunityLevel",
    "KeywordCluster",
    "GeographicBreakdown",
    "KeywordResearchReport",
    "KeywordValidationResult",
    # Social Content
    "RedditPost",
    "RedditComment",
    "TwitterTweet",
    "TwitterThread",
    "SocialContentCollection",
    # Research State
    "NicheContext",
    "SearchQuery",
    "FinalReport",
    "ResearchState",
    # Solution Refinement & Selection
    "SolutionRefinement",
    "SolutionSelection",
    # SEO Strategy
    "SEOStrategyReport",
]
