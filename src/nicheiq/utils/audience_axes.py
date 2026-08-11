"""Typed buyer-identity axes for recommendation-scoped audience comparison.

Lexical overlap answers "are these two strings similar", which is the wrong question. A buyer
identity can change completely inside near-identical wording ("clinic owners" ->
"clinic staff") and can survive a total rewording ("Independent veterinary clinics managing
medication inventory" -> "Owner-operated animal hospitals handling drug stock"). A token
comparator gets both backwards.

So this module does not compare wording. It extracts a small set of TYPED axes -- who inside
the business, how many sites they run, whether they are independent or corporate-owned, and
whether they are a generalist or a specialist -- and compares those. Every axis is ternary:
a value, or ``None`` meaning the phrase does not say. An axis that cannot be read confidently
on BOTH sides contributes nothing, so an unreadable phrase produces silence, never a guess.
That is deliberate: a notice that cries wolf is ignored, which lands in the same place as not
shipping one.

The numeric half of the scale axis reuses the grounded interval parser already proven in
``speaker_attribution`` ("5-20 locations" -> [5, 20], "5+ sites" -> [5, inf), "under 5
branches" -> [0, 5)), rather than inventing a second number reader.

There is deliberately NO "what kind of business is it" axis. Deciding that "clinics" and
"animal hospitals" name the same business, while "clinics" and "grooming salons" do not,
needs an open-ended ontology; every attempt at one in this codebase has been the source of
the false alarms rather than the catches. Business type is left unjudged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ..models.research_state import AudienceDriftNotice
from .speaker_attribution import _SCALE_PATTERN, _normalized_unit, _parse_scales

# ── Axis vocabularies ────────────────────────────────────────────────────────────────────
# Each entry is (compiled pattern, axis value). A phrase that matches patterns for two
# different values on one axis is ambiguous and reads as unknown.

# Read as "a different {label} than you asked for", so every label has to survive that frame.
AXIS_LABELS: dict[str, str] = {
    "party": "type of buyer (the business, or the people it serves)",
    "authority": "decision-maker inside the business",
    "scale": "operating scale",
    "independence": "ownership model",
    "specialization": "type of practice",
}

# Which side of the transaction the named party sits on. The provider list is deliberately
# made of business-shape words rather than trades, and the consumer list of person-roles that
# only ever name someone a business SERVES. Words a provider description routinely uses about
# its own customers -- client, customer, buyer -- are excluded from the consumer list: they
# appear inside phrases like "editors managing client revision rounds", where the buyer is
# still the editor.
_PARTY_MARKERS: tuple[tuple[str, str], ...] = (
    (r"businesse?s?\b", "provider"),
    (r"compan(?:y|ies)\b", "provider"),
    (r"firms?\b", "provider"),
    (r"practices?\b", "provider"),
    (r"studios?\b", "provider"),
    (r"operators?\b", "provider"),
    # No `professionals?`: it matches the ADJECTIVE far more often than the noun ("professional
    # scenes", "professional kitchens"), and an adjective says nothing about who is buying.
    (r"providers?\b", "provider"),
    (r"practitioners?\b", "provider"),
    (r"freelancers?\b", "provider"),
    (r"agenc(?:y|ies)\b", "provider"),
    (r"clinics?\b", "provider"),
    (r"teachers?\b", "provider"),
    (r"instructors?\b", "provider"),
    # Every consumer noun carries `(?!-)`: used attributively it is a MODIFIER, not the buyer.
    # "University Student-Union Venue Coordinators" is a venue job, not a student, and read as a
    # consumer it flipped a real corpus segment onto the wrong side of the counter.
    (r"learners?\b(?!-)", "consumer"),
    (r"students?\b(?!-)", "consumer"),
    (r"pupils?\b(?!-)", "consumer"),
    (r"parents?\b(?!-)", "consumer"),
    (r"patients?\b(?!-)", "consumer"),
    (r"tenants?\b(?!-)", "consumer"),
    (r"homeowners?\b(?!-)", "consumer"),
    (r"attendees?\b(?!-)", "consumer"),
    (r"shoppers?\b(?!-)", "consumer"),
    (r"guests?\b(?!-)", "consumer"),
    # "Direct-to-consumer" names a SALES CHANNEL the provider uses. Read as a buyer it turned
    # "Micro-Roasters Selling Direct-to-Consumer Online" into a consumer audience.
    (r"(?<!to-)(?<!to\s)consumers?\b(?!-)", "consumer"),
    (r"subscribers?\b(?!-)", "consumer"),
)

# A consumer word is only evidence about the BUYER when the buyer is the one being named.
# "private tutors helping students" and "property managers serving tenants" name the party the
# buyer SERVES, not the buyer — and both used to read as a consumer audience, which is the
# opposite of what the phrase says. A serving verb or a possessive is the grammatical marker of
# that construction, so when either is present the consumer reading is dropped rather than
# trusted. Dropping leaves either the provider reading or silence, both of which are honest.
_SERVED_PARTY_CONTEXT = re.compile(
    r"(?<!\w)(?:"
    r"help(?:s|ing|ed)?|serv(?:e|es|ing|ed|icing)|teach(?:es|ing)?|taught|"
    r"treat(?:s|ing|ed)?|tutor(?:s|ing|ed)?|coach(?:es|ing|ed)?|train(?:s|ing|ed)?|"
    r"support(?:s|ing|ed)?|advis(?:e|es|ing|ed)|guid(?:e|es|ing|ed)|"
    r"their|its|his|her|our|your|whose"
    r")\b|[’']s\b|s[’']\B",
    re.IGNORECASE,
)

_AUTHORITY_MARKERS: tuple[tuple[str, str], ...] = (
    (r"owner[-\s]?operators?", "owner"),
    (r"owner[-\s]?operated", "owner"),
    (r"owners?\b", "owner"),
    (r"proprietors?\b", "owner"),
    (r"principals?\b", "owner"),
    (r"partners?\b", "owner"),
    (r"self[-\s]?employed", "owner"),
    (r"staff\b", "staff"),
    (r"technicians?\b", "staff"),
    (r"techs\b", "staff"),
    (r"assistants?\b", "staff"),
    (r"receptionists?\b", "staff"),
    (r"nurses?\b", "staff"),
    (r"employees?\b", "staff"),
    (r"clerks?\b", "staff"),
    (r"associates?\b", "staff"),
    (r"coordinators?\b", "staff"),
    (r"front[-\s]desk", "staff"),
)

# Site-ish nouns: the things a business can have one or many of. Plurals are spelled out
# rather than suffixed, because "branches" and "facilities" are not "branchs"/"facilitys" --
# a suffix shortcut here silently stopped the scale axis from reading half its own vocabulary.
_SITE_WORDS: tuple[tuple[str, str], ...] = (
    ("site", "sites"), ("location", "locations"), ("branch", "branches"),
    ("clinic", "clinics"), ("office", "offices"), ("store", "stores"),
    ("shop", "shops"), ("practice", "practices"), ("outlet", "outlets"),
    ("unit", "units"), ("facility", "facilities"), ("hospital", "hospitals"),
)
_SITE_SINGULAR = f"(?:{'|'.join(singular for singular, _ in _SITE_WORDS)})"
_SITE_PLURAL = f"(?:{'|'.join(plural for _, plural in _SITE_WORDS)})"
# Plural first: the alternation is ordered, so "branches" must not be read as "branch" + "es".
_SITE_ANY = f"(?:{_SITE_PLURAL}|{_SITE_SINGULAR})"

# "Chain" only means "one business, many sites" when a site is actually in the phrase. Bare
# `chains?` read *supply chain*, *cold chain*, *value chain* and *chain of custody* as a
# multi-site corporate operator — and chain-of-custody is stock vocabulary in the veterinary
# controlled-substance niche this detector was built for. Three real corpus segments were
# misread that way, so the site context is required rather than assumed.
_CHAIN_ADJACENT = "(?:retail|restaurant|pharmacy|salon|gym|grocery|franchise|hotel)"
_CHAIN_OF_SITES = (
    f"(?:"
    f"(?:{_SITE_ANY}|{_CHAIN_ADJACENT})\\s+chains?\\b"
    f"|chains?\\s+of\\s+{_SITE_PLURAL}\\b"
    f"|chain\\s+{_SITE_PLURAL}\\b"
    f")"
)

_SCALE_MARKERS: tuple[tuple[str, str], ...] = (
    (rf"single[-\s]?{_SITE_ANY}\b", "single"),
    (rf"one[-\s]{_SITE_SINGULAR}\b", "single"),
    (rf"sole[-\s]{_SITE_SINGULAR}\b", "single"),
    (r"one[-\s]person\b", "single"),
    (r"solo\b", "single"),
    (rf"multi[-\s]?{_SITE_ANY}\b", "multi"),
    (rf"multiple\s+{_SITE_PLURAL}\b", "multi"),
    (rf"several\s+{_SITE_PLURAL}\b", "multi"),
    (rf"many\s+{_SITE_PLURAL}\b", "multi"),
    (rf"across\s+(?:several|multiple|many|its|their)\s+{_SITE_PLURAL}\b", "multi"),
    (_CHAIN_OF_SITES, "multi"),
    (r"group\s+practices?\b", "multi"),
    (rf"networks?\s+of\s+{_SITE_PLURAL}\b", "multi"),
)

_INDEPENDENCE_MARKERS: tuple[tuple[str, str], ...] = (
    (r"independent(?:ly)?\b", "independent"),
    (r"owner[-\s]?operated", "independent"),
    (r"family[-\s]?owned", "independent"),
    (r"corporate\b", "corporate"),
    (r"corporate[-\s]?owned", "corporate"),
    (r"enterprises?\b", "corporate"),
    (r"private[-\s]equity", "corporate"),
    (r"pe[-\s]backed", "corporate"),
    (r"franchis(?:e|ed|es|ees?|ors?)\b", "corporate"),
    (_CHAIN_OF_SITES, "corporate"),
)

_SPECIALIZATION_MARKERS: tuple[tuple[str, str], ...] = (
    (r"general\s+practices?", "general"),
    (r"general\s+practitioners?", "general"),
    (r"generalists?\b", "general"),
    (r"primary\s+care", "general"),
    (r"family\s+practices?", "general"),
    (r"specialt(?:y|ies)\b", "specialty"),
    (r"specialists?\b", "specialty"),
    (r"specialis[ez]ed\b", "specialty"),
    # "Emergency" is a kind of PRACTICE only next to a practice word. On its own it is the
    # ordinary trade sense — "emergency callouts", "emergency repairs" — which says nothing
    # about whether the business is a generalist or a specialist.
    (
        rf"emergency\s+(?:{_SITE_ANY}|care|medicine|department|departments|room|rooms"
        r"|vet|vets|veterinary|animal|surgeries|surgery|centers?|centres?)\b",
        "specialty",
    ),
    (r"referral\b", "specialty"),
    (r"sub[-\s]?specialt", "specialty"),
    (r"teaching\s+hospitals?", "specialty"),
)


def _compile(markers: tuple[tuple[str, str], ...]) -> tuple[tuple[re.Pattern[str], str], ...]:
    return tuple((re.compile(rf"(?<!\w){pattern}", re.IGNORECASE), value) for pattern, value in markers)


_COMPILED: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
    "party": _compile(_PARTY_MARKERS),
    "authority": _compile(_AUTHORITY_MARKERS),
    "scale": _compile(_SCALE_MARKERS),
    "independence": _compile(_INDEPENDENCE_MARKERS),
    "specialization": _compile(_SPECIALIZATION_MARKERS),
}

# Units the numeric interval parser is allowed to speak for. "5-20 locations" is a site count;
# "5-20 dollars" and "10-20 hours" are not, and must not reach the scale axis. Built by running
# the parser's OWN stemmer over the vocabulary, so the two never drift apart.
_COUNTABLE_SITE_UNITS = {
    _normalized_unit(word)
    for pair in _SITE_WORDS
    for word in pair
}


def _numeric_scale(text: str) -> Optional[str]:
    """Read an explicit site COUNT as a scale value, or ``None`` when it is not unambiguous."""
    site_scales = [scale for scale in _parse_scales(text) if scale.unit in _COUNTABLE_SITE_UNITS]
    if len(site_scales) != 1:
        return None
    scale = site_scales[0]
    if scale.maximum is not None and scale.maximum <= Decimal(1):
        return "single"
    if scale.minimum is not None and scale.minimum >= Decimal(2):
        return "multi"
    return None


def _without_headcounts(text: str) -> str:
    """Blank out "5-20 technicians"-shaped spans before reading roles out of a phrase.

    "Independent appliance repair companies with 5-20 technicians" states a SIZE, not that the
    buyer is a technician. Left in, that headcount reads as staff authority and would collide
    with an owner-worded segment to raise a drift notice about a difference nobody stated.
    """
    return _SCALE_PATTERN.sub(" ", text)


def _axis_value(axis: str, text: str) -> Optional[str]:
    """The one value this phrase states on ``axis``, or ``None`` when it does not state one.

    Two different values matched on the same axis means the phrase is talking about a mixed
    or compound buyer; that is not a reading we are willing to compare, so it is unknown.
    """
    searchable = text if axis == "scale" else _without_headcounts(text)
    values = {value for pattern, value in _COMPILED[axis] if pattern.search(searchable)}
    if axis == "party" and "consumer" in values and _SERVED_PARTY_CONTEXT.search(searchable):
        values.discard("consumer")
    if axis == "scale":
        numeric = _numeric_scale(text)
        if numeric is not None:
            values.add(numeric)
    return values.pop() if len(values) == 1 else None


@dataclass(frozen=True)
class AudienceAxes:
    """The typed reading of one audience phrase. ``None`` on an axis means 'does not say'."""

    party: Optional[str] = None
    authority: Optional[str] = None
    scale: Optional[str] = None
    independence: Optional[str] = None
    specialization: Optional[str] = None

    def value(self, axis: str) -> Optional[str]:
        return getattr(self, axis)


def read_audience_axes(value: Optional[str]) -> AudienceAxes:
    """Extract every axis this phrase states. Unreadable phrases read as all-unknown."""
    text = (value or "").strip()
    if not text:
        return AudienceAxes()
    return AudienceAxes(**{axis: _axis_value(axis, text) for axis in AXIS_LABELS})


def conflicting_axes(left: Optional[str], right: Optional[str]) -> tuple[str, ...]:
    """Axes on which both phrases state a value AND the values differ.

    Empty means no PROVEN difference: either the phrases agree everywhere they both speak, or
    they never both speak. The caller cannot tell those apart on purpose -- neither is grounds
    for warning a reader.
    """
    left_axes = read_audience_axes(left)
    right_axes = read_audience_axes(right)
    return tuple(
        axis for axis in AXIS_LABELS
        if left_axes.value(axis) is not None
        and right_axes.value(axis) is not None
        and left_axes.value(axis) != right_axes.value(axis)
    )


def _join_labels(axes: tuple[str, ...]) -> str:
    labels = [AXIS_LABELS[axis] for axis in axes]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


# Which two of the three phrases disagreed, in the order the message introduces them. Naming the
# pair is not a stylistic nicety: a run can disagree with the request on operating scale while the
# RECOMMENDATION agrees with the request on exactly that axis. The old single sentence ("they are
# different buyers on operating scale") pointed the reader at the recommendation in precisely that
# case, which is the one place the recommendation was not the problem.
_PAIR_SENTENCES: tuple[tuple[str, str], ...] = (
    ("requested_vs_primary",
     "This run's research settled on a different {axes} than you asked for."),
    ("requested_vs_source",
     "The recommendation is built for a different {axes} than you asked for."),
    ("primary_vs_source",
     "The recommendation is built for a different {axes} than the research settled on."),
)


# The Reality Check's `key_challenges` list carries a POINTER to the notice, never the notice.
#
# `backend/src/routes/schemas/sharedDiscoveryPayload.ts` classifies `audience_drift_notice` as
# `pool` (it describes the RECOMMENDATION) and `key_challenges` as `niche`. On a stale-pool
# public share `applyPreviewFieldAllowlist` therefore drops both labelled copies of the notice
# and still serves everything in `key_challenges` — so putting the full message there published
# the recommended source segment names verbatim on the exact path that had just withheld them.
#
# This sentence states THAT the buyer moved without naming who moved to, so the niche-scoped
# field carries nothing pool-scoped. It is also deliberately pair-agnostic: the notice fires on
# any one of the three pairings, including the one where the recommendation agrees with the
# request and the research is what drifted. The full message stays on `audience_drift_notice`.
#
# One sentence, and no cross-reference to the note. `AudienceSnapshot.svelte` renders that note
# only `{#if data.audience_drift_notice}`, so on the very path this string exists for — the one
# that withheld both labelled copies — a "see the audience note" pointed at a block that never
# renders. The boundary classifies and never rewrites, so there is no per-path wording to author.
AUDIENCE_DRIFT_CHALLENGE = (
    "What you asked for, what the research settled on, and what the recommendation is built "
    "for are not all the same buyer."
)


def _axis_sentences(conflicts: dict[str, list[str]]) -> str:
    return " ".join(
        template.format(axes=_join_labels(
            tuple(axis for axis in AXIS_LABELS if axis in conflicts[pair])
        ))
        for pair, template in _PAIR_SENTENCES
        if conflicts.get(pair)
    )


def _source_segment(candidate) -> str:
    if isinstance(candidate, str):
        return candidate.strip()
    if isinstance(candidate, dict):
        return str(candidate.get("source_segment") or "").strip()
    return str(getattr(candidate, "source_segment", None) or "").strip()


def detect_audience_drift(
    requested_audience: Optional[str],
    research_primary_segment: Optional[str],
    recommended_candidates,
) -> Optional[AudienceDriftNotice]:
    """Compare requested -> researched -> RECOMMENDED buyer identity on typed axes.

    ``recommended_candidates`` is recommendation-scoped by contract: the selected solution and
    the explicitly recorded runners-up, never the whole candidate pool. Passing the pool would
    make the notice fire on ideas the reader was never offered.

    Fires when any one of the three pairings states DIFFERENT values on the same axis. One
    proven axis disagreement is a buyer change; wording differences are not, and cannot reach
    this function's output because wording is never compared.
    """
    requested = (requested_audience or "").strip()
    primary = (research_primary_segment or "").strip()
    sources = list(dict.fromkeys(
        source for source in (_source_segment(item) for item in (recommended_candidates or []))
        if source
    ))
    if not requested or not primary or not sources:
        return None

    conflicts: dict[str, list[str]] = {pair: [] for pair, _ in _PAIR_SENTENCES}
    for pair, pairings in (
        ("requested_vs_primary", ((requested, primary),)),
        ("requested_vs_source", tuple((requested, source) for source in sources)),
        ("primary_vs_source", tuple((primary, source) for source in sources)),
    ):
        for left, right in pairings:
            for axis in conflicting_axes(left, right):
                if axis not in conflicts[pair]:
                    conflicts[pair].append(axis)
    if not any(conflicts.values()):
        return None

    recommended = "; ".join(sources)
    message = (
        f"You asked to reach “{requested}”. This run's research settled on “{primary}”, and "
        f"the recommendation is built for “{recommended}”. {_axis_sentences(conflicts)} "
        "Confirm that buyer change before you fund or build the recommendation."
    )
    return AudienceDriftNotice(
        requested_audience=requested,
        dossier_primary_segment=primary,
        recommended_source_segments=sources,
        message=message,
    )
