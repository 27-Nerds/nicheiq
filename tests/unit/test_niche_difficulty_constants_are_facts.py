"""D1 — the META-fix: no deterministic string this codebase authors may prescribe a money shape.

Rounds 12-14 each removed a monetisation LICENSE from wherever it had last been found, and each
time the same license turned up somewhere else. Round 14's blind critic named why: the prompt
license was withdrawn while the identical prescriptions survived as module-level CONSTANTS that
are both rendered to the reader (`key_challenges`) and injected into the very prompt carrying the
new remit block. Its ruling — "the residual has not shrunk, it has hardened, because a model can
be re-prompted and a hard-coded string cannot" — plus its verdict that "a unit test asserting
every module-level `_*_CHALLENGE` constant is clean would have caught all of this mechanically".

This is that test, and round 16 closed the half of the loop that was still hand-written. It
ENUMERATES rather than lists, from FOUR independent sources, so a prescribing string added
tomorrow is caught without anyone remembering to add it:

  1. ``_module_prose`` — module-level values, recursively: bare strings, dicts (including
     dict-of-dict), LISTS, TUPLES, and the attributes of module-level CLASSES. Round 15 read only
     strings and one level of dict, so a list, a tuple or a class attribute escaped it.
  2. ``_auto_rendered_prose`` — every function DEFINED in the module, discovered with
     ``inspect.getmembers`` and called with arguments synthesised from its annotations. A
     brand-new prose-BUILDING function is exercised without being named anywhere.
  3. ``_source_literal_prose`` — every non-docstring prose STRING LITERAL in the module source.
     This is the backstop that needs no call at all: the inline literals appended inside
     ``assess_niche_difficulty``, the branches of a function whose arguments cannot be synthesised,
     a literal nested three containers deep — all of them are literals in the file, so all of them
     are read. Legitimate hits are adjudicated in ``_SOURCE_LITERAL_ADJUDICATIONS`` with a reason.
  4. ``_RENDERED_PROSE`` — the hand-written renderings, kept because they call the prose builders
     with REPRESENTATIVE arguments (a real price string, a real wallet class), which the
     annotation-synthesised call in (2) cannot produce.

Documented residue (deliberately, rather than silently): a function whose arguments cannot be
synthesised AND which builds its prose entirely by interpolation from runtime objects, holding no
literal of its own, is invisible to all four. ``test_the_uncallable_residue_is_documented`` pins
the functions that are uncallable and DO hold prose literals, so that set cannot grow unreviewed;
the fully-interpolated case is covered instead at the point of use, by ``_facts_only`` at fact-pack
construction — see the last two tests.

The two detectors are the project's own, so the test cannot drift from the runtime contract:

  * ``has_zero_price_prescription`` — polarity-blind: does the string RECOMMEND a shape in which
    this audience does not pay?
  * ``_paying_wallet_copy_rule_labels`` — the named prescriptions plus the general case (it calls
    ``has_zero_price_prescription`` itself, so it is the stricter of the two; both are asserted so
    a failure names which register was breached).

``has_unsanctioned_commercial_claim`` is deliberately NOT asserted over every constant: it is
deny-by-default, correct only for the verdict card on a verified paying wallet, and several
constants legitimately REPORT money facts ("the free/DIY route is the real competition") that it
rejects by design. It is asserted where it IS the contract — over the sanctioned statements, which
must recognise themselves — in ``test_every_sanctioned_statement_recognises_itself``.
"""

import ast
import functools
import inspect
import textwrap
from types import SimpleNamespace

import pytest

from nicheiq.report import report_generator
from nicheiq.utils import idea_portfolio_summary as portfolio
from nicheiq.utils import niche_difficulty as nd
from nicheiq.utils import segment_payability
from nicheiq.validators import report_consistency, score_validators

# Modules whose module-level prose can reach `key_points` / `key_challenges` / a prompt.
#
# The first two are where the relocated license kept turning up. The other four are the
# READER-COPY modules: `report_generator` assembles the strings the report renders, the two
# validators author the concern/caveat lines that ride beside a score, and `segment_payability`
# both scores a segment's wallet and writes the phrase describing it. None of them is a
# monetisation prompt, which is exactly why nobody looked at them — and the same enumeration that
# guards `niche_difficulty` costs nothing to point at them.
_SCANNED_MODULES = (
    nd,
    portfolio,
    report_generator,
    score_validators,
    report_consistency,
    segment_payability,
)

# Prose-building functions: a constant with a free-text or numeric slot in it. Called with
# REPRESENTATIVE arguments, which is what this hand-written table still buys over the
# annotation-synthesised auto-discovery below.
_RENDERED_PROSE = {
    "niche_difficulty._wallet_challenge(evidence)": lambda: nd._wallet_challenge(
        "$0-25/mo total, start free"
    ),
    "niche_difficulty._wallet_challenge('')": lambda: nd._wallet_challenge(""),
    "niche_difficulty._wallet_positive_note": lambda: nd._wallet_positive_note(
        "$99-399/mo DaySmart Vet"
    ),
    "niche_difficulty._incumbent_density_challenge": lambda: nd._incumbent_density_challenge(9, 4),
    "niche_difficulty._wtp_judgment(weak)": lambda: nd._wtp_judgment(0.55, 0.0),
    "niche_difficulty._wtp_judgment(moderate)": lambda: nd._wtp_judgment(0.7, 0.1),
    "niche_difficulty._wtp_judgment(strong)": lambda: nd._wtp_judgment(0.8, 0.3),
    "niche_difficulty._wtp_judgment(paying-wallet corpus gap)": lambda: nd._wtp_judgment(
        0.4, 0.0, "paying", "$99/mo incumbent"
    ),
    "niche_difficulty._paying_wallet_buyer_note(consumer)": lambda: nd._paying_wallet_buyer_note(
        "consumer"
    ),
    "niche_difficulty._paying_wallet_buyer_note(indie-hobbyist)": (
        lambda: nd._paying_wallet_buyer_note("indie-hobbyist")
    ),
    "niche_difficulty.derive_monetization_directive(weak wallet)": (
        lambda: nd.derive_monetization_directive(
            [SimpleNamespace(commercial_intent=0.2)], [SimpleNamespace(payability_score=0.1)]
        )
    ),
    "niche_difficulty.derive_monetization_directive(weak wallet, commercial pain)": (
        lambda: nd.derive_monetization_directive(
            [SimpleNamespace(commercial_intent=0.8)], [SimpleNamespace(payability_score=0.1)]
        )
    ),
    "niche_difficulty.derive_monetization_directive(viable wallets)": (
        lambda: nd.derive_monetization_directive(
            [SimpleNamespace(commercial_intent=0.5)], [SimpleNamespace(payability_score=0.7)]
        )
    ),
    "niche_difficulty.derive_monetization_directive(no data)": (
        lambda: nd.derive_monetization_directive([SimpleNamespace(commercial_intent=0.5)], [])
    ),
    "niche_difficulty.derive_monetization_directive(paying wallet)": (
        lambda: nd.derive_monetization_directive(
            [SimpleNamespace(commercial_intent=0.2)],
            [SimpleNamespace(payability_score=0.1)],
            {"wallet_class": "paying", "evidence": "$99/mo incumbent"},
        )
    ),
    "niche_difficulty.monetization_guidance(paying)": lambda: nd.monetization_guidance(
        {"wallet_class": "paying", "evidence": "$99/mo"}
    ),
    "niche_difficulty.monetization_guidance(priced mixed)": lambda: nd.monetization_guidance(
        {"wallet_class": "mixed", "evidence": "Truckstop $42-159/mo"}
    ),
    "niche_difficulty.monetization_guidance(mixed)": lambda: nd.monetization_guidance(
        {"wallet_class": "mixed", "evidence": "quotes only"}
    ),
    "niche_difficulty.monetization_guidance(free-culture)": lambda: nd.monetization_guidance(
        {"wallet_class": "free-culture", "evidence": "every route here is free"}
    ),
    "niche_difficulty.monetization_guidance(unknown)": lambda: nd.monetization_guidance(None),
}

# A string is PROSE (rather than a vocabulary token, a regex source, a diagnostic label or a
# format fragment) when it reads as a sentence. Five words plus a space-separated shape is enough
# to separate "budgeted-business" and "zero-price shape prescribed for a priced niche" from
# anything a reader would be shown. The bar is deliberately low: over-inclusion costs nothing
# here, and every constant this test has ever needed to catch is far above it.
_MIN_PROSE_WORDS = 5

# ...with one exclusion. This module's detectors ARE long regex sources, and a regex that matches
# a prescription necessarily contains the prescription's vocabulary. Reading `_ZERO_PRICE_SHAPE_RE`
# as reader prose would make the detector fail on itself.
_REGEX_SOURCE_MARKERS = ("(?:", "(?P<", "(?<", "[^", "\\b", "\\s", "\\w", "\\d", "{0,")


def _is_prose(value: str) -> bool:
    if any(marker in value for marker in _REGEX_SOURCE_MARKERS):
        return False
    return len(value.split()) >= _MIN_PROSE_WORDS and " " in value.strip()


def _collect_prose(prefix: str, value, found: dict[str, str], depth: int = 0) -> None:
    """Recursively read strings out of a value's containers.

    Round 15 read `str` and one level of `dict`. A list, a tuple, a dict-of-dict and a class
    attribute all escaped that, and all four are ordinary ways to hold a rendered string.
    """
    if depth > 4:
        return
    if isinstance(value, str):
        if _is_prose(value):
            found[prefix] = value
    elif isinstance(value, dict):
        for key, child in value.items():
            _collect_prose(f"{prefix}[{key!r}]", child, found, depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for index, child in enumerate(value):
            _collect_prose(f"{prefix}[{index}]", child, found, depth + 1)


def _module_prose(module) -> dict[str, str]:
    """Every module-level prose string in `module`, through containers and class bodies."""
    found: dict[str, str] = {}
    short = module.__name__.rsplit(".", 1)[-1]
    for name, value in vars(module).items():
        if name.startswith("__"):
            continue
        if inspect.isclass(value) and getattr(value, "__module__", None) == module.__name__:
            for attribute, child in vars(value).items():
                if attribute.startswith("__"):
                    continue
                _collect_prose(f"{short}.{name}.{attribute}", child, found)
            continue
        if inspect.isfunction(value) or inspect.ismodule(value):
            continue
        _collect_prose(f"{short}.{name}", value, found)
    return found


def _synthesised_argument(annotation):
    """A degenerate value of the annotated type, or ``(None, False)`` when we cannot make one."""
    if annotation is inspect.Parameter.empty:
        return None, False
    text = str(annotation)
    if text in ("<class 'str'>", "str"):
        return "", True
    if text in ("<class 'float'>", "float"):
        return 0.0, True
    if text in ("<class 'int'>", "int"):
        return 0, True
    if text in ("<class 'bool'>", "bool"):
        return False, True
    if text.startswith(("Optional[", "typing.Optional[")):
        return None, True
    if text.startswith(("list", "<class 'list'>", "tuple", "<class 'tuple'>")):
        return [], True
    if text.startswith(("dict", "<class 'dict'>")):
        return {}, True
    return None, False


def _module_functions(module):
    return [
        (name, function)
        for name, function in inspect.getmembers(module, inspect.isfunction)
        if getattr(function, "__module__", None) == module.__name__
    ]


def _auto_rendered_prose(module) -> tuple[dict[str, str], dict[str, str]]:
    """Call every function in `module` with synthesised arguments; return (prose, residue).

    This is the half of the loop round 15 left hand-written: a brand-new prose-BUILDING function
    is exercised here without being named in `_RENDERED_PROSE`.
    """
    found: dict[str, str] = {}
    residue: dict[str, str] = {}
    short = module.__name__.rsplit(".", 1)[-1]
    for name, function in _module_functions(module):
        arguments = {}
        synthesised = True
        for parameter in inspect.signature(function).parameters.values():
            if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
                continue
            if parameter.default is not parameter.empty:
                continue
            value, ok = _synthesised_argument(parameter.annotation)
            if not ok:
                synthesised = False
                break
            arguments[parameter.name] = value
        if not synthesised:
            residue[f"{short}.{name}"] = "arguments cannot be synthesised from annotations"
            continue
        try:
            rendered = function(**arguments)
        except Exception as error:  # a degenerate call is allowed to be rejected
            residue[f"{short}.{name}"] = f"raised {type(error).__name__} on a degenerate call"
            continue
        _collect_prose(f"{short}.{name}()", rendered, found)
    return found, residue


@functools.cache
def _non_docstring_literals(source_owner) -> list[tuple[int, str]]:
    """Every prose string literal in a module's or a function's source, minus the docstrings.

    Cached: this reads the file off disk and parses it, which no monkeypatch of a runtime
    attribute can change, and `report_generator` alone is a quarter of a megabyte re-parsed once
    per parametrised case without it.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(source_owner)))
    docstrings = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and _is_prose(node.value)
    ]


# Source literals that are NOT reader copy, each with the reason. Keyed by module short name;
# the value is the (fragment, reason) pair, matched against the literal.
_SOURCE_LITERAL_ADJUDICATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "idea_portfolio_summary": (
        (
            "Write an honest analyst's summary of this idea pool",
            "The analyst PROMPT body. Its commercial paragraph forbids the analyst from choosing "
            "a money shape, and it has to name the vocabulary it forbids (wallet, pricing, "
            "subscription, free/paid, sponsor) in order to forbid it.",
        ),
        (
            "This must be the summary's only wallet, pricing",
            "The closing clause of that same remit: the one sanctioned wallet sentence is the "
            "summary's ONLY commercial claim. A restriction, not a license.",
        ),
    ),
    # The four reader-copy modules added to `_SCANNED_MODULES` hold no zero-price prescription at
    # all — the polarity-blind detector is silent on every literal in them. Three literals trip
    # one NAMED rule, `market willingness to pay declared weak`, which is a clause of the
    # PAYING-WALLET contract: it forbids copy that denies the wallet on a niche whose wallet was
    # verified as paying. All three are per-SEGMENT findings or the prompt that produces them,
    # emitted from a segment's own payability score and never from the niche wallet reading, so
    # the rule they trip is not the contract they are published under.
    "report_generator": (
        (
            "with weak willingness-to-pay — the build is feasible",
            "The `primary_concern` written when ONE segment's payability score falls under "
            "`payability_low_threshold`. It grades that segment and then asks for payment "
            "evidence; it neither denies the niche's wallet nor names a money shape.",
        ),
    ),
    "score_validators": (
        (
            "Target segment has weak willingness-to-pay for direct-paid pricing",
            "The same per-segment finding in the validator that authors it — a fallback "
            "`primary_concern` beside a segment payability score, held to Conditional. A grade "
            "on one segment, not a verdict on the niche and not a prescription.",
        ),
    ),
    "segment_payability": (
        (
            "Score each audience segment's ability and HABIT of paying for software",
            "The scoring PROMPT body. It has to name budget authority, paying habits and the "
            "payability classes in order to ask the model to grade them; the copy it produces is "
            "the class token, which the two entries above cover where it is rendered.",
        ),
    ),
}


def _adjudicated_literal(short: str, literal: str) -> str | None:
    for fragment, reason in _SOURCE_LITERAL_ADJUDICATIONS.get(short, ()):
        if fragment in literal:
            return reason
    return None


def _source_literal_prose(module) -> dict[str, str]:
    short = module.__name__.rsplit(".", 1)[-1]
    return {
        f"{short}.py:L{line}": literal
        for line, literal in _non_docstring_literals(module)
        if _adjudicated_literal(short, literal) is None
    }


def _all_deterministic_prose() -> dict[str, str]:
    found: dict[str, str] = {}
    for module in _SCANNED_MODULES:
        found.update(_module_prose(module))
        auto, _residue = _auto_rendered_prose(module)
        found.update(auto)
        found.update(_source_literal_prose(module))
    for name, build in _RENDERED_PROSE.items():
        rendered = build()
        if rendered and _is_prose(rendered):
            found[name] = rendered
    return found


def test_enumeration_actually_finds_the_constants_it_is_supposed_to_guard():
    """A test that silently enumerates nothing passes forever. Pin the floor and the landmarks."""
    prose = _all_deterministic_prose()
    assert len(prose) >= 150, sorted(prose)
    for expected in (
        "niche_difficulty._WEAK_WTP_CHALLENGE",
        "niche_difficulty._EPISODIC_CHALLENGE",
        "niche_difficulty._ADJACENT_MONEY_CHALLENGE",
        "niche_difficulty._SUBSTITUTE_CHALLENGE",
        "niche_difficulty._SATURATION_CHALLENGE",
        "niche_difficulty._INCUMBENT_DENSE_CHALLENGE",
        "niche_difficulty._SERP_OWNED_CHALLENGE",
        "niche_difficulty._BUYER_CLASS_NOTES['consumer']",
        "niche_difficulty._BUYER_CLASS_NOTES['indie-hobbyist']",
        "niche_difficulty._MONETIZATION_WTP_LADDER",
        "niche_difficulty._MONETIZATION_GUIDANCE['free-culture']",
        # Auto-discovered prose builders, named nowhere in this file (round 16, Priority 5).
        "niche_difficulty._fit_headline()",
        "niche_difficulty._shape_concentration_word()",
    ):
        assert expected in prose, f"{expected} dropped out of the enumeration"
    # And the source-literal backstop, which sees the INLINE literals no constant name reaches.
    assert any(name.startswith("niche_difficulty.py:L") for name in prose)
    assert any(name.startswith("idea_portfolio_summary.py:L") for name in prose)
    # The scanned SET, written out rather than derived from `_SCANNED_MODULES` — a test that
    # reads the tuple it is guarding cannot notice the tuple shrinking back to two modules.
    for short in (
        "niche_difficulty",
        "idea_portfolio_summary",
        "report_generator",
        "score_validators",
        "report_consistency",
        "segment_payability",
    ):
        assert any(name.startswith(f"{short}.") for name in prose), f"{short} is no longer scanned"


@pytest.mark.parametrize("name", sorted(_all_deterministic_prose()))
def test_no_deterministic_prose_prescribes_a_commercial_shape(name):
    """Every string this codebase authors states a FACT. None of them selects how to charge.

    This is the whole of D1 in one assertion. The rewrite that made each of these a fact is
    reversible by anyone; this is what makes reversing it fail.
    """
    copy = _all_deterministic_prose()[name]
    assert not nd.has_zero_price_prescription(copy), (
        f"{name} RECOMMENDS a commercial shape rather than reporting one.\n{copy!r}"
    )
    assert nd._paying_wallet_copy_rule_labels(copy) == [], (
        f"{name} breaks a named commercial-copy rule.\n{copy!r}"
    )


_MUTANTS = [
    # Verbatim the constant round 15 found relocated (the pre-rewrite `_WEAK_WTP_CHALLENGE`),
    # caught by the NAMED rules: an anti-subscription prescription plus sponsor-funded free
    # distribution.
    "No pain shows strong buying signals in this run: plan a free-tool + distribution "
    "monetization (lead-gen, sponsorship, a cheap team tier), not subscription pricing.",
    # A shape nobody has written down yet, caught by the polarity-blind detector instead —
    # neither an anti-subscription word nor a named funding model in it.
    "The realistic path here is to hand the whole thing over to the trade association and "
    "let them carry the hosting bill.",
    # And the register the YAML few-shot used: a recommendation smuggled in as an example.
    "Ship it as a free, affiliate-and-lead-gen-supported tool rather than something the shops buy.",
]


@pytest.mark.parametrize("mutant", _MUTANTS)
def test_the_enumeration_catches_a_newly_added_prescribing_constant(monkeypatch, mutant):
    """Mutant proof: the guard must fail on a constant nobody told it about.

    A test that only checks the constants that exist today is a snapshot, not a guard. Each mutant
    is added at runtime under a fresh name and the enumeration is required to (a) find it without
    being told and (b) reject it.
    """
    monkeypatch.setattr(nd, "_ROUND_16_CHALLENGE", mutant, raising=False)

    prose = _all_deterministic_prose()
    assert "niche_difficulty._ROUND_16_CHALLENGE" in prose
    assert (
        nd.has_zero_price_prescription(mutant)
        or nd._paying_wallet_copy_rule_labels(mutant) != []
    )

    with pytest.raises(AssertionError):
        test_no_deterministic_prose_prescribes_a_commercial_shape(
            "niche_difficulty._ROUND_16_CHALLENGE"
        )


def _mutant_class(mutant):
    class _Round16Card:
        blurb = mutant

    _Round16Card.__module__ = nd.__name__
    return _Round16Card


def _mutant_function(mutant):
    def _round16_note(evidence: str) -> str:
        return f"{mutant} {evidence}".strip()

    _round16_note.__module__ = nd.__name__
    return _round16_note


@pytest.mark.parametrize("shape,build", [
    ("list", lambda mutant: [mutant]),
    ("tuple", lambda mutant: ("preamble", (mutant,))),
    ("nested dict", lambda mutant: {"paying": {"line": mutant}}),
    ("class attribute", _mutant_class),
    ("prose-building function", _mutant_function),
])
def test_the_enumeration_catches_the_shapes_round_15_could_not_see(monkeypatch, shape, build):
    """Round 15's enumeration read strings and one level of dict. These five escaped it.

    All five were latent (none held prose at the time), which is exactly why they had to be closed
    before one of them acquired some. Each is installed at runtime and the enumeration must find
    and reject it without being told the name.
    """
    mutant = _MUTANTS[1]
    monkeypatch.setattr(nd, "_ROUND_16_SHAPE", build(mutant), raising=False)

    prose = _all_deterministic_prose()
    hits = [name for name, copy in prose.items() if mutant in copy and "_ROUND_16_SHAPE" in name]
    assert hits, f"a prescribing string held as a {shape} escaped the enumeration: {mutant!r}"

    for name in hits:
        with pytest.raises(AssertionError):
            test_no_deterministic_prose_prescribes_a_commercial_shape(name)


def test_the_uncallable_residue_is_documented():
    """Functions auto-discovery cannot call, and that still hold prose literals of their own.

    Their literals are covered by `_source_literal_prose`, so nothing here is unguarded — but the
    SET is pinned so it cannot grow silently, and so the next author sees which functions the
    call-based half of the enumeration does not reach.
    """
    documented = {
        "niche_difficulty._commercial_copy_violations",
        "niche_difficulty._deterministic_paying_wallet_fallback",
        "niche_difficulty._fallback_narrative",
        "niche_difficulty._paying_wallet_contract_baseline",
        "niche_difficulty._paying_wallet_copy_violations",
        "niche_difficulty._wtp_judgment",
        "niche_difficulty.assess_niche_difficulty",
        "niche_difficulty.derive_monetization_directive",
        "niche_difficulty.detect_recommendation_audience_drift",
        "niche_difficulty.generate_niche_difficulty_verdict",
        "niche_difficulty.reconcile_persisted_niche_difficulty_verdict",
        "idea_portfolio_summary._idea_digest_line",
        "segment_payability._segment_evidence",
        "segment_payability.payability_phrase",
        "segment_payability.payer_retarget_hint",
        "segment_payability.score_segment_payability",
    }
    holding_prose = set()
    for module in _SCANNED_MODULES:
        short = module.__name__.rsplit(".", 1)[-1]
        _auto, residue = _auto_rendered_prose(module)
        for qualified in residue:
            function = getattr(module, qualified.rsplit(".", 1)[-1])
            if _non_docstring_literals(function):
                holding_prose.add(f"{short}.{qualified.split('.', 1)[-1]}")
    assert holding_prose == documented, (
        "The set of uncallable prose-holding functions changed. Every literal in them is still "
        "read by the source-literal scan; update this list so the residue stays explicit.\n"
        f"added: {sorted(holding_prose - documented)}\n"
        f"gone:  {sorted(documented - holding_prose)}"
    )


def test_every_sanctioned_statement_recognises_itself():
    """A statement the codebase declares sanctioned must survive its own deny-by-default boundary.

    This is where ``has_unsanctioned_commercial_claim`` IS the contract: if a sanctioned statement
    is rewritten and its entry in the sanctioned list is not, the verdict card silently starts
    rejecting its own deterministic copy and falls back on every run.
    """
    sanctioned = [
        nd._PAYING_WALLET_CORPUS_CHALLENGE,
        nd._PAYING_WALLET_MONETIZATION_DIRECTIVE,
        nd._MINIMAL_PAYING_WALLET_NARRATIVE,
        nd._PAYING_WALLET_CONSUMER_BUYER_NOTE,
        nd._PAYING_WALLET_INDIE_BUYER_NOTE,
        nd._BUYER_CLASS_NOTES["budgeted-business"],
        nd._BUYER_CLASS_NOTES["smb-operator"],
        nd._BUYER_CLASS_NOTES["mixed"],
        nd._BUYER_CLASS_NOTES["prosumer"],
        nd._wallet_positive_note("$99-399/mo DaySmart Vet"),
        nd._incumbent_density_challenge(9, 4),
        *nd._MONETIZATION_GUIDANCE.values(),
        nd._MONETIZATION_GUIDANCE_UNKNOWN,
    ]
    unrecognised = [
        copy for copy in sanctioned if nd.has_unsanctioned_commercial_claim(copy)
    ]
    assert unrecognised == []


# --------------------------------------------------------------------------------------------
# The other half of the guard: the appends inside `assess_niche_difficulty` are INLINE literals.
# The source-literal scan above reads them where they are written; this validates them where the
# list is BUILT, which also covers a point assembled at runtime from non-literal parts.
# --------------------------------------------------------------------------------------------


def _pain(ci=0.4, addressable="full"):
    return SimpleNamespace(tool_addressable=addressable, commercial_intent=ci)


def _idea(novelty=0.6):
    return SimpleNamespace(
        novelty_score=novelty,
        novelty_score_raw=novelty,
        project_type="saas",
        mechanism_tag="workflow",
        audience_fit=True,
        requires_data_aggregation=False,
        data_access_model="public",
        incumbent_parity="none found",
        adjacent_market_parity=None,
        tags=SimpleNamespace(usage_cadence="continuous"),
    )


def _niche_context():
    return SimpleNamespace(
        audience_scope="whole_niche", user_target_audience="independent veterinary clinics"
    )


@pytest.mark.parametrize("wallet", [
    None,
    {"wallet_class": "paying", "evidence": "$99-399/mo DaySmart Vet"},
    {"wallet_class": "mixed", "evidence": "Truckstop $42-159/mo"},
    {"wallet_class": "mixed", "evidence": "quotes only"},
    {"wallet_class": "free-culture", "evidence": "every route here is free"},
])
def test_a_built_fact_pack_never_carries_a_prescription(wallet):
    """The real output, across every wallet reading, on the signal mix that fires the most points."""
    pains = [_pain(ci) for ci in (0.55, 0.4, 0.3, 0.2)]
    ideas = [_idea()] * 4
    for idea in ideas:
        idea.incumbent_parity = "substitute: a spreadsheet already does this"
        idea.adjacent_market_parity = "sold to logistics brokers"
        idea.tags = SimpleNamespace(usage_cadence="episodic")

    fp = nd.assess_niche_difficulty(
        pains,
        ideas,
        _niche_context(),
        concept_duplication_rate=0.6,
        segments=[SimpleNamespace(
            segment_name="solo vets", budget_sensitivity="high",
            payability_score=0.15, payability_class="personal-wallet")],
        niche_wallet_brief=wallet,
        incumbent_map=[{"name": f"Tool{i}", "pricing": "$49/mo"} for i in range(9)],
        serp_owned_share=0.8,
    )

    assert fp.key_points, "the fixture is supposed to fire several points"
    for point in [*fp.key_points, *fp.key_strengths]:
        assert not nd.has_zero_price_prescription(point), point
        assert nd._paying_wallet_copy_rule_labels(point) == [], point


def test_fact_pack_construction_drops_a_prescribing_point_instead_of_publishing_it(monkeypatch):
    """Mutant proof for the runtime half: an INLINE prescription never reaches the fact pack.

    Round 14 removed the prompt license and round 15 found it in a constant. The next place it can
    hide is a literal appended in this function, where it has no name to enumerate — so the list is
    filtered at construction rather than trusted.
    """
    mutant = (
        "Most products in this niche are used episodically. Favor one-time purchases, credits, "
        "or a lead-gen tool."
    )
    monkeypatch.setattr(nd, "_EPISODIC_CHALLENGE", mutant)
    assert nd.has_zero_price_prescription(mutant)

    ideas = [_idea() for _ in range(4)]
    for idea in ideas:
        idea.tags = SimpleNamespace(usage_cadence="episodic")

    fp = nd.assess_niche_difficulty(
        [_pain(0.8), _pain(0.75)], ideas, _niche_context()
    )

    assert mutant not in fp.key_points
    assert not any(nd.has_zero_price_prescription(point) for point in fp.key_points)
