"""ReportGenerator._generate_market_reality — the final-report side of the market-data handoff
(utils/market_brief.py). Mirrors the preview-report test in
tests/unit/flows/test_market_reality_preview.py."""

from nicheiq.models.research_state import ResearchState
from nicheiq.report.report_generator import ReportGenerator


def test_none_when_no_probe_data():
    gen = ReportGenerator(ResearchState())
    assert gen._generate_market_reality() is None


def test_populated_when_incumbents_present():
    state = ResearchState()
    state.niche_incumbent_map = [
        {"name": "Aftershoot", "pricing": "$29/mo", "focus": "AI culling", "gap": "no galleries",
         "source": "web"}
    ]
    gen = ReportGenerator(state)
    result = gen._generate_market_reality()
    assert result == {
        "incumbents": [{"name": "Aftershoot", "pricing": "$29/mo", "focus": "AI culling",
                         "gap": "no galleries", "source": "web"}],
        "wallet": {},
    }


def test_populated_when_only_wallet_present():
    state = ResearchState()
    state.niche_wallet_brief = {"wallet_class": "mixed", "evidence": "most tools $10-30/mo"}
    gen = ReportGenerator(state)
    result = gen._generate_market_reality()
    assert result == {"incumbents": [], "wallet": {"wallet_class": "mixed",
                                                     "evidence": "most tools $10-30/mo"}}
