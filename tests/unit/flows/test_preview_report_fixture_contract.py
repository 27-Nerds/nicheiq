"""The Phase-1 preview report, GENERATED from the real materializer and vendored.

WHY THIS EXISTS. `_materialize_preview_report` writes the JSON the SvelteKit job page
fetches verbatim, and it assembles its 23 sections inside blocks that each end
`except Exception: logger.debug(...)`. That combination is the sharpest version of the
defect this program is closing: a `SimpleNamespace` idea missing one field raises inside a
section block, the section vanishes from the JSON entirely, the page renders without it,
and the swallowed exception is a DEBUG line nobody reads. `test_preview_portfolio_summary.py`
and `test_preview_idea_theses.py` drive this producer with exactly that — a real
`ResearchState` whose `idea_generation` has been swapped for
`SimpleNamespace(solution_ideas=[SimpleNamespace(...)])` — and each asserts one section, so
a fail-soft that deleted the other 22 would pass both.

`tests/unit/flows/test_audience_drift_live_path.py` already holds one field of one section
this way (`audienceDriftNotice.exemplar.json`). This file holds the whole document: the real
materializer over the real captured 8f35ea6b run state, restored by the real
`CheckpointManager` (see `tests/unit/report/report_run_8f35ea6b.py`), persisting through the
real checkpoint manager rather than a `Mock`.

Regenerate after any deliberate change to the preview:

    PREVIEW_REPORT_FIXTURE_REGEN=1 pytest tests/unit/flows/test_preview_report_fixture_contract.py

and commit the JSON.

NORMALIZED, and only this one, because it is the only wall-clock field left: `generated_at`.
`research_metadata.collection_date` used to be normalized alongside it, because the preview
path stamped `now()` while the report path (`ReportGenerator._generate_research_metadata`)
filled the SAME field of the SAME model from `social_content.collection_timestamp` — two
producers, one field, two weeks apart on this run. The preview now reads the corpus
timestamp like the report does, so the value is a property of the captured run rather than
of the clock, and it is pinned in the vendored JSON instead of being dropped.
`test_both_collection_date_producers_agree` holds the reconciliation directly.

NOT COVERED: `_refresh_idea_portfolio_summary`, stubbed out exactly as the audience-drift
production-path test stubs it. It is an LLM pass gated on a candidate-set fingerprint, so
leaving it live would make this fixture depend on whether the machine running the suite has
an API key — a fixture whose value changes with the environment is not a contract. Its
output field, `idea_portfolio_summary`, therefore rides in from the captured run's own
metadata, which is where a resumed run gets it too.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.report.report_generator import ReportGenerator

from ..report.report_run_8f35ea6b import JOB_ID, load_run

VENDORED_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests" / "fixtures" / "generated" / "previewReport.generated.json"
)

# Wall-clock, and nothing else. `test_the_only_unstable_fields_are_wall_clock` holds it.
WALL_CLOCK_FIELDS = (("generated_at",),)


def _drop_wall_clock(document: dict) -> dict:
    for path in WALL_CLOCK_FIELDS:
        node = document
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict):
            node.pop(path[-1], None)
    return document


def _build(tmp_path) -> dict:
    state, manager = load_run(tmp_path)

    flow = ResearchFlow.__new__(ResearchFlow)
    flow.job_id = JOB_ID
    flow.niche_description = state.niche_context.niche_description
    flow._state = state
    flow.checkpoint_mgr = manager
    # See the module docstring: LLM pass, gated on a fingerprint, stubbed the same way the
    # existing production-path test stubs it. Everything else in the materializer runs.
    flow._refresh_idea_portfolio_summary = lambda **_kwargs: False

    output_dir = Path(tmp_path) / "preview_out"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = flow._materialize_preview_report(str(output_dir))
    assert path is not None, (
        "_materialize_preview_report returned None on a complete captured run. It is "
        "fail-soft end to end, so None here means the whole document was dropped."
    )
    return _drop_wall_clock(json.loads(Path(path).read_text()))


def _check(path: Path, generated: dict) -> None:
    if os.environ.get("PREVIEW_REPORT_FIXTURE_REGEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")

    assert json.loads(path.read_text()) == generated, (
        f"The vendored preview report ({path.name}) has drifted from what "
        f"_materialize_preview_report actually writes. Regenerate it:\n  "
        f"PREVIEW_REPORT_FIXTURE_REGEN=1 pytest tests/unit/flows/{Path(__file__).name}\n"
        "Do NOT hand-edit the JSON. If a whole section disappeared, look for a raise inside "
        "its `except Exception: logger.debug(...)` block before assuming the change was "
        "intended — that is how this document loses a section silently."
    )


def test_vendored_preview_report_matches_the_real_materializer(tmp_path):
    _check(VENDORED_PATH, _build(tmp_path))


def test_the_only_unstable_fields_are_wall_clock(tmp_path):
    """Guards the normalization list. A second unstable field must fail here rather than
    be quietly added to `WALL_CLOCK_FIELDS` to stop the drift test flapping."""
    assert _build(tmp_path / "a") == _build(tmp_path / "b")


def test_every_section_survives_the_fail_soft_blocks(tmp_path):
    """The defect this file exists for, as an assertion.

    Each section is assembled inside its own `except Exception: logger.debug(...)`, so the
    failure mode is a MISSING key, not a wrong value — and a missing key is invisible to any
    test that asserts on the sections it happens to care about. Named explicitly so a
    deletion has to be argued for.
    """
    document = _build(tmp_path)
    for section in (
        "niche", "niche_context", "detailed_pain_points", "pain_analysis_summary",
        "pain_point_analytics", "pain_total_mentions", "top_pain_categories",
        "audience_mapping", "content_categorization", "alternative_solutions",
        "idea_theses", "idea_portfolio_summary", "idea_portfolio_summary_fingerprint",
        "overlap_groups", "examined_ruled_out", "market_reality",
        "niche_difficulty_verdict", "overall_competitive_insights",
        "data_quality_summary", "evidence_appendix", "research_metadata",
        "user_adjusted", "user_adjustments",
    ):
        assert section in document, (
            f"{section} vanished from the preview. A fail-soft section block swallowed a "
            "raise; check the DEBUG log for the real exception."
        )
    # The control: sections are present AND carry the run's content, not empty shells.
    assert document["detailed_pain_points"]
    assert document["alternative_solutions"]
    assert document["niche"]


def test_both_collection_date_producers_agree(tmp_path):
    """One field, one meaning — asserted by driving BOTH producers over the same state.

    Replaces `test_the_two_collection_date_producers_disagree`, which pinned the divergence
    and asked to be deleted when it was reconciled. `research_metadata.collection_date` is
    written by the preview materializer AND by `ReportGenerator._generate_research_metadata`
    for the same run; the preview used to stamp materialization time, so the job page's
    payload said the evidence was gathered today while the report of the same run said two
    weeks ago. Both now read `social_content.collection_timestamp`.

    Asserting the two producers against each other rather than against a literal is the
    point: a change to either one alone fails here.
    """
    state, manager = load_run(tmp_path)
    corpus_timestamp = state.social_content.collection_timestamp

    flow = ResearchFlow.__new__(ResearchFlow)
    flow.job_id = JOB_ID
    flow.niche_description = state.niche_context.niche_description
    flow._state = state
    flow.checkpoint_mgr = manager
    flow._refresh_idea_portfolio_summary = lambda **_kwargs: False
    output_dir = Path(tmp_path) / "dates_out"
    output_dir.mkdir(parents=True, exist_ok=True)
    written = json.loads(
        Path(flow._materialize_preview_report(str(output_dir))).read_text()
    )
    preview_date = written["research_metadata"]["collection_date"]

    report_metadata = ReportGenerator(state)._generate_research_metadata()
    assert report_metadata is not None, (
        "the report path produced no research_metadata at all for a complete captured run"
    )

    assert preview_date == corpus_timestamp.isoformat(), (
        "the preview stamped something other than the corpus's own collection timestamp — "
        "if it is close to now(), the wall-clock stamp is back"
    )
    assert report_metadata.collection_date == corpus_timestamp
    assert preview_date == report_metadata.collection_date.isoformat(), (
        "the two producers of research_metadata.collection_date disagree again: preview "
        f"{preview_date!r} vs report {report_metadata.collection_date.isoformat()!r}"
    )


def test_preview_collection_date_is_null_when_there_is_no_corpus(tmp_path):
    """No scrape means no collection date — not a fresh-looking one.

    The report path returns no `research_metadata` at all without a corpus. The preview is
    fail-soft and always emits the block, so the honest value for a corpus-less run is null;
    stamping `now()` here is what let a catalog-seeded run claim its evidence was gathered
    today. The frontend already renders a missing value as "Not available"
    (`ReportContent.svelte`).
    """
    state, manager = load_run(tmp_path)
    state.social_content = None

    flow = ResearchFlow.__new__(ResearchFlow)
    flow.job_id = JOB_ID
    flow.niche_description = state.niche_context.niche_description
    flow._state = state
    flow.checkpoint_mgr = manager
    flow._refresh_idea_portfolio_summary = lambda **_kwargs: False
    output_dir = Path(tmp_path) / "no_corpus_out"
    output_dir.mkdir(parents=True, exist_ok=True)
    written = json.loads(
        Path(flow._materialize_preview_report(str(output_dir))).read_text()
    )

    assert written["research_metadata"]["collection_date"] is None
