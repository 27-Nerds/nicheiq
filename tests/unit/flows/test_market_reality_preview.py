"""_materialize_preview_report must emit the market-data handoff (utils/market_brief.py) at a
top-level market_reality key — the same Phase-1 web-verified incumbent/wallet facts the final
report's market_reality carries and Stage-2 deep research consumes (mirrors
test_preview_report_content_categorization.py's pattern for content_categorization/angle fields)."""

from __future__ import annotations

import json
from pathlib import Path

from nicheiq.flows.research_flow import ResearchFlow

NICHE = "AI productivity tools for indie hackers"


def _read_preview(tmp_path: Path) -> dict:
    files = list(tmp_path.glob("preview_report_*.json"))
    assert len(files) == 1, f"expected one preview report, got {files}"
    return json.loads(files[0].read_text())


def test_market_reality_populated_when_probes_found_data(tmp_path):
    flow = ResearchFlow(niche_description=NICHE, job_id="test-job-market-1")
    flow.state.niche_incumbent_map = [
        {"name": "Aftershoot", "pricing": "$29/mo", "focus": "AI culling", "gap": "no galleries",
         "source": "web"}
    ]
    flow.state.niche_wallet_brief = {"wallet_class": "mixed", "evidence": "most tools $10-30/mo",
                                      "free_density": "few free routes"}

    path = flow._materialize_preview_report(str(tmp_path))
    assert path is not None

    report = _read_preview(tmp_path)
    mr = report["market_reality"]
    assert mr is not None
    assert mr["incumbents"][0]["name"] == "Aftershoot"
    assert mr["wallet"]["wallet_class"] == "mixed"


def test_market_reality_present_but_empty_when_no_probe_data(tmp_path):
    """Always-present-but-empty shape (not omitted) so the frontend never has to special-case
    a missing key — mirrors the examined_ruled_out / overlap_groups pattern in the same block."""
    flow = ResearchFlow(niche_description=NICHE, job_id="test-job-market-2")

    path = flow._materialize_preview_report(str(tmp_path))
    assert path is not None

    report = _read_preview(tmp_path)
    assert report["market_reality"] == {"incumbents": [], "wallet": {}}
