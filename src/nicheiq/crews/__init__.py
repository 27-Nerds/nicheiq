"""
Specialized CrewAI crews for different stages of the research pipeline.
"""

from .audience_mapping_crew import AudienceMappingCrew
from .data_source_crew import DataSourceResearchCrew
from .market_sizing_crew import MarketSizingCrew
from .pain_point_crew import PainPointCrew
from .pricing_strategy_crew import PricingStrategyCrew
from .seo_strategy_crew import SEOStrategyCrew
from .solution_refinement_crew import SolutionRefinementCrew
from .trend_longevity_crew import TrendLongevityCrew
from .unified_solution_crew import UnifiedSolutionCrew

__all__ = [
    "PainPointCrew",
    "SEOStrategyCrew",
    "DataSourceResearchCrew",
    "UnifiedSolutionCrew",
    "SolutionRefinementCrew",
    "PricingStrategyCrew",
    "AudienceMappingCrew",
    "MarketSizingCrew",
    "TrendLongevityCrew",
]
