"""Flow-level handling of an off-niche competitive landscape.

Regression for run 8ef396eb: the on-demand competitive task had NO validation at all (the
guardrail lives on the batch task, which this path does not use), so a landscape the
researcher invented from the solution name's prior — Mint and YNAB for a live-music venue
niche — was checkpointed and fed to the report's competitor count, saturation and gaps.

Behaviour under test: reject once with a corrective retry, then keep the landscape verbatim
and stamp it (downgrade-only), never rewrite it.
"""

from types import SimpleNamespace

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.competitor import CompetitiveLandscape
from nicheiq.models.research_state import NicheContext

SOLUTION = "HouseNutIndex — Pre-Show Settlement Benchmarks for Independent Rooms"

# Real Stage-1 context and the two real landscapes from run 8ef396eb (the detector itself
# is covered in tests/unit/utils/validation/test_competitor_relevance.py).
LIVE_MUSIC_CTX = NicheContext(
    niche_input="Independent live music venues coordinating artist settlements",
    niche_description="Independent live music venue management.",
    market_segments=["Independent venue owners"],
    industry_boundaries="Operational management of physical performance spaces.",
    anchor_entities=["Prism.fm", "VenuePilot", "Eventbrite Music", "DICE"],
    audience_jargon=["artist settlement", "house nut"],
    community_search_terms=["independent venues", "live music venues"],
)

HOUSENUT_LANDSCAPE = CompetitiveLandscape(
    solution_name=SOLUTION,
    competitors=[
        {
            "name": "Mint",
            "url": "https://mint.intuit.com",
            "competitor_type": "direct",
            "description": "Comprehensive personal finance tracker and budgeting tool.",
            "key_features": ["Automated expense categorization", "Budget planning"],
        },
        {
            "name": "You Need A Budget (YNAB)",
            "url": "https://www.ynab.com",
            "competitor_type": "direct",
            "description": "Zero-based budgeting software focused on behavior change.",
            "key_features": ["Zero-based budgeting system", "Goal tracking"],
        },
    ],
    market_gaps=[
        "Lack of personalized, actionable, real-time financial coaching",
        "Disconnect between budgeting tools and investment execution",
    ],
    differentiation_opportunities=["Gamification of debt reduction and savings milestones"],
    competitive_intensity="High; the personal finance management space is saturated.",
    recommended_positioning="Position as the 'Proactive Financial Partner'.",
    pricing_insights="Market trends favor a tiered subscription model.",
)

SHOWCLOSE_LANDSCAPE = CompetitiveLandscape(
    solution_name="ShowClose Settlement Desk",
    competitors=[
        {
            "name": "Prism.fm",
            "url": "https://prism.fm/",
            "competitor_type": "direct",
            "description": "Booking and settlement platform for live music venues.",
            "key_features": ["Automated settlement from booking terms"],
        },
    ],
    market_gaps=["A cross-platform settlement layer for venues remains underserved.", "g2"],
    differentiation_opportunities=["Bilateral pre-show approval lock"],
    competitive_intensity="High. Prism.fm and VenuePilot both describe settlement.",
    recommended_positioning="A neutral approval layer above existing ticketing stacks.",
    pricing_insights="Public pricing is limited for major music-venue platforms.",
)


class _Crew:
    """Minimal stand-in for the mini competitive crew."""

    def __init__(self, retry_result):
        self._retry_result = retry_result
        self.kickoffs = 0

    def kickoff(self):
        self.kickoffs += 1
        if isinstance(self._retry_result, Exception):
            raise self._retry_result
        return SimpleNamespace(pydantic=self._retry_result)


def _guard(landscape, retry_result):
    flow = SimpleNamespace(
        state=SimpleNamespace(niche_context=LIVE_MUSIC_CTX, pipeline_degradations=[])
    )
    crew = _Crew(retry_result)
    task = SimpleNamespace(description="ORIGINAL")
    result = ResearchFlow._guard_landscape_on_niche(
        flow, landscape, SOLUTION, crew, task, "ORIGINAL"
    )
    return result, flow, crew, task


class TestOffNicheGuard:
    def test_on_niche_landscape_passes_through_without_a_retry(self):
        result, flow, crew, _ = _guard(SHOWCLOSE_LANDSCAPE, None)
        assert result is SHOWCLOSE_LANDSCAPE
        assert crew.kickoffs == 0
        assert flow.state.pipeline_degradations == []
        assert result.off_niche_caveat is None

    def test_off_niche_landscape_triggers_one_corrective_retry(self):
        result, flow, crew, task = _guard(HOUSENUT_LANDSCAPE, SHOWCLOSE_LANDSCAPE)
        assert crew.kickoffs == 1
        assert result is SHOWCLOSE_LANDSCAPE
        assert result.off_niche_caveat is None
        assert flow.state.pipeline_degradations == []
        assert "YOUR PREVIOUS ANSWER WAS REJECTED" in task.description
        assert task.description.startswith("ORIGINAL")

    def test_second_off_niche_answer_is_caveated_not_rewritten(self):
        second = CompetitiveLandscape.model_validate(HOUSENUT_LANDSCAPE.model_dump())
        result, flow, crew, _ = _guard(HOUSENUT_LANDSCAPE, second)
        assert crew.kickoffs == 1
        # Downgrade-only: the competitors survive verbatim, the claim is marked unverified.
        assert [c.name for c in result.competitors] == ["Mint", "You Need A Budget (YNAB)"]
        assert result.off_niche_caveat is not None
        assert len(flow.state.pipeline_degradations) == 1
        assert flow.state.pipeline_degradations[0].startswith(SOLUTION)

    def test_failed_retry_keeps_the_first_landscape_and_caveats_it(self):
        result, flow, crew, _ = _guard(HOUSENUT_LANDSCAPE, RuntimeError("rate limited"))
        assert crew.kickoffs == 1
        assert result is HOUSENUT_LANDSCAPE
        assert result.off_niche_caveat is not None
        assert len(flow.state.pipeline_degradations) == 1

    def test_caveat_names_the_downstream_metrics_it_invalidates(self):
        result, _, _, _ = _guard(
            CompetitiveLandscape.model_validate(HOUSENUT_LANDSCAPE.model_dump()),
            RuntimeError("no retry"),
        )
        caveat = result.off_niche_caveat
        assert "saturation" in caveat
        assert "UNVERIFIED" in caveat
