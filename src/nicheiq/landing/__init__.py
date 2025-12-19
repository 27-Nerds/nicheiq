"""
Landing Page Generator module.

Generates unique, fully-designed HTML landing pages from NicheIQ research reports.

Usage:
    python -m nicheiq.landing --report output/final_report.json
    python -m nicheiq.landing --report output/final_report.json --output my_landing.html
"""

from ..crews.landing_page_crew import LandingPageCrew
from ..models.landing_page import (
    BrandIdentity,
    HTMLPageResult,
    LandingPageCopy,
    LandingPageResult,
    LandingPageSection,
)

__all__ = [
    "LandingPageCrew",
    "BrandIdentity",
    "LandingPageCopy",
    "LandingPageSection",
    "HTMLPageResult",
    "LandingPageResult",
]
