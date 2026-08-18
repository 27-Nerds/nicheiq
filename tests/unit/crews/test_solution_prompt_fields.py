"""Model-authored fields reach the prompts that score them WHOLE.

The defect these guard: every field below was rendered into a scoring prompt through a
guessed constant char-slice (`[:200]`, `[:240]`, `[:600]`, or the `_g(attr, n=240)` default
argument). Measured over 5,350 artifact JSONs in this repo, those slices removed text from
96.0% of `technical_approach`, 91.6% of `why_it_works`, 88.5% of `value_proposition`,
88.5% of idea `description` and 98.0% of pain `description` values -- with no ellipsis, so
the receiving model could not tell "the mechanism does not cover this" from "the sentence
saying so was cut".

The assertions are PROPERTIES, not prose: the exact authored text must appear in the prompt,
and the only remaining bound is the runaway backstop, which announces itself.
"""

import re
from types import SimpleNamespace

import pytest

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.utils.content_security import PROMPT_FIELD_MAX

# Long, distinctive, word-boundary-free-of-collisions text per field. Each is far longer than
# the constant that used to cut it, so a regression re-introducing any of those constants
# fails on the exact-substring assertion.
LONG = {
    "technical_approach": (
        "MECH-START Nightly the worker pulls the county recorder bulk export over their "
        "documented FTP endpoint, normalises the grantor/grantee rows with a rapidfuzz "
        "blocking pass, and diffs each parcel against the prior snapshot; the diff, not the "
        "snapshot, is what gets indexed. Everything after this clause is the part the old "
        "two-hundred-character slice destroyed: the pipeline runs on a single small VM "
        "because the bulk export is only forty megabytes a night, there is no streaming "
        "requirement, no vector store, and no model training of any kind. The one genuinely "
        "hard part is the grantor-name normalisation, which is why the library choice "
        "matters and why naming rapidfuzz here is load-bearing for the build estimate. "
        "MECH-END"
    ),
    "why_it_works": (
        "WHY-START Title abstractors already pay for this diff by hand, once per closing, and "
        "the manual pass is where the errors come from. The clause the old two-hundred-and-"
        "forty-character default severed always came next, because the sentence structure is "
        "'it works because X, BUT the caveat is Y' -- and Y is the half a critic needs. "
        "WHY-END"
    ),
    "conventional_approach": (
        "CONV-START Everyone builds a searchable record archive and charges per lookup, which "
        "is what the incumbents already ship and why a me-too archive has no wedge here at "
        "all, no matter how good the search is. CONV-END"
    ),
    "innovation_angle": (
        "INNO-START The wedge is the diff rather than the archive: nobody sells the delta, "
        "and the delta is the only part of the record set that changes between closings, "
        "which is also the only part anyone re-reads. INNO-END"
    ),
    "value_proposition": (
        "VP-START Tells a title abstractor exactly which parcels changed overnight, so the "
        "morning review is a five-item list instead of a full re-read of the county roll. "
        "VP-END"
    ),
    "programmatic_seo_opportunity": (
        "SEO-START One indexable page per county per document type, roughly three thousand "
        "of them, each fed by the same nightly diff so the pages stay fresh without hand "
        "authoring; the corpus is enumerable from the recorder list itself. SEO-END"
    ),
    "content_generation_model": (
        "CGM-START Template plus data, no generative text: the page body is the diff table "
        "and a deterministic sentence, which is what keeps this from being a thin-content "
        "penalty magnet. CGM-END"
    ),
}

# Every value must exceed the LARGEST constant that ever cut any of these fields (800, at
# the blank-field repair prompt), so each assertion is load-bearing against every one of the
# old limits and not just the smallest.
_PAD = (" The sentences before the end marker exist so this value is longer than every "
        "constant that used to slice it, including the eight-hundred-character one. ")
# Pad is inserted BEFORE the trailing *-END sentinel, so the sentinel only survives a
# render that kept the whole value.
LONG = {k: v.rsplit(" ", 1)[0] + _PAD * 6 + " " + v.rsplit(" ", 1)[1] for k, v in LONG.items()}
assert all(len(v) > 800 for v in LONG.values()), {k: len(v) for k, v in LONG.items()}

# (head, tail) sentinels: the tail is the LAST token of the padded value, so a prompt that
# contains the head but not the tail is proof of a silent cut.
MARKERS = {k: (v.split()[0], v.split()[-1]) for k, v in LONG.items()}


def _idea(name="ParcelDiff", **kw):
    base = dict(
        solution_name=name,
        description="D" * 900,
        pain_points_addressed=["Manual parcel re-reads"],
        core_features=["nightly diff", "per-county page"],
        target_personas=["title abstractor"],
        source_pain="Manual parcel re-reads",
        market_fit_score=0.7, technical_feasibility_score=0.7, novelty_score=0.5,
        seo_scalability_score=0.6, obviousness_score=0.4,
        **LONG,
    )
    base.update(kw)
    return BaseSolutionIdea(**base)


def _capturing_self(captured, pain_points=None):
    """Minimal 'self' for the two batch scorers (mirrors tests/unit/test_score_calibration.py)."""
    fake = SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: an existing archive product",
        pain_point_analysis=SimpleNamespace(pain_points=pain_points or []),
        _record_divergent_usage=lambda u: None,
        cost_tracker=None,
    )
    for meth in ("_calibration_static_prompt", "_calibrate_batch",
                 "_angle_static_prompt", "_classify_batch"):
        setattr(fake, meth, getattr(usc.UnifiedSolutionCrew, meth).__get__(fake))
    return fake


def _run_calibration(monkeypatch, idea):
    captured = {}

    def _capture(**kw):
        captured["prompt"] = kw["prompt"]
        return usc._ScoreCalibrations(calibrations=[]), SimpleNamespace()

    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_capture))
    _capturing_self(captured)._calibrate_batch(batch=[idea])
    return captured["prompt"]


def _run_angle(monkeypatch, idea):
    captured = {}

    def _capture(**kw):
        captured["prompt"] = kw["prompt"]
        return SimpleNamespace(verdicts=[]), SimpleNamespace()

    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_capture))
    _capturing_self(captured)._classify_batch(batch=[idea])
    return captured["prompt"]


# The critic that REPLACES market_fit / technical_feasibility / novelty / seo_scalability /
# obviousness / solo_dev must see every field it scores on in full.
CALIBRATION_FIELDS = sorted(LONG)

# The angle classifier decides WHERE an idea's edge lives; it renders a subset.
ANGLE_FIELDS = ["technical_approach", "value_proposition", "conventional_approach",
                "innovation_angle", "programmatic_seo_opportunity"]


class TestCalibrationPrompt:
    @pytest.mark.parametrize("field", CALIBRATION_FIELDS)
    def test_field_reaches_the_prompt_whole(self, monkeypatch, field):
        prompt = _run_calibration(monkeypatch, _idea())
        assert LONG[field] in prompt, (
            f"{field} was truncated before the calibration critic that re-scores this idea"
        )

    def test_no_field_is_cut_without_a_marker(self, monkeypatch):
        prompt = _run_calibration(monkeypatch, _idea())
        for field, (head, tail) in MARKERS.items():
            assert head in prompt and tail in prompt, f"{field} lost its tail"
        assert "…[truncated]" not in prompt  # nothing here is anywhere near the backstop

    def test_addressed_pain_titles_are_not_cut(self, monkeypatch):
        titles = [f"P{i} " + "long pain title text " * 6 for i in range(4)]
        prompt = _run_calibration(monkeypatch, _idea(pain_points_addressed=titles))
        for t in titles:
            assert t in prompt


class TestAnglePrompt:
    @pytest.mark.parametrize("field", ANGLE_FIELDS)
    def test_field_reaches_the_prompt_whole(self, monkeypatch, field):
        prompt = _run_angle(monkeypatch, _idea())
        assert LONG[field] in prompt, (
            f"{field} was truncated before the winning-angle classifier"
        )

    def test_source_pain_is_not_cut(self, monkeypatch):
        sp = "Manual parcel re-reads " + "with every single closing document " * 8
        prompt = _run_angle(monkeypatch, _idea(source_pain=sp))
        assert sp in prompt


class TestRunawayBackstop:
    """The only remaining bound announces itself instead of cutting silently."""

    def test_pathological_value_is_marked_not_silently_cut(self, monkeypatch):
        runaway = "R" * (PROMPT_FIELD_MAX + 500)
        prompt = _run_calibration(monkeypatch, _idea(content_generation_model=runaway))
        assert runaway not in prompt
        assert "…[truncated]" in prompt
        assert "R" * PROMPT_FIELD_MAX in prompt


class TestKnownRouteConfirm:
    """`_finalize_idea_pool` -> `llm_confirm_known_route(context=...)`.

    That call decides whether a claimed data route is REAL; a rejection lands as a worse
    `data_access_model` and a docked data_feasibility. 71.3% of technical_approach values
    exceed the old [:400], and the sibling caller in idea_improvement_loop_v4 passes it uncut,
    so the cut here was also a cross-caller inconsistency.
    """

    # A real multi-registry confirmation returns every canonical hit (the helper's own
    # docstring example is "npm Registry, PyPI, RubyGems, crates.io"), so the composed note
    # routinely runs past the old 160-char bound and loses its trailing marker.
    NAMES = ("npm Registry, PyPI, RubyGems, crates.io, Packagist, NuGet Gallery, "
             "Maven Central, Go Module Index, Hex.pm, CPAN, CocoaPods")

    def _run(self, monkeypatch, idea):
        import nicheiq.utils.public_data_sources as pds

        seen = {}
        monkeypatch.setattr(pds, "retrieve_known_sources",
                            lambda parts: [("SEC EDGAR", "SEC EDGAR")])

        def _confirm(matches, *, context=""):
            seen["context"] = context
            return self.NAMES

        monkeypatch.setattr(pds, "llm_confirm_known_route", _confirm)
        fake = SimpleNamespace(
            _canonicalize_project_type=lambda i: None,
            _canonicalize_delivery_format=lambda i: None,
        )
        usc.UnifiedSolutionCrew._finalize_idea_pool.__get__(fake)([idea])
        return seen

    def test_technical_approach_reaches_the_confirm_call_whole(self, monkeypatch):
        idea = _idea(data_access_model="restricted", data_sources=["SEC EDGAR"])
        seen = self._run(monkeypatch, idea)
        assert LONG["technical_approach"] in seen["context"]

    def test_allowlist_note_keeps_its_provenance_marker(self, monkeypatch):
        """The stored note used to be cut as a WHOLE composed string, so a long source list
        severed the '(allowlist-verified)' suffix the note exists to carry."""
        idea = _idea(data_access_model="restricted", data_sources=["SEC EDGAR"])
        self._run(monkeypatch, idea)
        assert self.NAMES in idea.data_acquisition_notes
        assert idea.data_acquisition_notes.endswith("(allowlist-verified)")


class TestGroundingBlocks:
    def test_anchor_pain_description_is_whole(self):
        desc = "Abstractors re-read the full county roll every morning. " * 12
        pain = SimpleNamespace(description=desc)
        block = usc.UnifiedSolutionCrew._format_anchor_pains_block(
            ["Manual parcel re-reads"], {"Manual parcel re-reads": pain})
        assert desc in block

    def test_representative_quote_is_whole(self):
        quote = "I spend the first ninety minutes of every day re-reading rows " * 5
        pain = SimpleNamespace(
            title="Manual parcel re-reads", description="d", severity_score=0.8,
            commercial_intent=0.7, opportunity_level=None, mention_count=12,
            affected_segments=["abstractors"], representative_quotes=[quote],
        )
        block = usc._format_one_pain(pain)
        assert " ".join(quote.split()) in block


# ---------------------------------------------------------------------------
# Round 2: the classifier's OUTPUT side.
#
# `_classify_batch` renders the idea into the angle prompt (guarded above) and then WRITES the
# verdict back onto the idea. Those write-backs were cut at 600/300/300 with no marker. A write
# truncation is worse than a read one: the severed value is STORED, so every downstream reader
# inherits it and no read-side fix can recover it. Measured over the checkpoint corpus, values
# sitting exactly at the bound -- i.e. provably severed -- were differentiation_locus 242/1021
# (23.7%), angle_rationale 133/1335 (10.0%), novelty_rationale 20/1342 (1.5%).
#
# Neither field has a length contract (the prompt asks for "1-3 sentences" / "1 sentence"), and
# both reach a reader that must tell a finished thought from a severed one: differentiation_locus
# is rendered into `{angle_brief}` for the Stage-2 SEO crew, angle_rationale is printed raw to the
# buyer. So the only bound is the runaway backstop, which announces itself.
# ---------------------------------------------------------------------------

# Digit-free (humanize_score_mentions rewrites bare 0-1 decimals) and word-boundary-marked at
# both ends, so a cut at ANY of the old constants loses the *-END sentinel.
def _long_verdict_text(head: str, tail: str, n: int) -> str:
    body = ("the edge lives in the nightly recorder diff rather than the archive itself, which "
            "is the half of the sentence every one of the old constants removed, ") * n
    return f"{head} {body}{tail}"


LOCUS = _long_verdict_text("LOCUS-START", "LOCUS-END", 5)        # > 300 (old bound), < backstop
ANGLE_RAT = _long_verdict_text("ANGLERAT-START", "ANGLERAT-END", 8)   # > 600 (old bound)
NOVELTY_RAT = _long_verdict_text("NOVRAT-START", "NOVRAT-END", 5)     # > 300 (old bound)
assert len(LOCUS) > 300 and len(NOVELTY_RAT) > 300 and len(ANGLE_RAT) > 600
assert all(len(v) < PROMPT_FIELD_MAX for v in (LOCUS, ANGLE_RAT, NOVELTY_RAT))


def _apply_verdict(monkeypatch, idea, **verdict_kw):
    """Drive the real `_classify_batch` write-back with a real `_AngleVerdicts` payload."""
    kw = dict(name=idea.solution_name, winning_angle="distribution_seo",
              differentiation_locus=LOCUS, angle_rationale=ANGLE_RAT,
              novelty_rationale=NOVELTY_RAT)
    kw.update(verdict_kw)
    verdicts = usc._AngleVerdicts(verdicts=[usc._AngleVerdict(**kw)])

    def _capture(**_):
        return verdicts, SimpleNamespace()

    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_capture))
    applied, _ = _capturing_self({})._classify_batch(batch=[idea])
    assert applied == 1, "verdict was not applied -- the test proves nothing"
    return idea


class TestAngleVerdictWriteBack:
    def test_differentiation_locus_is_stored_whole(self, monkeypatch):
        idea = _apply_verdict(monkeypatch, _idea())
        assert idea.differentiation_locus == LOCUS

    def test_angle_rationale_is_stored_whole(self, monkeypatch):
        idea = _apply_verdict(monkeypatch, _idea())
        assert idea.angle_rationale == ANGLE_RAT

    def test_novelty_rationale_is_stored_whole(self, monkeypatch):
        idea = _apply_verdict(monkeypatch, _idea())
        assert idea.novelty_rationale == NOVELTY_RAT

    def test_locus_reads_whole_where_the_seo_crew_consumes_it(self, monkeypatch):
        """The damage showed up one hop downstream: `build_angle_brief` renders the stored locus
        into the `{angle_brief}` interpolation that seo_strategy_tasks.yaml feeds to the Stage-2
        crew, and the TEMPLATE supplies the full stop -- so a severed clause reads as a finished
        thought to the crew told to 'investigate where the edge lives for THIS angle'."""
        from nicheiq.utils.angle_brief import build_angle_brief

        idea = _apply_verdict(monkeypatch, _idea())
        brief = build_angle_brief(idea)["angle_brief"]
        assert LOCUS in brief
        assert brief.split("Its claimed edge: ")[1].startswith("LOCUS-START")
        assert "LOCUS-END." in brief  # the sentinel, not a mid-word stub, meets the template's stop

    def test_score_humanization_still_runs(self, monkeypatch):
        """The write-back's OTHER job (a quoted decimal goes stale when caps move the score)
        must survive the truncation change."""
        idea = _apply_verdict(monkeypatch, _idea(),
                              angle_rationale="Fit is 0.85 for this idea.")
        assert "0.85" not in idea.angle_rationale

    def test_runaway_verdict_field_is_marked_not_silently_cut(self, monkeypatch):
        runaway = "RUNAWAY " * (PROMPT_FIELD_MAX // 4)
        idea = _apply_verdict(monkeypatch, _idea(), differentiation_locus=runaway)
        assert len(idea.differentiation_locus) < len(runaway)
        assert idea.differentiation_locus.endswith("…[truncated]")


# ---------------------------------------------------------------------------
# `why_it_works_short` -- the one bound that is a REAL slot contract.
#
# Unlike the three above, 120 is stated by the field's own generation prompt
# (unified_solution_tasks.yaml: "1 sentence, max 120 chars (card summary...)") and by the
# blank-repair directive, and the value renders in a card. So the bound STAYS. What was wrong is
# that the SAME field had two different cuts: `_derive_why_short` cut at 117 and appended "…",
# while `_repair_blank_idea_fields` applied a second, silent, mid-word `[:120]` that also re-cut
# what the first had already marked. 5 of the 11 distinct exactly-120 values in the checkpoint
# corpus end mid-word. `_derive_why_short` now owns both paths with one marked, word-boundary cut.
# ---------------------------------------------------------------------------

_LONG_WHY = ("Abstractors already pay for this overnight parcel diff by hand once per closing "
             "and the manual pass is exactly where the recording errors come from.")
assert len(_LONG_WHY) > 120


def _derive(idea):
    usc.UnifiedSolutionCrew._derive_why_short(idea)
    return idea.why_it_works_short


class TestWhyItWorksShortSlot:
    def test_derived_value_fits_the_slot_and_is_marked(self):
        out = _derive(_idea(why_it_works=_LONG_WHY, why_it_works_short=None))
        assert len(out) <= 120
        assert out.endswith("…")

    def test_over_long_stored_value_is_clamped_not_left_over_slot(self):
        out = _derive(_idea(why_it_works_short=_LONG_WHY))
        assert len(out) <= 120
        assert out.endswith("…")

    def test_the_cut_lands_on_a_word_boundary(self):
        """A mid-word cut hands the card reader a garbled token; the marker alone is not enough."""
        for idea in (_idea(why_it_works_short=_LONG_WHY),
                     _idea(why_it_works=_LONG_WHY, why_it_works_short=None)):
            out = _derive(idea)
            assert _LONG_WHY.startswith(out[:-1])          # a prefix of the authored text
            assert out[:-1] + " " in _LONG_WHY + " "       # ...ending at a word boundary

    def test_a_value_inside_the_slot_is_untouched(self):
        fits = "Abstractors already pay for this diff by hand, once per closing."
        assert _derive(_idea(why_it_works_short=fits)) == fits

    def test_clamping_is_idempotent(self):
        """The old second cut re-sliced an already-marked value, dropping the marker's last chars."""
        idea = _idea(why_it_works_short=_LONG_WHY)
        once = _derive(idea)
        assert _derive(idea) == once

    def test_repair_path_clamps_an_llm_filled_short_form_with_a_marker(self, monkeypatch):
        """The site that used to hold the silent `[:120]`: the blank-field repair fills
        why_it_works_short from the LLM, which does not honour the char budget."""
        idea = _idea(why_it_works_short=None, why_it_works=None)
        llm_reply = _idea(why_it_works_short=_LONG_WHY)

        def _capture(**_):
            return llm_reply, SimpleNamespace()

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_capture))
        fake = SimpleNamespace(
            niche_context=None, _monetization_directive="",
            _record_divergent_usage=lambda u: None,
            _derive_why_short=usc.UnifiedSolutionCrew._derive_why_short,  # staticmethod
        )
        for meth in ("_pain_wtp_label", "_repair_blank_idea_fields"):
            setattr(fake, meth, getattr(usc.UnifiedSolutionCrew, meth).__get__(fake))
        fake._repair_blank_idea_fields(idea)

        assert idea.why_it_works_short, "repair never ran -- the fail-soft except swallowed it"
        assert len(idea.why_it_works_short) <= 120
        assert idea.why_it_works_short.endswith("…")
        assert _LONG_WHY.startswith(idea.why_it_works_short[:-1])


# ---------------------------------------------------------------------------
# Round 3: the two PARITY judges -- the ones whose verdict is a HARD CAP.
#
# Everything above guards a prompt that feeds a SCORE. These two feed `_parity_cap`, a ceiling
# on market_fit (shipped 0.45 / substitute 0.5 / partial 0.55 / bundled_free 0.4) that no later
# pass can lift. Both judges are asked a question ABOUT THE MECHANISM:
#
#   * `_probe_mechanism_parity`  -- "whether an incumbent already SHIPS the idea's core mechanism"
#   * `_probe_adjacent_markets`  -- "an idea whose value prop OR MECHANISM differs is NOT covered"
#
# and until 2026-08-18 both were handed the value proposition ONLY. A mechanism question answered
# from positioning alone has no way to separate two ideas that promise the same outcome by
# different means, so the "not covered" escape hatch was unreachable. Measured: 40.4% of 643
# distinct stamped ideas carry a cap, and 99.2% of those hold a `technical_approach` the judge
# never saw.
#
# These tests drive the REAL methods end to end (fake search tool, no network) and assert on the
# prompt the judge actually received. Both probes are fail-soft -- a bad stub returns silently --
# so every helper asserts the judge call HAPPENED and that the idea's own name and value prop are
# on the page before asserting the mechanism is too. A stub that never reaches the judge cannot
# produce a vacuous green.
# ---------------------------------------------------------------------------

_SEARCH_SNIPPET = ("ArchiveCo - county record search for title professionals. Pricing from $99/mo. "
                   "Full-text archive of recorded documents, no change tracking.")


def _mech_idea(name, **kw):
    """A real BaseSolutionIdea carrying the LONG mechanism, tagged so the adjacent probe's
    deterministic family detection has a key to group on."""
    return _idea(name, mechanism_tag="record diff", data_source_tag="county recorder", **kw)


def _parity_probe_self(captured):
    """Minimal 'self' for `_probe_mechanism_parity` up to and including its judge call.

    Only the attributes on the path to that call are stubbed; the search tool returns a fixed
    string so nothing touches the network."""
    fake = SimpleNamespace(
        search_tool=SimpleNamespace(run=lambda search_query="": _SEARCH_SNIPPET),
        niche_context=SimpleNamespace(
            niche_description="Independent title abstractors working US county records"),
        _probe_incumbents=lambda: "",
        _incumbent_rows=[{"name": "ArchiveCo",
                          "focus": "county recorder archive search for title abstractors"}],
        _capability_phrases=lambda ideas: {},
        _mechanism_keywords=usc.UnifiedSolutionCrew._mechanism_keywords,  # staticmethod
        _record_search_arm=lambda *a, **k: None,
        _record_search_arm_finding=lambda *a, **k: None,
        _parity_discovery_spent=0,
        cost_tracker=None,
    )
    return fake


def _run_parity_probe(monkeypatch, ideas):
    """Drive the real `_probe_mechanism_parity` and return the prompt its judge received."""
    captured = {}

    def _capture(**kw):
        captured["prompt"] = kw["prompt"]
        # findings=[] -> the method returns right after the judge call, so nothing downstream
        # (recalibration, adjacent/toolbelt probes) needs stubbing.
        return kw["output_model"](findings=[]), None

    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_capture))
    usc.UnifiedSolutionCrew._probe_mechanism_parity.__get__(_parity_probe_self(captured))(ideas)

    # Anti-vacuous-green: the probe is fail-soft (`except Exception` -> logger.warning), so a
    # mis-wired stub returns silently. Prove the judge ran and saw these ideas at all.
    prompt = captured.get("prompt")
    assert prompt, ("the parity judge was never called -- the fail-soft except swallowed a stub "
                    "error, so this test proves nothing")
    assert "already SHIPS the idea's core mechanism" in prompt, "not the parity judge's prompt"
    for i in ideas:
        assert i.solution_name in prompt, f"{i.solution_name} never reached the judge"
        assert i.value_proposition in prompt, f"{i.solution_name}'s value prop never reached it"
    return prompt


def _adjacent_probe_self():
    """Minimal 'self' for `_probe_adjacent_markets` up to and including its judge call."""
    return SimpleNamespace(
        search_tool=SimpleNamespace(batch_run=lambda qs: {q: _SEARCH_SNIPPET for q in qs}),
        _ma_search_batch=lambda qs, **k: {q: _SEARCH_SNIPPET for q in qs},
        niche_context=SimpleNamespace(
            niche_description="Independent title abstractors working US county records"),
        _mechanism_keywords=usc.UnifiedSolutionCrew._mechanism_keywords,
        _record_search_arm=lambda *a, **k: None,
        _record_search_arm_finding=lambda *a, **k: None,
        _ADJACENT_FAMILY_CAP=usc.UnifiedSolutionCrew._ADJACENT_FAMILY_CAP,
        cost_tracker=None,
    )


def _run_adjacent_probe(monkeypatch, ideas):
    """Drive the real `_probe_adjacent_markets` and return the prompt its FAMILY judge received.

    The method makes two structured calls: a category-reformulation call first, then the judge.
    The reformulation reply is built from the family keys the method itself printed, so the
    judge's `snippets_by_key` is non-empty and the judge actually fires."""
    captured = {}

    def _capture(**kw):
        model = kw["output_model"]
        if model.__name__.endswith("Markets"):
            keys = re.findall(r"### family_key: (.+)", kw["prompt"])
            assert keys, "the reformulation call saw no families -- stub is mis-wired"
            captured["reformulation_prompt"] = kw["prompt"]
            return model(markets=[{"family_key": k.strip(),
                                   "categories": ["records intelligence"],
                                   "budget_line": "title data spend"} for k in keys]), None
        captured["prompt"] = kw["prompt"]
        return model(findings=[]), None

    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_capture))
    lines, covered = usc.UnifiedSolutionCrew._probe_adjacent_markets.__get__(
        _adjacent_probe_self())(ideas)

    prompt = captured.get("prompt")
    assert prompt, ("the adjacent-market family judge was never called -- the fail-soft except "
                    "swallowed a stub error, so this test proves nothing")
    assert "value prop or mechanism differs is NOT covered" in prompt, "not the family judge"
    for i in ideas:
        assert i.solution_name in prompt, f"{i.solution_name} never reached the judge"
        assert i.value_proposition in prompt, f"{i.solution_name}'s value prop never reached it"
    return prompt


class TestMechanismParityJudgePrompt:
    """`_probe_mechanism_parity` -> the judge whose `parity` verdict caps market_fit."""

    def test_technical_approach_reaches_the_judge_whole(self, monkeypatch):
        prompt = _run_parity_probe(monkeypatch, [_mech_idea("ParcelDiff")])
        assert LONG["technical_approach"] in prompt, (
            "the mechanism-parity judge is asked whether an incumbent ships the idea's MECHANISM "
            "but the mechanism is not on the page (or was cut)"
        )

    def test_the_mechanism_keeps_its_tail(self, monkeypatch):
        head, tail = MARKERS["technical_approach"]
        prompt = _run_parity_probe(monkeypatch, [_mech_idea("ParcelDiff")])
        assert head in prompt and tail in prompt, "the mechanism was silently cut"
        assert "…[truncated]" not in prompt

    def test_same_promise_different_mechanism_is_distinguishable(self, monkeypatch):
        """The defect in one assertion: two ideas making the SAME promise by different means
        must not look identical to a judge asked a mechanism question."""
        shared_vp = LONG["value_proposition"]
        other_mech = ("OTHERMECH-START A browser extension that scrapes the recorder's own web "
                      "search UI on demand, per user, with no bulk export and no nightly job. "
                      "OTHERMECH-END")
        a = _mech_idea("ParcelDiff", value_proposition=shared_vp)
        b = _mech_idea("RollWatch", value_proposition=shared_vp,
                       technical_approach=other_mech)
        prompt = _run_parity_probe(monkeypatch, [a, b])
        assert LONG["technical_approach"] in prompt
        assert other_mech in prompt
        # ...and the two ideas' rendered blocks are not byte-identical apart from the name.
        assert prompt.count("mechanism:") >= 2

    def test_a_missing_mechanism_is_labelled_not_blank(self, monkeypatch):
        """An idea with no technical_approach must read as 'n/a', not as an empty line the judge
        can mistake for a rendering artefact."""
        prompt = _run_parity_probe(monkeypatch, [_mech_idea("ParcelDiff", technical_approach=None)])
        assert "mechanism: n/a" in prompt

    def test_runaway_mechanism_is_marked_not_silently_cut(self, monkeypatch):
        runaway = "R" * (PROMPT_FIELD_MAX + 500)
        prompt = _run_parity_probe(monkeypatch, [_mech_idea("ParcelDiff",
                                                            technical_approach=runaway)])
        assert runaway not in prompt
        assert "R" * PROMPT_FIELD_MAX in prompt
        assert "…[truncated]" in prompt


class TestAdjacentMarketJudgePrompt:
    """`_probe_adjacent_markets` -> the family judge whose `covered_idea_names` back-fills
    `incumbent_parity` (and therefore the same market_fit cap)."""

    def test_member_technical_approach_reaches_the_judge_whole(self, monkeypatch):
        prompt = _run_adjacent_probe(monkeypatch, [_mech_idea("ParcelDiff")])
        assert LONG["technical_approach"] in prompt, (
            "the family judge is told an idea whose MECHANISM differs is not covered, but the "
            "member mechanisms are not on the page (or were cut)"
        )

    def test_member_mechanism_keeps_its_tail(self, monkeypatch):
        head, tail = MARKERS["technical_approach"]
        prompt = _run_adjacent_probe(monkeypatch, [_mech_idea("ParcelDiff")])
        assert head in prompt and tail in prompt, "the member mechanism was silently cut"

    def test_family_members_are_separable_by_mechanism(self, monkeypatch):
        """Two members of the SAME family (same mechanism/data tags, so they group together)
        promising the same thing differently: covering one must not implicitly cover the other,
        which the judge can only decide if it sees both mechanisms."""
        shared_vp = LONG["value_proposition"]
        other_mech = ("OTHERMECH-START A browser extension that scrapes the recorder's own web "
                      "search UI on demand, per user, with no bulk export. OTHERMECH-END")
        a = _mech_idea("ParcelDiff", value_proposition=shared_vp)
        b = _mech_idea("RollWatch", value_proposition=shared_vp, technical_approach=other_mech)
        prompt = _run_adjacent_probe(monkeypatch, [a, b])
        assert LONG["technical_approach"] in prompt
        assert other_mech in prompt
        assert prompt.count("      mechanism: ") >= 2

    def test_a_missing_member_mechanism_is_labelled_not_blank(self, monkeypatch):
        prompt = _run_adjacent_probe(monkeypatch,
                                     [_mech_idea("ParcelDiff", technical_approach=None)])
        assert "mechanism: n/a" in prompt
