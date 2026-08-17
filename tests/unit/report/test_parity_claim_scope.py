"""A5 R2/R3 — the product may not assert a fact it does not have.

R3, WHY THIS FILE GREW. R2 fixed two modules and hardcoded `[ivb, ips]` as the source-scan
set. The claim regrew on the very next run in a THIRD module — `report_generator`'s
zero-result marketing channel, live in `final_report_20260817_105342.json` — and R2's guard
could not see it for TWO independent reasons, only one of which the R3 brief named:

  * the SET was a two-element literal, so a third module was never scanned; and
  * the VOCABULARY did not cover the claim class. Measured before touching anything:
    `unscoped_absence_claims` returns [] for all three of the strings that shipped. So
    widening the enumeration alone would have caught nothing here.

R3 therefore (a) derives the module set by walking the report package plus the defining
module of every renderer this file drives, (b) widens the absence vocabulary to the
numeral zero and to `competing <any noun>`, (c) adds two claim classes the scope property
structurally cannot see — ATTRIBUTION (naming the search ACT licenses "found no existing
content"; only naming the INSTRUMENT does not) and POSITION (an inference like "first-mover
opportunity" carries no negative at all) — and (d) walks the channel objects themselves
over the zero-result state space, with the platform keys read out of their producer.

THE DEFECT. `incumbent_parity` is a RETRIEVAL RESULT. `_probe_mechanism_parity`
(`crews/unified_solution_crew.py`) builds its queries out of each idea's OWN vocabulary
(`f"{mechanism_keywords} software {niche_label}"`, plus `f'"{incumbent_name}" {kw}'`), so
the wording of the pitch decides the verdict. Re-derived over `output/checkpoints/`
(457 run dirs, 101 carrying parity-stamped ideas, 1228 ideas):

    591  ideas carry a "none" stamp
    533  of those 591 (90.2%) sit in a run that ALREADY holds a NAMED incumbent finding
         on a different idea
    468  of 812 multi-idea pains (57.6%) carry a none-vs-covered contradiction
     94  ideas carry a BLANK/ABSENT stamp — the probe runs over a top slice only

So the two things the system may say are "our queries returned nothing for this idea"
(a "none" stamp) and "we have no result for this idea" (a blank stamp). What it may NOT
say is "there is no competitor", and it may not turn the blank into the "none".

WHAT THIS FILE HOLDS. Two independent properties, neither of which pins the sites that
happened to be fixed:

  1. SCOPE (`unscoped_absence_claims`). Decomposes a rendered string into CLAUSES and
     asks, per clause, whether a negative existential over a competitor is accompanied
     IN THAT SAME CLAUSE by the retrieval act it is scoped to. A hedge word loose in the
     artifact does not scope a claim made in a different clause — that is the failure
     mode a token-presence assertion has, and `test_the_checker_rejects_a_hedge_that_does_not_scope_the_claim`
     is the control for it.

  2. STATE DISTINCTION. Absent evidence and searched-and-empty are different states and
     must render differently. This one needs no vocabulary at all.

  3. ATTRIBUTION and POSITION (R3, section 7). For copy the caller KNOWS was rendered from
     a zero retrieval count: the null must be attributed to the instrument that produced
     it, and no market position may be drawn from it.

All of them are applied to SETS that are ENUMERATED BY WALKING, never by listing:

  * every string leaf of `build_idea_validation_block`'s artifact, over a closed parity ×
    brief-parity × red-team state space driven through the real captured 056b2c68 run;
  * every `_idea_digest_line` rendering over the same parity state space;
  * every non-docstring, non-log string literal in every REPORT-COPY MODULE, where that set
    is derived (`_report_copy_modules`) rather than listed — the `nicheiq.report` package
    walked from disk, unioned with the defining module of every driven renderer;
  * every string field of every marketing channel `_identify_marketing_channels` produces
    for a zero-result platform, over the platform keys derived from the flow that writes
    `sources_searched`.
"""

from __future__ import annotations

import ast
import re
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import nicheiq.report as nicheiq_report
from nicheiq.report import idea_validation_block as ivb
from nicheiq.report import report_generator as rg
from nicheiq.utils import idea_portfolio_summary as ips

from .fixture_056b2c68 import load_fixture, state_from_fixture

# ── the claim decomposition ────────────────────────────────────────────────────────
#
# A competitor REFERENCE: the noun class the parity finding is about, plus the domain's
# competitor predicate ("nothing ... SHIPS the mechanism" is the same claim as "no
# shipper exists"). Deliberately narrow: "product" alone is not one (`MARKET_SIGNAL_PREFIX`
# says "a product like yours", which is the USER's product), and "competitive" is not one
# ("No competitive conclusion was established" is an explicit statement of unknown).
#
# R3 widened `competing\s+product\w*` to `competing\s+\w+`: the regrown instance
# (`report_generator._identify_marketing_channels`) said "0 competing posts found", and
# the noun the claim rides on is chosen by whoever writes the copy, not by this file.
#
# R3 also made `match`/`matches` NOUN-only. As a bare alternative it fired on the verb
# ("the landscape ... did not match this niche", report_generator.py:2504 — a string that
# already scopes its claim correctly), which is the class of false positive that gets a
# checker deleted. A following determiner/pronoun is the verb reading.
_COMPETITOR_REF = re.compile(
    r"\b(competitor|competitors|competing\s+\w+|equivalent|equivalents|"
    r"incumbent|incumbents|rival|rivals|vendor|vendors|shipper|shippers|"
    r"substitute|substitutes|"
    r"match(?:es)?(?!\s+(?:this|that|these|those|the|a|an|any|it|its|his|her|their|my|"
    r"your|our)\b)|"
    r"ships|shipping|ship)\b",
    re.I,
)

# A negative existential head. The bare digit is an alternative in its own right: the
# regrown instance counted the absence in numerals ("0 competing posts found"), and a
# word-list of negatives does not see a "0". Guarded on both sides so "0-based",
# "0.45" and "v0" are not negatives.
_ABSENCE = re.compile(
    r"(?:\b(no|none|nothing|nobody|no\s?one|zero|never|without|"
    r"not\s+any|did\s+not|does\s+not|do\s+not|didn't|doesn't|don't|"
    r"is\s+not|are\s+not|isn't|aren't|has\s+no|have\s+no|cannot|can't|could\s+not|"
    r"couldn't)\b"
    r"|(?<![\w.\-])0(?![\w.\-]))",
    re.I,
)

# The retrieval act the claim must be scoped to. AGENTED or INSTRUMENTED only: a bare
# past participle ("found", "listed") names no searcher and no search, which is exactly
# how "no incumbent match found" could be emitted for an idea nothing ever checked.
_RETRIEVAL_SCOPE = re.compile(
    r"("
    r"\bwe\s+(found|find|could\s+not\s+find|did\s+not\s+find|searched|looked)\b"
    r"|\bour\s+(search\w*|quer\w+|probe\w*|check\w*)\b"
    r"|\bsearch\w*\b|\bsearched\b|\bquer(y|ies|ied)\b"
    r"|\bsurfac\w+\b|\bturn(s|ed|ing)?\s+up\b"
    r"|\bprobe[sd]?\b|\bprobing\b"
    r"|\bproduce\w*\s+a\s+result\b|\brecord(s|ed|ing)?\b"
    r"|\bcheck(s|ed|ing)?\b|\bretriev\w+\b"
    r"|\bin\s+this\s+run\b|\bthis\s+run's\b"
    r")",
    re.I,
)

# Clause boundaries. Commas included on purpose: over-splitting can only make the check
# STRICTER (a scope stranded on the far side of a comma stops counting), never laxer.
_CLAUSE_SPLIT = re.compile(r"(?:[.!?;:]|—|–|\bbut\b|\bthough\b|\balthough\b|,)+")


def clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(text) if c and c.strip()]


def unscoped_absence_claims(text: str) -> list[str]:
    """Clauses that assert a competitor is ABSENT without naming the retrieval that is
    the only thing the system actually knows. Empty list == the string claims only what
    the system has."""
    if not isinstance(text, str) or not text.strip():
        return []
    bad = []
    for clause in clauses(text):
        if not _ABSENCE.search(clause):
            continue
        if not _COMPETITOR_REF.search(clause):
            continue
        if _RETRIEVAL_SCOPE.search(clause):
            continue
        bad.append(clause)
    return bad


# ── R3: the two claim classes the SCOPE property above cannot see ──────────────────
#
# MEASURED FIRST (this is the correction to the brief that sent this round). Run
# `unscoped_absence_claims` over the three strings the regrown instance shipped and it
# returns [] for all three. Widening the module enumeration ALONE would not have caught
# this site; the vocabulary had to widen too. Per string:
#
#   "0 competing posts found"      -> missed twice: "0" was not a negative, and
#                                    "competing posts" was not a competitor reference
#                                    (only "competing product" was). Both fixed above,
#                                    so the SCOPE property now catches this one.
#   "Searched Hacker News and      -> NOT an unscoped claim, and the brief's first
#    found no existing content        characterisation is therefore only half right: the
#    for this niche."                 clause names its own search. The defect is the
#                                    OBJECT — it reports the reach of one query set as
#                                    the content population of a platform. Naming the
#                                    ACT of searching licenses that slide; naming the
#                                    INSTRUMENT (what was asked, what matched, what the
#                                    gate kept) does not. -> ATTRIBUTION property.
#   "Potential first-mover         -> carries no negative at all, so no absence property
#    opportunity if audience          can reach it. It is an inference of market
#    overlaps."                       POSITION from a null retrieval. -> POSITION property.

# The retrieved population a channel recommendation is about. Deliberately NOT merged into
# `_COMPETITOR_REF`: measured over `src/nicheiq/**`, folding these nouns into the scope
# property fires on honest strings ("the discussions show no purchase intent",
# "No content categorization available for ICP"), and a checker with false positives is a
# checker somebody deletes. It is safe HERE because the caller has already established
# that the count is zero, so no guessing about whether the noun means the population.
_RETRIEVED_POPULATION = re.compile(
    r"\b(content|posts?|threads?|discussions?|conversations?|stories|story|"
    r"articles?|videos?|coverage|mentions?|results?)\b",
    re.I,
)

# The INSTRUMENT, as distinct from the ACT. `_RETRIEVAL_SCOPE` accepts "Searched X"; this
# does not. It wants the thing that produced the zero: the queries, the matching, the
# relevance gate, the run.
_INSTRUMENT = re.compile(
    r"("
    r"\bour\s+(quer\w+|search\w*|probe\w*|filter\w*|gate\w*|run)\b"
    r"|\bquer(y|ies|ied)\b|\bkeyword\w*\b"
    r"|\bmatch(ed|es|ing)?\b|\bsurfac\w+\b|\breturn(s|ed|ing)?\b"
    r"|\bpass(ed|es|ing)?\b|\bretriev\w+\b|\bcited\b"
    r"|\brelevance\s+gate\b|\bfilter\w*\b"
    r"|\bthis\s+run\b|\bthis\s+run's\b|\bin\s+this\s+run\b"
    r")",
    re.I,
)

# A claim about where the market stands. Every one of these is a statement about the
# world, so a null retrieval can support none of them.
_POSITION = re.compile(
    r"(first[-\s]?mover|untapped|uncontested|unserved|unclaimed|white\s?space|"
    r"green\s?field|blue\s?ocean|virgin\s+(?:market|territory)|wide\s+open|"
    r"content\s+gap|market\s+gap|gap\s+in\s+the\s+market|no\s+competition|"
    r"zero\s+competition|nobody\s+is\s+(?:doing|building|serving))",
    re.I,
)


def unattributed_null_claims(text: str) -> list[str]:
    """Clauses that report an absence of retrieved material without naming the instrument
    that produced the zero. For strings the caller KNOWS were rendered from a zero count.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    bad = []
    for clause in clauses(text):
        if not _ABSENCE.search(clause):
            continue
        if not (_RETRIEVED_POPULATION.search(clause) or _COMPETITOR_REF.search(clause)):
            continue
        if _INSTRUMENT.search(clause):
            continue
        bad.append(clause)
    return bad


def position_claims(text: str) -> list[str]:
    """Market-position assertions, anywhere in the string (not clause-local: a position
    claim is unsupportable from a null no matter which clause it sits in)."""
    if not isinstance(text, str):
        return []
    return [m.group(0) for m in _POSITION.finditer(text)]


def position_inferred_from_a_null(text: str) -> list[str]:
    """The SOURCE-scan form. A bare position term in a literal is not a defect —
    `report_generator` renders "Key market gaps identified: …" from an evidence-backed
    competitor landscape, and flagging that would be a false positive for this claim
    class. What may never appear is a single literal that reports a null AND draws a
    position from it. That pairing is the regrown string's exact shape."""
    if not isinstance(text, str) or not _ABSENCE.search(text):
        return []
    return position_claims(text)


# ── (1) the checker itself is under test ───────────────────────────────────────────

def test_the_checker_catches_the_bare_claim():
    """The three strings this round removed, each caught for its own reason."""
    # the chip: a fact about the market, from a fact about our queries
    assert unscoped_absence_claims("No direct equivalent")
    # the manufactured negative: emitted when NOTHING was checked. "found" is a bare
    # participle — it names no searcher, so it does not scope anything.
    assert unscoped_absence_claims("no incumbent match found")
    # the refinement headline: "we evaluated" scopes the VERSION, not the search
    assert unscoped_absence_claims(
        "Your original mechanism already has tools shipping in it; the sharpened version "
        "we evaluated has no direct shipper.")


def test_the_checker_rejects_a_hedge_that_does_not_scope_the_claim():
    """THE CONTROL FOR THIS WHOLE FILE.

    A token-presence assertion ("does the rendered string contain a hedge word?") passes
    every string below while the banned claim is still being made, because the hedge sits
    in a different clause from the claim. Clause-local scoping is the whole point.
    """
    naive_passes = [
        # hedge in the NEXT sentence
        "No direct equivalent. Our searches ran on the idea's own wording.",
        # hedge in the PREVIOUS sentence
        "We searched the web for this. There is no competitor.",
        # hedge in a subordinate clause about something else entirely
        "No competing product exists, though we may revisit the search later.",
        # the brief's own shape: a hedge about a future action, not about the finding
        "The incumbent map is out of date, so we may restore it later; there is no rival.",
    ]
    for text in naive_passes:
        assert "search" in text.lower() or "we may" in text.lower(), text  # naive check passes
        assert unscoped_absence_claims(text), f"clause-local check must reject: {text}"


def test_the_checker_accepts_a_claim_scoped_in_its_own_clause():
    ok = [
        "Our searches did not surface a direct competitor.",
        "nothing we found ships your mechanism yet",
        "no direct equivalent of your exact product turned up",
        "the competitor probe recorded no result for this idea",
        "our searches surfaced no direct competitor",
    ]
    for text in ok:
        assert unscoped_absence_claims(text) == [], text


def test_the_checker_does_not_fire_on_non_competitor_absence():
    """Absence claims about OTHER things are not this file's business — a checker that
    fires on them would be turned off by the next person who hits a false positive."""
    for text in (
        "No thread in this run names your problem.",
        "No one has paid, pre-ordered, or given up anything for this idea.",
        "Nothing here is commitment evidence.",
        "Not enough linked evidence to grade the problem's breadth.",
        "No competitive conclusion was established.",
    ):
        assert unscoped_absence_claims(text) == [], text


# ── the parity state space (closed; every branch of both renderers) ────────────────

PARITY_STATES = {
    "absent": None,
    "empty": "",
    "whitespace": "   ",
    "none_found": "none found",
    "none_bare": "none",
    "shipped": "shipped by Acme: Acme ships lot-level roast tracking",
    "partial": "partial by Acme: Acme covers the settlement step",
    "substitute": "substitute (free spreadsheet templates): operators use sheets",
    "bundled": "bundled_free (Acme): included free with the Acme plan",
    "free_text": "unclear",
}

RED_TEAM_STATES = ("none", "weakened", "killed")
BRIEF_PARITY_STATES = ("miss", "hit")


def _strings(node):
    """Every string LEAF of the artifact — the enumeration is the walk, so a field added
    tomorrow is covered without being named here."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _strings(value)


_FIXTURE = load_fixture()


def _block(parity, *, red_team="none", brief="miss"):
    fx = deepcopy(_FIXTURE)
    for row in fx["ideas"]:
        if row.get("generation_operation_id") == "validate":
            row["incumbent_parity"] = parity
            if red_team == "none":
                row["red_team_verdict"] = None
                row["red_team_findings"] = None
            else:
                row["red_team_verdict"] = red_team
                row["red_team_findings"] = None
    state = state_from_fixture(fx)
    state.user_idea_brief_parity = (
        "partial by Acme: Acme covers the pitched mechanism" if brief == "hit" else None)
    return ivb.build_idea_validation_block(state, "validate_idea")


def _digest(parity):
    """A digest line for an idea whose ONLY interesting field is the parity stamp."""
    return ips._idea_digest_line(SimpleNamespace(
        solution_name="ProbeSubject",
        short_description="a thing",
        technical_approach="a mechanism",
        core_features=[],
        market_fit_score=0.5,
        market_fit_score_raw=0.5,
        seo_scalability_score=0.5,
        source_segment_payability=0.5,
        source_segment_payability_class="smb-budget",
        incumbent_parity=parity,
        adjacent_market_parity=None,
        estimated_development_time="4 weeks",
        tags=None,
        red_team_verdict=None,
        red_team_findings=None,
        red_team_caveats=[],
        red_team_revised=False,
        red_team_vocab_mismatch=False,
        target_market="b2b",
    ))


# ── (2) the driven SET: the idea_validation block ──────────────────────────────────

@pytest.mark.parametrize("parity_key", sorted(PARITY_STATES))
@pytest.mark.parametrize("red_team", RED_TEAM_STATES)
@pytest.mark.parametrize("brief", BRIEF_PARITY_STATES)
def test_no_rendered_string_in_the_block_asserts_absence_as_fact(parity_key, red_team, brief):
    block = _block(PARITY_STATES[parity_key], red_team=red_team, brief=brief)
    offenders = []
    for text in _strings(block):
        # The STORED stamp rides through the artifact untouched by design (>=7 consumers
        # parse its prefix). It is data, not a rendered sentence.
        if text == (PARITY_STATES[parity_key] or ""):
            continue
        offenders.extend((text, clause) for clause in unscoped_absence_claims(text))
    assert offenders == [], (
        f"parity={parity_key} red_team={red_team} brief={brief}: the block renders a "
        f"claim of absence the run cannot support:\n" + "\n".join(map(repr, offenders)))


# ── (3) the driven SET: the portfolio digest line ──────────────────────────────────

@pytest.mark.parametrize("parity_key", sorted(PARITY_STATES))
def test_no_digest_line_asserts_absence_as_fact(parity_key):
    parity = PARITY_STATES[parity_key]
    line = _digest(parity)
    offenders = [c for c in unscoped_absence_claims(line)
                 if c.strip().lower() != (parity or "").strip().lower()]
    assert offenders == [], f"parity={parity_key}: {offenders}"


# ── (4) the source SET: any literal, anywhere in EVERY report-copy module ──────────

_LOG_CALL = re.compile(r"^(logger|log|logging|_logger)$")


def _non_docstring_literals(path: Path) -> list[str]:
    """Every string literal that could become COPY: docstrings excluded (they are not
    rendered), and log/print arguments excluded too — R3 addition, on the same reasoning.
    Without it the scan reports `logger.warning("⚠️ No competitor features found - ...")`
    (report_generator.py:4803), which no reader ever sees; carrying known false positives
    is how a guard gets switched off."""
    tree = ast.parse(path.read_text())
    excluded = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                excluded.add(id(body[0].value))
        if isinstance(node, ast.Call):
            fn = node.func
            is_log = (
                (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                 and _LOG_CALL.match(fn.value.id))
                or (isinstance(fn, ast.Name) and fn.id == "print")
            )
            if is_log:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        excluded.add(id(sub))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in excluded]


# The renderers this file DRIVES. Read by `_report_copy_modules` to derive which source
# files the forward guard scans, so adding a driver above widens the scan by itself.
DRIVEN_RENDERERS = (
    ivb.build_idea_validation_block,
    ips._idea_digest_line,
    rg.ReportGenerator._identify_marketing_channels,
)


def _report_copy_modules() -> list[Path]:
    """THE SET — derived by walking, never listed.

    R3 exists because this was `[ivb, ips]`, a two-element literal, and the claim regrew
    in a THIRD module (`report/report_generator.py`) on the next run. A defect of the form
    "some member of a set violates a property" is only closed by enumerating the set.

    Two derivations, unioned:

      1. the whole `nicheiq.report` PACKAGE, by walking its directory — `report_generator`,
         `idea_validation_block`, everything under `report/utils/`, and any file added
         tomorrow, none of them named here;
      2. the defining module of every renderer in `DRIVEN_RENDERERS`, read off the function
         objects (`__module__`). This is what keeps `nicheiq.utils.idea_portfolio_summary`
         in scope: it renders report copy but does not live in the report package, so
         derivation (1) alone would have dropped the coverage R2 established.
    """
    package_dir = Path(nicheiq_report.__file__).resolve().parent
    paths = {p.resolve() for p in package_dir.rglob("*.py") if p.name != "__init__.py"}
    for fn in DRIVEN_RENDERERS:
        module = sys.modules[fn.__module__]
        paths.add(Path(module.__file__).resolve())
    return sorted(paths)


def claim_offenders_in_source(path: Path) -> list[tuple[str, str, str]]:
    """(property, literal, offending fragment) for one source file. Factored out of the
    test so `test_the_forward_guard_names_an_unlisted_module` can point it at a throwaway
    package and prove the enumeration is real."""
    out = []
    for literal in _non_docstring_literals(path):
        for clause in unscoped_absence_claims(literal):
            out.append(("scope", literal, clause))
        for term in position_inferred_from_a_null(literal):
            out.append(("position-from-null", literal, term))
    return out


def _module_ids(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


_COPY_MODULES = _report_copy_modules()


def test_the_derived_module_set_is_not_a_list():
    """Guards the derivation itself. If someone replaces the walk with a literal again,
    or the report package grows a copy module the walk misses, this notices."""
    names = set(_module_ids(_COPY_MODULES))
    # the three modules that have carried this claim class so far must all be in, and
    # NONE of them is named in the parametrize
    assert {"report_generator.py", "idea_validation_block.py",
            "idea_portfolio_summary.py"} <= names, names
    # the walk reaches the report package's helper subdirectory, not just its top level
    assert any(p.parent.name == "utils" and "report" in p.parts for p in _COPY_MODULES), \
        _COPY_MODULES
    # and it is genuinely a walk: the package dir listing and the set agree
    package_dir = Path(nicheiq_report.__file__).resolve().parent
    walked = {p.resolve() for p in package_dir.rglob("*.py") if p.name != "__init__.py"}
    assert walked <= set(_COPY_MODULES)


@pytest.mark.parametrize("path", _COPY_MODULES, ids=_module_ids(_COPY_MODULES))
def test_no_literal_in_any_report_copy_module_asserts_absence_as_fact(path):
    """The forward guard, over the derived SET. `test_no_rendered_string_...` covers what
    today's code paths reach; this covers a constant added tomorrow that no test drives
    yet. Reintroducing "No direct equivalent", "no incumbent match found", "0 competing
    posts found", or a null paired with a first-mover claim ANYWHERE in any report-copy
    module fails here, whether or not anything renders it."""
    offenders = claim_offenders_in_source(path)
    assert offenders == [], (
        f"{path.name} carries a literal asserting absence as fact, or drawing a market "
        f"position from a null:\n" + "\n".join(map(repr, offenders)))


def test_the_forward_guard_names_an_unlisted_module():
    """THE PROOF that the enumeration is derived rather than declared.

    Builds a throwaway package with a module this file has never heard of, points the same
    derivation at it, and requires the offending module to be NAMED. This is the test that
    would have failed in R2 and made the R3 regrowth impossible.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp) / "fake_report_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        # a module nobody listed, carrying the exact claim class that regrew
        (pkg / "a_module_nobody_listed.py").write_text(
            'HEADLINE = "0 competing posts found"\n'
            'BLURB = "Searched the platform and found no competitor. '
            'Potential first-mover opportunity."\n'
        )
        # and one that is clean, so the check is not simply flagging everything
        (pkg / "an_innocent_module.py").write_text(
            'OK = "Our searches did not surface a direct competitor."\n'
            'ALSO_OK = "Key market gaps identified: onboarding, billing."\n'
        )
        walked = sorted(p for p in pkg.rglob("*.py") if p.name != "__init__.py")
        assert len(walked) == 2, walked
        named = {p.name: claim_offenders_in_source(p) for p in walked}
        assert named["an_innocent_module.py"] == [], named["an_innocent_module.py"]
        flagged = named["a_module_nobody_listed.py"]
        assert flagged, "the derivation did not name a module it was never told about"
        assert {kind for kind, _, _ in flagged} == {"scope", "position-from-null"}, flagged


# ── (5) absent evidence is not evidence of absence ─────────────────────────────────

def test_the_digest_never_turns_a_blank_stamp_into_a_finding():
    """`idea_portfolio_summary` line 237 rendered blank/absent parity as "no incumbent
    match found" — a NEGATIVE FINDING manufactured out of missing data, fed verbatim into
    the portfolio-summary prompt (`build_idea_portfolio_digest` -> the analyst narrative
    the user reads). 94 ideas in `output/checkpoints/` carry a blank stamp.

    No vocabulary needed for this one: three states, and the state the probe never
    reached may not render as the state where it ran and came back empty.
    """
    absent = _digest(None)
    empty = _digest("")
    blank_ws = _digest("   ")
    searched = _digest("none found")

    def segment(line: str) -> str:
        return next(s for s in line.split("; ") if s.startswith("incumbent parity:"))

    assert segment(absent) == segment(empty) == segment(blank_ws), (
        "None, '' and whitespace are all 'we have no result' — they must render alike")
    assert segment(absent) != segment(searched), (
        "not-checked must not render as checked-and-empty")
    # ...and it must SAY unknown, rather than merely differ.
    assert "not checked" in segment(absent)
    assert "unknown" in segment(absent)


def test_the_none_found_note_discloses_the_searchs_dependence_on_the_ideas_wording():
    """A PIN, NOT A PROPERTY — said plainly so nobody mistakes it for one.

    The copy this round replaced ("No direct competitor turned up. …") ALREADY scoped its
    absence claim to the retrieval, so `unscoped_absence_claims` passes it and would pass
    it again if someone restored it. Measured on this repo's `output/checkpoints`, the
    thing a reader could not learn from it is the one the corpus says matters: the probe's
    queries are built from the idea's OWN vocabulary, and 533 of the 591 "none" stamps
    (90.2%) sit in a run that already holds a NAMED incumbent finding on another idea. So
    the disclosure is held here, by a pin, and the scope property is held above.
    """
    note = ivb.NONE_FOUND_NOTE
    assert unscoped_absence_claims(note) == []
    lowered = note.lower()
    assert "wording" in lowered, "the reader is not told what the search's reach depended on"
    assert "missed" in lowered, "the consequence of that dependence is not stated"


def test_the_digest_marks_a_none_stamp_as_a_retrieval_result():
    seg = next(s for s in _digest("none found").split("; ")
               if s.startswith("incumbent parity:"))
    assert unscoped_absence_claims(seg) == []
    assert "retrieval result" in seg


# ── (6) the STORED value and the parsed prefix are untouched ───────────────────────

@pytest.mark.parametrize("parity_key", sorted(PARITY_STATES))
def test_the_stored_stamp_and_its_parsed_prefix_survive_the_display_fix(parity_key):
    """>=7 consumers parse the stamp PREFIX: `_parity_cap` and rule (e)
    (`crews/unified_solution_crew.py`, `startswith("none")`), `niche_difficulty`
    (`startswith(("shipped","partial"))`), `idea_theses`, `market_brief`,
    `evidence_breadth`, `report_consistency`, and the frontend/backend
    `incumbentParityPhrase`. A display fix that moved the prefix would break capping and
    the go/no-go verdict at the same time."""
    stamp = PARITY_STATES[parity_key]
    block = _block(stamp)
    expected = (stamp or "").strip() or None
    assert block["incumbent_parity"] == expected
    if expected:
        assert (block["incumbent_parity"].lower().startswith("none")
                == expected.lower().startswith("none"))


@pytest.mark.parametrize("parity_key,expected_state", [
    ("absent", "not_checked"),
    ("empty", "not_checked"),
    ("none_found", "none_found"),
    ("none_bare", "none_found"),
    ("shipped", "shipped"),
    ("partial", "partial"),
    ("substitute", "adjacent"),
    ("bundled", "adjacent"),
])
def test_the_frontend_enum_is_unchanged(parity_key, expected_state):
    """`parts[space_occupied].state` is what `ValidationVerdict.svelte` keys on ("Who
    ships in this category" vs "Competitors and adjacent tools"). The copy moved; the
    enum must not."""
    block = _block(PARITY_STATES[parity_key])
    part = next(p for p in block["parts"] if p["key"] == "space_occupied")
    assert part["state"] == expected_state


# ── (7) R3: the marketing-channel SET, walked over the zero-result state space ──────
#
# WHERE THE CLAIM REGREW. `report_generator._identify_marketing_channels` appends a
# channel for every ENABLED platform whose `posts_found` is 0, and shipped:
#
#     channel_name          "Hacker News (Content Gap)"
#     channel_type          "Content Gap"
#     target_audience_size  "0 competing posts found"
#     rationale             "Searched Hacker News and found no existing content for this
#                            niche. Potential first-mover opportunity if audience overlaps."
#
# live in `go_to_market_blueprint.recommended_channels[2]` of the 2026-08-17 run. FOUR
# overclaims, not three: the brief named the rationale's two and the audience-size field,
# and missed that the channel is NAMED after a gap it has not established.
#
# WHAT `posts_found` COUNTS — re-derived, because the audience-size field assumed
# competitors. `research_flow.stage_2_search_and_discover` sets it to `len(hn_posts)` where
# `_search_hackernews_pipeline` returns `collection.posts`, i.e. the `relevant_count` of
# `candidate_count` Algolia candidates that survived a semantic gate; the discovery writer
# then recounts hackernews as its surviving `generic_posts`. So it counts the PLATFORM'S OWN
# community discussion that this run's queries retrieved AND the gate kept — never
# competitors, never marketing content. A zero is a retrieval-and-filter outcome, and
# `sources_searched` records only the final 0, so the report cannot even tell "nothing was
# retrieved" from "the gate rejected everything".


def _platform_keys() -> list[str]:
    """The platform SET, derived from its PRODUCER. `stage_2_search_and_discover` writes
    `self.state.sources_searched` as a dict literal; the keys are read out of that literal
    by AST, so a platform added to the flow tomorrow is covered here with no edit. The
    unmapped key is appended on purpose: `_identify_marketing_channels` falls back to the
    raw platform string as the display label, which is its own rendering branch."""
    from nicheiq.flows import research_flow

    src = Path(research_flow.__file__).read_text()
    keys: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (isinstance(target, ast.Attribute) and target.attr == "sources_searched"
                    and isinstance(node.value, ast.Dict)):
                keys |= {k.value for k in node.value.keys
                         if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert keys, "the platform set could not be derived from research_flow"
    return sorted(keys) + ["a_platform_added_tomorrow"]


PLATFORM_KEYS = _platform_keys()


def _channels(sources: dict) -> list:
    """Drive the real method. `social_content`/`seo_strategy_report` are absent so the
    evidence-backed channels drop out and the zero-result branch is what is left; the
    method's own try/except returns [] on any error, so every caller below asserts the
    expected channel COUNT — a swallowed exception must not read as a clean pass."""
    gen = rg.ReportGenerator.__new__(rg.ReportGenerator)
    gen.state = SimpleNamespace(
        sources_searched=sources, social_content=None, seo_strategy_report=None)
    return gen._identify_marketing_channels()


def test_the_channel_harness_is_not_silently_empty():
    """The control for section (7). `_identify_marketing_channels` swallows exceptions and
    returns []; without this, every property below would pass vacuously."""
    channels = _channels({p: {"enabled": True, "posts_found": 0} for p in PLATFORM_KEYS})
    assert len(channels) == len(PLATFORM_KEYS), channels
    assert all(c.priority == "Low" for c in channels), channels


@pytest.mark.parametrize("platform", PLATFORM_KEYS)
def test_no_zero_result_channel_string_claims_more_than_the_run_knows(platform):
    """The enumeration is the WALK: every string field of the channel object, over every
    platform the producer can write. Three properties, each for a distinct overclaim."""
    channels = _channels({platform: {"enabled": True, "posts_found": 0}})
    assert len(channels) == 1, channels
    offenders = []
    for text in _strings(channels[0].model_dump()):
        offenders += [("scope", text, c) for c in unscoped_absence_claims(text)]
        offenders += [("attribution", text, c) for c in unattributed_null_claims(text)]
        offenders += [("position", text, c) for c in position_claims(text)]
    assert offenders == [], (
        f"platform={platform}: the zero-result channel claims what a null retrieval "
        f"cannot support:\n" + "\n".join(map(repr, offenders)))


@pytest.mark.parametrize("platform", PLATFORM_KEYS)
def test_the_zero_result_channel_names_the_instrument_that_produced_the_zero(platform):
    """The positive half. Deleting the offending sentences would satisfy the three
    negative properties above while telling the reader nothing; the rationale has to say
    what actually happened."""
    channel = _channels({platform: {"enabled": True, "posts_found": 0}})[0]
    assert _INSTRUMENT.search(channel.rationale), channel.rationale
    assert _INSTRUMENT.search(channel.target_audience_size or ""), channel.target_audience_size


def test_the_zero_result_rationale_discloses_the_same_limit_as_the_accepted_copy():
    """A PIN, NOT A PROPERTY — said plainly, as R2 did for `NONE_FOUND_NOTE`.

    The report must not contradict itself: `idea_validation_block.NONE_FOUND_NOTE` tells
    the reader the search ran on the idea's own WORDING and that a differently-described
    rival can be MISSED. The channel copy is the same epistemic situation one layer out,
    so it discloses the same two things about the query set. The scope/attribution/
    position properties above hold the claim; this holds the disclosure.
    """
    rationale = _channels({"hackernews": {"enabled": True, "posts_found": 0}})[0].rationale
    lowered = rationale.lower()
    assert "wording" in lowered, "the reader is not told what the queries' reach depended on"
    assert "missed" in lowered, "the consequence of that dependence is not stated"
    # and the accepted copy's own properties still hold on it
    assert unscoped_absence_claims(ivb.NONE_FOUND_NOTE) == []
    assert unscoped_absence_claims(rationale) == []


@pytest.mark.parametrize("platform", PLATFORM_KEYS)
def test_a_platform_that_was_never_searched_yields_no_channel(platform):
    """State distinction, the same one section (5) holds for the parity stamp: not-searched
    is not searched-and-empty. A disabled platform has no retrieval result at all, so it
    may not be rendered as one."""
    assert _channels({platform: {"enabled": False, "posts_found": 0}}) == []
    assert _channels({platform: {"posts_found": 0}}) == []


@pytest.mark.parametrize("platform", PLATFORM_KEYS)
def test_a_platform_with_results_yields_no_zero_result_channel(platform):
    assert _channels({platform: {"enabled": True, "posts_found": 1}}) == []
