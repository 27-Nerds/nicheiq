"""Model-authored text must reach downstream prompts (and downstream STORAGE) whole.

Four producers used to cut model-authored fields at guessed character limits before the text
reached an LLM — limits measured (3.7k checkpoint JSONs) to bind on 88-100% of real values,
cutting mid-word with no ellipsis:

  * ``technical_blueprint_crew``  — ``description[:500]``   (idea description median 870, 93.9% bind)
  * ``landing_page_crew``         — ``pricing_rationale[:200]`` (median 594, 100% bind) + 4 more
  * ``idea_improvement_loop_v4``  — a WRITE cap on ``data_acquisition_notes`` (160/200/120)
  * ``public_data_sources``       — a second ``[:400]`` on an already-cut ``context``

These assert the PROPERTY (the author's text arrives intact; a runaway is marked, never silent),
not the prose. Real pydantic models throughout — MagicMock swallows field errors and has produced
false greens in this repo. All LLM/crew calls are mocked; nothing here touches the network.
"""

import pytest
from pydantic import BaseModel, ValidationError

from nicheiq.crews import idea_improvement_loop_v4 as v4
from nicheiq.crews.idea_improvement_loop_v4 import DataRouteVerdict, verify_data_routes
from nicheiq.crews.landing_page_crew import LandingPageCrew
from nicheiq.crews.technical_blueprint_crew import TechnicalBlueprintCrew
from nicheiq.models.research_state import FinalReport, PricingStrategyResult
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.utils import llm_service as llm_service_mod
from nicheiq.utils import public_data_sources as pds
from nicheiq.utils.content_security import PROMPT_FIELD_MAX

# A description at the real median (870 chars) -- the old [:500] removed 42% of it.
LONG_DESCRIPTION = (
    "Shop owners paste the OEM part number and the tool watches the three distributor feeds "
    "they already have accounts with, then reconciles the promised ship date against the "
    "carrier scan so a part that silently slipped from Tuesday to the following Monday shows "
    "up as an exception on one board instead of being discovered when the customer calls. "
    "The reconciliation runs nightly and only surfaces parts whose promised date moved by more "
    "than one business day, which is the threshold shops said actually changes what they tell "
    "the customer. Everything below that threshold stays silent so the board does not become "
    "another inbox nobody reads by the second week of using it in a real service department. "
    "Slipped parts are attached to the open repair order they belong to, so the service writer "
    "sees the delay in the same place they already look before calling the customer back."
)


def _assert_intact(rendered: str, original: str, label: str, old_cap: int = 500) -> None:
    """The author's text arrives whole and unmarked (it is far under the runaway backstop).

    ``old_cap`` is the constant this site used to cut at; the fixture must exceed it or the
    test would pass against the unfixed code. Defaults to 500 (the most common old constant).
    """
    assert len(original) > old_cap, f"{label}: fixture too short to exercise the old cap"
    assert len(original) < PROMPT_FIELD_MAX, f"{label}: fixture must not trip the backstop"
    assert original in rendered, (
        f"{label}: text was cut -- {len(original)} chars in, "
        f"{len(rendered)} out: ...{rendered[-60:]!r}"
    )
    assert "[truncated]" not in rendered, f"{label}: backstop fired on a normal-length value"


# --------------------------------------------------------------------------------------
# Site 1: technical_blueprint_crew -- description / value_proposition / pricing_strategy
# --------------------------------------------------------------------------------------


class _CapturedResult:
    tasks_output: list = []


class _CapturingCrew:
    """Stands in for the CrewAI Crew: records the inputs dict, runs no agents."""

    usage_metrics = None

    def __init__(self):
        self.inputs = None

    def kickoff(self, inputs=None):
        self.inputs = inputs
        return _CapturedResult()


def _blueprint_inputs(**overrides) -> dict:
    crew = TechnicalBlueprintCrew()
    captured = _CapturingCrew()
    crew.crew = lambda: captured  # noqa: E731 -- instance-level stub, no agents built
    kwargs = dict(
        solution_name="Part Limbo Board",
        description=LONG_DESCRIPTION,
        project_type="saas",
        core_features=["exception board"],
        target_personas=["service manager"],
        data_sources=["distributor feed"],
        estimated_indexable_pages=50,
        content_generation_model="Manual content",
        value_proposition="Catch slipped parts before the customer does.",
        organic_discovery_queries=["part delay tracker"],
        pricing_strategy="Flat monthly per location.",
    )
    kwargs.update(overrides)
    crew.generate(**kwargs)
    assert captured.inputs is not None, "crew.kickoff was never reached"
    return captured.inputs


def test_blueprint_description_reaches_crew_inputs_in_full():
    inputs = _blueprint_inputs()
    _assert_intact(inputs["description"], LONG_DESCRIPTION, "blueprint description")


def test_blueprint_value_proposition_fallback_to_description_is_not_cut():
    # value_proposition is optional; when it is absent the description is the fallback, and the
    # old [:300] cut that fallback on essentially every real idea (median description 870).
    inputs = _blueprint_inputs(value_proposition="")
    _assert_intact(
        inputs["value_proposition"], LONG_DESCRIPTION, "blueprint value_proposition fallback"
    )


def test_blueprint_pricing_strategy_reaches_crew_inputs_in_full():
    # pricing_strategy prose measured median 326 -- the old [:300] bound 58% of real values.
    pricing = "Flat monthly per location, billed annually. " * 12
    inputs = _blueprint_inputs(pricing_strategy=pricing)
    _assert_intact(inputs["pricing_strategy"], pricing, "blueprint pricing_strategy")


def test_blueprint_runaway_value_is_marked_not_silently_cut():
    runaway = "x" * (PROMPT_FIELD_MAX + 500)
    inputs = _blueprint_inputs(description=runaway)
    rendered = inputs["description"]
    assert len(rendered) < len(runaway)
    assert rendered.endswith("[truncated]"), "a backstop cut must be visible to the reader"


def test_blueprint_missing_description_renders_empty_string():
    inputs = _blueprint_inputs(description=None, value_proposition="Some value.")
    assert inputs["description"] == ""


# --------------------------------------------------------------------------------------
# Site 2: landing_page_crew -- report prose feeding the 8-agent prompt chain
# --------------------------------------------------------------------------------------

LONG_RATIONALE = (
    "Shops anchor on the parts-markup line they already understand, so a per-location flat fee "
    "reads as overhead rather than as a share of a recovered job; the interviews put the "
    "willingness-to-pay band at roughly forty to ninety dollars a month per location, with the "
    "top of that band available only where the shop can point at a specific comeback the tool "
    "would have caught. Pricing above that band moved the conversation to a procurement review "
    "the buyer does not control, which is why the recommendation is a single tier with the "
    "second seat free rather than a usage-metered plan that makes the invoice unpredictable."
)


def _report(**overrides) -> FinalReport:
    fields = dict(
        niche="independent auto repair shops",
        executive_summary=LONG_DESCRIPTION,
        selected_solution_name="Part Limbo Board",
        selection_rationale="Highest severity pain with a reachable buyer.",
        pain_points_summary=LONG_DESCRIPTION,
        recommended_solutions=["Part Limbo Board"],
        solutions_summary="One board for slipped parts.",
        competitive_summary=LONG_DESCRIPTION,
        market_validation="Validated across ten threads.",
        data_sourcing_recommendations="Distributor feeds the shop already has.",
        next_steps=["Interview five shops"],
    )
    fields.update(overrides)
    return FinalReport(**fields)


def _landing_inputs(**overrides) -> dict:
    return LandingPageCrew()._extract_inputs(_report(**overrides))


def _pricing(rationale: str) -> PricingStrategyResult:
    return PricingStrategyResult(
        solution_name="Part Limbo Board",
        pricing_model="Subscription",
        pricing_rationale=rationale,
        estimated_arpu="$59",
        estimated_ltv="$1400",
        ltv_to_cac_ratio="4.2",
        price_vs_competitors="in line",
        value_proposition_delta="catches slips a week earlier",
        pricing_confidence="Medium",
        wtp_validation="ten shop interviews",
        recommended_starter_price="$49/mo",
        recommended_pro_price="$99/mo",
    )


def test_landing_pricing_rationale_reaches_prompt_in_full():
    inputs = _landing_inputs(pricing_strategy=_pricing(LONG_RATIONALE))
    _assert_intact(inputs["pricing_summary"], LONG_RATIONALE, "landing pricing_rationale")


def test_landing_report_prose_reaches_prompt_in_full():
    inputs = _landing_inputs(mvp_scope_definition=LONG_DESCRIPTION)
    for key in ("value_proposition", "pain_points_summary", "competitive_summary", "mvp_features"):
        _assert_intact(inputs[key], LONG_DESCRIPTION, f"landing {key}")


def test_landing_absent_optional_prose_renders_empty_string():
    inputs = _landing_inputs()
    assert inputs["mvp_features"] == ""


def test_landing_runaway_value_is_marked_not_silently_cut():
    runaway = "y" * (PROMPT_FIELD_MAX + 500)
    inputs = _landing_inputs(competitive_summary=runaway)
    assert inputs["competitive_summary"].endswith("[truncated]")


# --------------------------------------------------------------------------------------
# Site 3: idea_improvement_loop_v4 -- the WRITE cap on data_acquisition_notes
# --------------------------------------------------------------------------------------

# The verifier's note is the only record of WHY a route failed; it is both re-read into
# downstream prompts and rendered in the UI's Data badge, so a cut here is unrecoverable.
LONG_NOTE = (
    "The county publishes the assessor roll as a quarterly ZIP of fixed-width text behind an "
    "unauthenticated link, but the parcel-to-owner crosswalk the product needs lives in a "
    "separate recorder system whose bulk export is available only to title companies under a "
    "signed data-use agreement; the public web search returns individual parcels one at a time "
    "with a session cookie and a rate limit that makes a nightly full refresh impossible, so "
    "the claimed daily-ownership-change feature cannot be built off the public route as stated."
)


def _verify_idea(**fields) -> BaseSolutionIdea:
    base = dict(
        solution_name="Ownership Change Watch",
        description="Watches recorded ownership changes.",
        value_proposition="Know who bought what, the day after.",
        pain_points_addressed=["stale ownership data"],
        core_features=["nightly diff"],
        target_personas=["title researcher"],
        # Deliberately NOT an allowlist-known source: keeps the well-known-source
        # short circuit out of the way so the web-verify branches run.
        data_sources=["Zzyzx County proprietary recorder crosswalk"],
    )
    base.update(fields)
    return BaseSolutionIdea(**base)


def _run_verify(monkeypatch, verdict: DataRouteVerdict, **idea_fields) -> BaseSolutionIdea:
    idea = _verify_idea(**idea_fields)
    monkeypatch.setattr(
        v4.LLMService, "invoke_structured", staticmethod(lambda *a, **k: (verdict, None))
    )
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    return idea


@pytest.mark.parametrize(
    "verdict_kwargs, expected_route",
    [
        # branch 1: refuted -> blocked
        (dict(self_sourced=False, verdict="refuted", access_model="blocked", obtainable=False),
         "blocked"),
        # branch 2: not_enough_info -> unverified (fixed prefix + note)
        (dict(self_sourced=False, verdict="not_enough_info", access_model="official",
              obtainable=True),
         "unverified"),
        # branch 3: supported, route changed vs prior -> canonical route label
        (dict(self_sourced=False, verdict="supported", access_model="unofficial",
              obtainable=True),
         "unofficial"),
    ],
    ids=["blocked", "unverified", "route-changed"],
)
def test_verifier_note_is_stored_whole_on_every_branch(monkeypatch, verdict_kwargs, expected_route):
    verdict = DataRouteVerdict(note=LONG_NOTE, **verdict_kwargs)
    idea = _run_verify(monkeypatch, verdict, data_access_model="unverified")
    assert idea.data_access_model == expected_route, "wrong branch exercised"
    _assert_intact(idea.data_acquisition_notes, LONG_NOTE, f"v4 {expected_route} note")


def test_unverified_prefix_does_not_eat_the_notes_budget(monkeypatch):
    """The fixed disclaimer must not consume the model's share of any cap.

    The old code capped ``prefix + note`` at 200 with a ~135-char prefix, so the verifier's
    finding survived at ~65 chars regardless of how much it wrote.
    """
    verdict = DataRouteVerdict(self_sourced=False, verdict="not_enough_info",
                               access_model="official", obtainable=True, note=LONG_NOTE)
    idea = _run_verify(monkeypatch, verdict, data_access_model="public")
    stored = idea.data_acquisition_notes
    assert stored.startswith("Data route UNVERIFIED"), "disclaimer must still lead"
    assert LONG_NOTE in stored


def test_verifier_runaway_note_is_marked_not_silently_cut(monkeypatch):
    runaway = "z" * (PROMPT_FIELD_MAX + 500)
    verdict = DataRouteVerdict(self_sourced=False, verdict="refuted", access_model="blocked",
                               obtainable=False, note=runaway)
    idea = _run_verify(monkeypatch, verdict, data_access_model="unverified")
    assert idea.data_acquisition_notes.endswith("[truncated]")


# --------------------------------------------------------------------------------------
# Site 4: public_data_sources -- the stacked [:400] on the allowlist-confirm prompt
# --------------------------------------------------------------------------------------

LONG_CLAIM = (
    "NEEDS-VERIFY: does the federal contract-opportunities API expose the amendment history "
    "for a solicitation, or only the current revision? The product's whole premise is diffing "
    "successive amendments to a posted solicitation so a small vendor learns that the scope "
    "moved before the bid is due, and if only the current revision is retrievable then the "
    "diff has to be reconstructed from our own nightly snapshots instead of from the source. "
    "The same question applies to the attachments list, which is where the statement of work "
    "actually lives for most of these solicitations and is the part a bidder cares about."
)


class _PromptSpy:
    def __init__(self):
        self.prompt = None

    def __call__(self, *args, **kwargs):
        self.prompt = kwargs["prompt"]

        class _Confirm:
            confirmed = False
            note = ""

        return _Confirm(), None


def _confirm_prompt(monkeypatch, matches, context) -> str:
    spy = _PromptSpy()
    monkeypatch.setattr(
        llm_service_mod.LLMService, "invoke_structured", staticmethod(spy)
    )
    pds.llm_confirm_known_route(matches, context=context)
    assert spy.prompt is not None, "the confirm LLM was never called"
    return spy.prompt


def test_allowlist_confirm_prompt_carries_the_full_idea_context(monkeypatch):
    prompt = _confirm_prompt(monkeypatch, [("SAM.gov opportunities", "SAM.gov")], LONG_CLAIM)
    _assert_intact(prompt, LONG_CLAIM, "allowlist confirm context")


def test_allowlist_confirm_prompt_carries_the_full_claim_text(monkeypatch):
    prompt = _confirm_prompt(monkeypatch, [(LONG_CLAIM, "SAM.gov")], "")
    _assert_intact(prompt, LONG_CLAIM, "allowlist confirm claim")


def test_v4_hands_the_allowlist_confirmer_an_uncut_claim(monkeypatch):
    """The caller must not pre-cut: two independent [:400] slices stacked on one string."""
    seen = {}

    def _fake_confirm(matches, *, context=""):
        seen["context"] = context
        return None

    monkeypatch.setattr(v4, "llm_confirm_known_route", _fake_confirm)
    monkeypatch.setattr(v4, "retrieve_known_sources", lambda parts: [("claim", "SAM.gov")])
    monkeypatch.setattr(
        v4.LLMService,
        "invoke_structured",
        staticmethod(lambda *a, **k: (
            DataRouteVerdict(self_sourced=False, verdict="not_enough_info",
                             access_model="official", obtainable=True, note=""),
            None,
        )),
    )
    idea = _verify_idea(technical_approach=f"[NEEDS-VERIFY: {LONG_CLAIM}]")
    verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert "context" in seen, "the allowlist pre-pass never ran"
    _assert_intact(seen["context"], LONG_CLAIM, "v4 -> allowlist claim")


# --------------------------------------------------------------------------------------
# Site 5: idea_improvement_loop_v4 -- the schema-repair retry turn
# --------------------------------------------------------------------------------------
# `_improve` catches a BaseSolutionIdea schema violation and re-asks the model with the
# validation error attached. The error text is a pydantic repr rather than model-authored
# prose, but the property that matters is the same: an LLM is being asked to act on a
# decision input it cannot fully see. A real BaseSolutionIdea ValidationError measures
# 872-988 chars (6 missing fields -> 988), so the old [:500] hid 1-3 of the very field
# names the repair turn exists to fix -- the model repairs what it can see, resubmits, and
# fails again on the hidden ones. The loop cannot converge.


def _validation_error(**partial) -> ValidationError:
    """A REAL BaseSolutionIdea ValidationError -- the field list is pydantic's, not ours."""
    try:
        BaseSolutionIdea(**partial)
    except ValidationError as exc:
        return exc
    raise AssertionError("payload was valid; the fixture must violate the schema")


def _missing_fields(exc: ValidationError) -> list[str]:
    return [str(e["loc"][0]) for e in exc.errors()]


def _repair_prompt(exc: ValidationError) -> str:
    """Drive _improve through its retry branch and return the repair message it appends."""
    # `_is_idea_schema_contract_error` gates on the wrapper the structured-output client
    # raises, not on the bare pydantic error; the class name is taken from the real
    # exception rather than spelled out, so the gate token cannot drift from reality.
    wrapped = ValueError(f"Tool payload {type(exc).__name__}: {exc}")
    calls = {"n": 0}

    def invoke(messages, output_model, *, temperature, model_name, reasoning_effort):
        calls["n"] += 1
        if calls["n"] == 1:
            raise wrapped
        return _verify_idea(), None

    thread: list[dict] = []
    crit = v4.IdeaCritiqueV4(market_fit=0.6, novelty=0.6, clarity=0.6, on_anchor_pain=True,
                             binding_constraint="novelty", directive="sharpen it",
                             meets_bar=False, rationale="grounded")
    v4._improve(crit, thread, _verify_idea(), invoke=invoke, model=None, effort="none")
    assert calls["n"] == 2, "the retry branch never ran -- the contract-error gate rejected it"
    repair = [m["content"] for m in thread
              if m["role"] == "user" and "violated the BaseSolutionIdea schema" in m["content"]]
    assert len(repair) == 1, "expected exactly one repair turn"
    return repair[0]


@pytest.mark.parametrize(
    "partial",
    [
        {},
        {"solution_name": "Ownership Change Watch"},
        {"solution_name": "Ownership Change Watch", "description": "d", "value_proposition": "v"},
    ],
    ids=["empty-object", "name-only", "three-fields-present"],
)
def test_repair_prompt_names_every_missing_field(partial):
    """Per-field, not token-presence: a substring check on the error passes even truncated,
    because the first few field names always survive any cut."""
    exc = _validation_error(**partial)
    prompt = _repair_prompt(exc)
    expected = _missing_fields(exc)
    assert expected, "fixture produced no field-level errors"
    hidden = [f for f in expected if f not in prompt]
    assert hidden == [], (
        f"{len(hidden)} of {len(expected)} missing fields never reach the repair turn: "
        f"{hidden} -- the model cannot fix what it is not shown"
    )


def test_repair_prompt_carries_the_whole_validation_error(monkeypatch):
    exc = _validation_error()
    prompt = _repair_prompt(exc)
    assert len(str(exc)) < PROMPT_FIELD_MAX
    assert str(exc) in prompt
    assert "[truncated]" not in prompt


# --------------------------------------------------------------------------------------
# Site 6: segment_payability -- the WRITE cap on the payability rationale
# --------------------------------------------------------------------------------------
# `item.rationale = (...).strip()[:200]` stored the CUT value: it is copied onto
# `AudienceSegment.payability_rationale` (unified_solution_crew / research_flow), survives
# model_dump into the checkpoint, and is read BACK by `_payability_map_from_segments` on a
# resume. Measured over the checkpoint corpus: n=221 distinct values, median 186, max 200,
# and 71 of them (32.1%) sat EXACTLY at 200 -- provably severed, mid-word, unmarked
# ("...indicating both wallet capacity and willingness to p"). No renderer imposes a slot
# width on it: the only frontend consumer normalizes it (design-preview/job/normalize.ts
# -> `payabilityRationale`) and nothing clamps or renders it, so the producer had no width
# to honour. The prompt asks for one sentence; the model field documents a user-facing
# reason. Bound is the runaway backstop only, and it announces itself.

LONG_PAYABILITY_RATIONALE = (
    "These shop owners run established businesses that already carry a line item for "
    "specialized software and repeatedly reference paying about a hundred dollars a month "
    "for scheduling and invoicing tools, which shows both the wallet capacity and the "
    "existing habit of buying rather than merely a loud complaint about the current process."
)


def _segment(name: str = "Independent shop owners", **overrides):
    from nicheiq.models.research_state import AudienceSegment

    base = dict(
        segment_name=name,
        size_estimate="Medium",
        pain_point_alignment=["parts arrive late"],
        motivation_drivers=["fewer callbacks"],
        expertise_level="Intermediate",
        budget_sensitivity="Medium",
        discovery_channels=["trade forums"],
    )
    base.update(overrides)
    return AudienceSegment(**base)


def _score_payability(monkeypatch, rationale: str, segment=None):
    """Drive the real batched scorer with a REAL _PayabilityBatch reply.

    `score_segment_payability` is fail-soft (any exception -> ({}, None)), so the caller must
    assert the map is non-empty; a silently swallowed double error would otherwise read as a
    pass. Returns the stored SegmentPayability.
    """
    from nicheiq.utils import segment_payability as sp

    segment = segment or _segment()
    reply = sp._PayabilityBatch(
        segments=[sp.SegmentPayability(
            segment_name=segment.segment_name, payability_score=0.7,
            payability_class="smb-budget", rationale=rationale)]
    )
    monkeypatch.setattr(
        llm_service_mod.LLMService, "invoke_structured",
        staticmethod(lambda *a, **k: (reply, None)),
    )
    out, _usage = sp.score_segment_payability([segment], [], [], "auto repair shops")
    assert out, "scorer failed soft -- the double never produced a scored segment"
    return next(iter(out.values()))


def test_payability_rationale_is_stored_whole(monkeypatch):
    stored = _score_payability(monkeypatch, LONG_PAYABILITY_RATIONALE)
    _assert_intact(stored.rationale, LONG_PAYABILITY_RATIONALE, "payability rationale", old_cap=200)


def test_payability_rationale_survives_onto_the_segment_and_a_checkpoint_roundtrip(monkeypatch):
    """The write is the damage: assert the whole sentence reaches the persisted model."""
    from nicheiq.models.research_state import AudienceSegment

    segment = _segment()
    stored = _score_payability(monkeypatch, LONG_PAYABILITY_RATIONALE, segment=segment)
    segment.payability_rationale = stored.rationale  # what the two callers do verbatim
    revived = AudienceSegment.model_validate(segment.model_dump())
    _assert_intact(revived.payability_rationale, LONG_PAYABILITY_RATIONALE,
                   "payability rationale (revived)", old_cap=200)


def test_payability_runaway_rationale_is_marked_not_silently_cut(monkeypatch):
    stored = _score_payability(monkeypatch, "z" * (PROMPT_FIELD_MAX + 500))
    assert stored.rationale.endswith("[truncated]")


def test_payability_missing_rationale_stays_an_empty_string(monkeypatch):
    stored = _score_payability(monkeypatch, "")
    assert stored.rationale == ""


# --------------------------------------------------------------------------------------
# Site 7: idea_improvement_loop_v4 -- the allowlist-verified provenance marker
# --------------------------------------------------------------------------------------
# `f"Known public data source: {names} (allowlist-verified)"[:160]` bounded the composed
# string INCLUDING its own suffix, so the cut ate the marker the line exists to attach:
# prefix 26 + suffix 21 leaves 113 chars for `names`. `retrieve_known_sources` joins up to
# 6 canonical names PER claimed part and `llm_confirm_known_route` joins the per-part
# strings, so ordinary multi-source ideas clear 113 easily. A token-presence check would
# pass on the broken version (the prefix survives ANY cut) -- the property that matters is
# that the note still ENDS with the marker.

MULTI_REGISTRY_SOURCES = [
    "npm Registry, PyPI, RubyGems, crates.io, Packagist, NuGet",
    "SAM.gov, USAspending, Bureau of Labor Statistics, Census Bureau",
    "GitHub API",
]


class _Confirmed(BaseModel):
    confirmed: bool = True
    note: str = "all match"


def _run_allowlist_branch(monkeypatch, data_sources):
    """Real registry retrieval + real name joining; only the confirm LLM is doubled.

    `names` is therefore whatever the shipped allowlist actually produces, not a fixture
    string chosen to be long.
    """
    monkeypatch.setattr(
        llm_service_mod.LLMService, "invoke_structured",
        staticmethod(lambda *a, **k: (_Confirmed(), None)),
    )
    idea = _verify_idea(data_sources=data_sources, data_access_model="unverified")
    verdict = verify_data_routes(idea, None, search=lambda q: "", invoke=None)
    assert verdict is not None, "the allowlist short-circuit never fired"
    return idea


def _confirmed_names(data_sources) -> str:
    """The `names` string the real allowlist produces -- computed from the registry, NOT read
    back out of the note under test (which may itself be truncated, making the fixture-length
    guard fire instead of the assertion that matters)."""
    matches = pds.retrieve_known_sources(data_sources)
    assert matches, "fixture is not recognized by the shipped allowlist"
    return ", ".join(dict.fromkeys(n for _, n in matches))


def test_allowlist_note_keeps_its_provenance_marker_for_many_sources(monkeypatch):
    names = _confirmed_names(MULTI_REGISTRY_SOURCES)
    assert len(names) > 113, (
        f"fixture too short to exercise the old cap: the allowlist joins {len(names)} chars of "
        "names, and the old [:160] only severed the marker past 113 (160 - 26 prefix - 21 suffix)"
    )
    idea = _run_allowlist_branch(monkeypatch, MULTI_REGISTRY_SOURCES)
    notes = idea.data_acquisition_notes
    assert notes.endswith("(allowlist-verified)"), (
        "the provenance marker was severed -- the stored note reads as unverified prose: "
        f"...{notes[-40:]!r}"
    )
    assert "[truncated]" not in notes


def test_allowlist_note_keeps_every_confirmed_source_name(monkeypatch):
    """Per-name, not substring: the leading names survive any cut, the trailing ones do not."""
    idea = _run_allowlist_branch(monkeypatch, MULTI_REGISTRY_SOURCES)
    confirmed = pds.retrieve_known_sources(MULTI_REGISTRY_SOURCES)
    expected = [n.strip()
                for joined in dict.fromkeys(n for _, n in confirmed)
                for n in joined.split(",")]
    assert len(expected) > 6, "fixture must match several sources"
    missing = [n for n in expected if n not in idea.data_acquisition_notes]
    assert missing == [], (
        f"{len(missing)} of {len(expected)} allowlist-confirmed sources never reach the "
        f"stored note: {missing}"
    )


def test_allowlist_note_short_case_is_unchanged(monkeypatch):
    idea = _run_allowlist_branch(monkeypatch, ["Common Crawl"])
    assert idea.data_acquisition_notes == (
        "Known public data source: Common Crawl (allowlist-verified)")
