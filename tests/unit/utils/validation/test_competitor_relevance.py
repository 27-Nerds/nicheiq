"""Off-niche competitive-landscape guard.

Fixtures are the REAL records from live run 8ef396eb ("independent live music venues
coordinating artist settlements, door splits and ticketing reconciliation"), where the
winner's landscape came back as personal-finance apps: the researcher answered from the
solution name's prior ("HouseNut…Index" -> household budgeting) without running a single
search, and Mint + YNAB flowed into the report's competitor count, saturation and gaps.
The on-niche landscape from the SAME run is the negative control.
"""

import pytest

from nicheiq.models.competitor import CompetitiveLandscape
from nicheiq.models.research_state import NicheContext
from nicheiq.utils.validation.competitor_relevance import assess_landscape_relevance

# --- Real Stage-1 niche context from run 8ef396eb -------------------------------------
LIVE_MUSIC_CTX = NicheContext(
    niche_input=(
        "Independent live music venues coordinating artist settlements, door splits "
        "and ticketing reconciliation"
    ),
    niche_description=(
        "The independent live music venue management market encompasses the operational, "
        "financial, and logistical systems required to run small-to-mid-sized music "
        "performance spaces."
    ),
    market_segments=[
        "Independent venue owners managing multi-room performance spaces",
        "Bar and restaurant owners integrating live music as a primary revenue stream",
        "Non-profit community arts center managers hosting recurring concert series",
    ],
    industry_boundaries=(
        "This market is defined by the operational management of physical performance "
        "spaces and the financial reconciliation of live events."
    ),
    anchor_entities=[
        "Prism.fm", "VenuePilot", "Eventric Master Tour", "Eventbrite Music", "DICE",
        "Tixr", "See Tickets", "TicketSocket", "ShowClix", "Ticketmaster Universe",
        "Tixly", "Lyte", "ASCAP", "BMI", "SESAC",
    ],
    disambiguation_exclusions=[
        "Nightclub bottle-service and VIP-table operations",
        "Theater, arena, and stadium venue management",
        "Restaurant and bar point-of-sale reconciliation",
        "Music-streaming royalty accounting",
    ],
    audience_jargon=[
        "artist settlement", "settlement sheet", "door split", "versus deal",
        "house nut", "walkout amount", "box-office closeout", "ticket manifest",
    ],
    community_search_terms=[
        "independent venues", "venue operators", "live music venues",
        "concert promoters", "venue management",
    ],
)

# --- Real off-niche landscape (stage_5_5_competitive.json, written 00:52:00) -----------
HOUSENUT_LANDSCAPE = CompetitiveLandscape(
    solution_name="HouseNutIndex — Pre-Show Settlement Benchmarks for Independent Rooms",
    competitors=[
        {
            "name": "Mint",
            "url": "https://mint.intuit.com",
            "competitor_type": "direct",
            "description": "Comprehensive personal finance tracker and budgeting tool.",
            "key_features": [
                "Automated expense categorization", "Budget planning",
                "Credit score monitoring", "Investment tracking", "Bill reminders",
            ],
            "pricing_model": "Freemium (Ad-supported)",
            "strengths": ["Large user base", "Robust account connectivity"],
            "weaknesses": ["Lack of proactive financial coaching", "Privacy concerns"],
        },
        {
            "name": "You Need A Budget (YNAB)",
            "url": "https://www.ynab.com",
            "competitor_type": "direct",
            "description": "Zero-based budgeting software focused on behavior change.",
            "key_features": [
                "Zero-based budgeting system", "Real-time expense syncing",
                "Detailed financial reporting", "Goal tracking",
            ],
            "pricing_model": "Subscription (Annual/Monthly)",
            "strengths": ["High user engagement", "Effective methodology"],
            "weaknesses": ["Steep learning curve", "Limited investment planning features"],
        },
    ],
    market_gaps=[
        "Lack of personalized, actionable, real-time financial coaching",
        "Disconnect between budgeting tools and investment execution",
        "Insufficient support for complex tax-loss harvesting or estate planning "
        "for middle-income users",
        "Poor integration of behavioral psychology to improve spending habits",
        "Difficulty for users to see the long-term impact of current spending choices "
        "in a simulated way",
    ],
    differentiation_opportunities=[
        "Implement generative AI that acts as a human-like financial coach",
        "Gamification of debt reduction and savings milestones",
        "Integration of automated micro-investing based on daily budget surpluses",
    ],
    competitive_intensity=(
        "High; the personal finance management space is saturated with incumbents, but "
        "lacks highly proactive, personalized AI coaching."
    ),
    recommended_positioning=(
        "Position as the 'Proactive Financial Partner' rather than a passive 'Tracker', "
        "focusing on behavioral change and automated wealth-building."
    ),
    pricing_insights=(
        "Market trends favor a tiered subscription model (Freemium vs. Pro)."
    ),
)

# --- Real ON-niche landscape from the same run (negative control) ----------------------
SHOWCLOSE_LANDSCAPE = CompetitiveLandscape(
    solution_name="ShowClose Settlement Desk",
    competitors=[
        {
            "name": "Prism.fm",
            "url": "https://prism.fm/",
            "competitor_type": "direct",
            "description": "Booking and settlement platform for live music venues.",
            "key_features": ["Automated settlement from booking terms", "Ticket sales sync"],
        },
        {
            "name": "VenuePilot",
            "url": "https://www.venuepilot.com/",
            "competitor_type": "direct",
            "description": "Deals, deposits, settlement sheets and artist payouts.",
            "key_features": ["Settlement sheets", "Artist payouts", "Deposits"],
        },
    ],
    market_gaps=[
        "A cross-platform settlement layer for venues using different ticketing systems "
        "remains insufficiently served.",
        "No verified competitor publicly establishes an append-only, immutable event ledger.",
    ],
    differentiation_opportunities=["Bilateral pre-show approval lock"],
    competitive_intensity="High. Prism.fm, Opendate and VenuePilot all describe settlement.",
    recommended_positioning="A neutral approval/audit layer above existing ticketing stacks.",
    pricing_insights="Public pricing is limited for major music-venue platforms.",
)


class TestRealHouseNutIndexRegression:
    def test_real_personal_finance_landscape_is_flagged(self):
        verdict = assess_landscape_relevance(HOUSENUT_LANDSCAPE, LIVE_MUSIC_CTX)
        assert verdict["active"] is True
        assert verdict["off_niche"] is True
        assert verdict["coverage"] == 0.0
        assert "off-niche" in verdict["caveat"].lower()
        assert "UNVERIFIED" in verdict["caveat"]

    def test_real_on_niche_landscape_from_same_run_is_not_flagged(self):
        verdict = assess_landscape_relevance(SHOWCLOSE_LANDSCAPE, LIVE_MUSIC_CTX)
        assert verdict["off_niche"] is False
        assert verdict["coverage"] > 0.0

    def test_solution_name_alone_cannot_rescue_a_drifted_landscape(self):
        # The name is the drift source, so it is excluded from the judged text: renaming
        # the idea to something loudly on-niche must not silence the guard.
        drifted = HOUSENUT_LANDSCAPE.model_copy(
            update={"solution_name": "Live music venue artist settlement benchmarks"}
        )
        assert assess_landscape_relevance(drifted, LIVE_MUSIC_CTX)["off_niche"] is True


class TestFailOpen:
    @pytest.mark.parametrize("entities", [[], ["Prism.fm"], ["Prism.fm", "VenuePilot"]])
    def test_no_op_below_min_anchor_entities(self, entities):
        ctx = LIVE_MUSIC_CTX.model_copy(update={"anchor_entities": entities})
        verdict = assess_landscape_relevance(HOUSENUT_LANDSCAPE, ctx)
        assert verdict["active"] is False
        assert verdict["off_niche"] is False

    def test_no_niche_context_is_a_no_op(self):
        assert assess_landscape_relevance(HOUSENUT_LANDSCAPE, None)["off_niche"] is False

    def test_honest_empty_landscape_is_never_called_off_niche(self):
        # "No competitors found via search" is the correct abstain, not a drifted result.
        empty = HOUSENUT_LANDSCAPE.model_copy(update={
            "competitors": [],
            "market_gaps": ["No external search data available to identify market gaps.",
                            "Competitive landscape analysis requires real-time market data."],
            "differentiation_opportunities": [],
            "competitive_intensity": "Unknown",
            "recommended_positioning": "Unknown",
            "pricing_insights": "Unknown",
        })
        assert assess_landscape_relevance(empty, LIVE_MUSIC_CTX)["off_niche"] is False


class TestVocabularyRecall:
    def test_parenthetical_jargon_still_matches_the_plain_phrase(self):
        # "cottage food operation (CFO)" must match text that says "cottage food laws"
        # (real false positive from the home-bakers run before asides were stripped).
        ctx = NicheContext(
            niche_input="home bakers selling cakes and cookies under cottage food laws",
            niche_description="d", market_segments=["s"], industry_boundaries="b",
            anchor_entities=["Texas Cottage Food Law (HB 970)", "FDA Model Food Code",
                             "ServSafe Food Handler"],
            audience_jargon=["cottage food operation (CFO)", "gross sales cap"],
        )
        landscape = CompetitiveLandscape(
            solution_name="CottageFoodLawBot",
            competitors=[{
                "name": "Forrager",
                "competitor_type": "direct",
                "description": "Directory of cottage food laws with state-by-state summaries.",
                "key_features": ["State summaries"],
            }],
            market_gaps=["No plain-English yes/no validation", "High cognitive load"],
            differentiation_opportunities=["SMS interface"],
            competitive_intensity="High",
            recommended_positioning="Utility over directory",
            pricing_insights="Freemium",
        )
        assert assess_landscape_relevance(landscape, ctx)["off_niche"] is False

    def test_niche_identity_bigram_counts_as_niche_vocabulary(self):
        ctx = LIVE_MUSIC_CTX.model_copy(update={
            "audience_jargon": [], "community_search_terms": [],
        })
        landscape = CompetitiveLandscape(
            solution_name="ShowClose Settlement Desk",
            competitors=[{
                "name": "Unlisted Vendor",
                "competitor_type": "direct",
                "description": "Tooling for live music venues.",
                "key_features": ["Payouts"],
            }],
            market_gaps=["g1", "g2"],
            differentiation_opportunities=[],
            competitive_intensity="Medium",
            recommended_positioning="n/a",
            pricing_insights="n/a",
        )
        assert assess_landscape_relevance(landscape, ctx)["off_niche"] is False
