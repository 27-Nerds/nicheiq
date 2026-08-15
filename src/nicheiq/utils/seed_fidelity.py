"""Deterministic identity guard for user-submitted product ideas."""

from __future__ import annotations

from collections.abc import Iterable
from math import ceil
from typing import Any

from loguru import logger

# EXACT_TERMS_TOKEN_CAP was removed on 2026-08-14 along with the exact-terms rule itself.
# See `is_seed_faithful`'s docstring for the measurements and why it must not come back:
# the cap was calibrated on survivorship (completed runs happened to be 17-25 tokens), and
# live 7703f811 failed at 23 tokens — under the cap — for dropping 'find', 'out', 'work'.

# THE WHOLE TEXT CORPUS A SEED GATE MAY READ. Two different kinds of field live in here and
# only one of them can serve as a post-birth CHANGE DETECTOR — see `_EVALUATION_FIELDS` below.
# Every consumer that wants TEXT (the axis tuples, the retention corpus, the replay capture)
# reads this tuple; the one consumer that asks "did a later pass change the product?"
# (`seed_identity_snapshot`) reads `_PRODUCT_IDENTITY_FIELDS`.
_IDENTITY_FIELDS = (
    "concept_name",
    "one_liner",
    "solution_name",
    "headline",
    "short_description",
    "description",
    "value_proposition",
    "core_features",
    "project_type",
    "delivery_format",
    "mechanism_tag",
    "why_it_works",
    "innovation_angle",
    "differentiation_factors",
    "technical_approach",
    "target_personas",
    "requires_data_aggregation",
    "market_fit_claimed_route",
    "data_route",
    "data_source_hint",
    "data_sources",
    "data_source",
    "data_source_tag",
    "data_access_model",
    "data_acquisition_notes",
)

# EVALUATION EVIDENCE, NOT PRODUCT IDENTITY (2026-08-15, S19 — live kill 8580c179).
#
# These three are CODE-POPULATED CONCLUSIONS ABOUT the product, not assertions OF it. A later
# pass rewriting one is the pipeline doing its job; a later pass rewriting `solution_name` is
# the defect the post-birth diff exists to catch. Snapshotting a field the pipeline is
# DESIGNED to overwrite makes the lock fire on its own machinery, and because
# `changed_seed_identity_fields` flags blank-FILLS and blank-CLEARS too, it fires in both
# directions and there is no value a candidate can hold that survives.
#
# WHAT IT COST: job 8580c179-5fcb-441f-8fee-5e14fd0eaf43, a completed ~40-minute paid
# "Check my idea" run on a 268-char pitch. The birth judge ACCEPTED it
# (`output/checkpoints/seed_identity_trace_8580c179-…json`, records [0]-[2]); the post-birth
# diff then refused it with `fields=['market_fit_claimed_route']`, telling the user their idea
# had changed when nothing about their product had. That trace is the first birth capture this
# program ever produced and it is now the regression fixture
# (`tests/fixtures/seed_identity_trace_8580c179.json`).
#
# MEASURED, not argued — `_finalize_idea_pool` (the FIRST post-birth wave step, deterministic,
# no LLM on these paths) driven on that candidate rebuilt as a real `SolutionIdea`:
#   * `market_fit_claimed_route`: 'Public community discussions (Reddit/HN/forums, public)'
#     -> None, by the Q-030/Q-035 guarded reset in `UnifiedSolutionCrew._finalize_idea_pool`
#     — the branch that clears the field when no `*_score_raw` is stamped. NAMED, not cited by
#     line: three sites carried `unified_solution_crew.py:10453-10456`, which is the
#     `_keep_validate_marker` tuple a dozen lines earlier, and line ranges in that file drift
#     every round. Its own model
#     contract says it outright: "Data route the independent calibration critic cited as
#     market-fit support … Code-populated; never trusted from generator output." It moves on
#     5 of the 22 corpus candidates too, always to None.
#   * `data_access_model`: 'licensed' -> 'paywalled' (closed-vocab alias) and
#     'partner feed, negotiated' -> None (prose, rejected by the vocab screen). It is the
#     ROUTE VERIFIER'S VERDICT about obtainability — `_score_wave`'s own ordering comment says
#     `verify_data_routes` "always overwrites" it.
#   * `data_acquisition_notes`: rewritten in the same branch to "Data route: partner feed,
#     negotiated | <original>", and replaced wholesale by the well-known-source upgrade. This
#     module ALREADY classified it — it is excluded from `_ROUTE_ASSERTION_FIELDS` because it
#     is "a DISCLOSURE", after honest cost/ToS prose in it killed an earlier live run.
#
# WHAT STAYS LOCKED AND WHY THE LINE IS NOT "the pipeline touches it". `project_type` and
# `delivery_format` are ALSO normalized by that same pass — and they stay locked, because
# birth runs `_canonicalize_project_type` and the `infer_delivery_format` stamp BEFORE taking
# the snapshot, so the later normalization is idempotent and moves nothing. (Measured: on the
# corpus, whose candidates predate that stamp, `delivery_format` moves None -> inferred on 20
# of 22; on the live trace, where birth stamped it, it does not move at all. Do not read the
# corpus number as a production defect — trap 1.) The line is OWNERSHIP: who authors the
# value. A normalization of the generator's own product copy is lockable once birth
# pre-applies it; a verdict the pipeline mints about the product is not lockable at all.
#
# `data_sources` is deliberately NOT here. It is generator-authored product copy — WHICH
# external sources the product uses is part of what the product is, and it is the primary
# route-value carrier the whole unpitched-route gate is built on. The one post-birth pass that
# touches it (`_relocate_needs_verify_flags`) only strips `[NEEDS-VERIFY: …]` items its own
# model contract already bans from that field. Residual, stated rather than hidden: if that
# sanitiser ever fires on a seed it will refuse the run.
_EVALUATION_FIELDS = (
    "market_fit_claimed_route",
    "data_access_model",
    "data_acquisition_notes",
)

# DERIVED, so the default for a new field is FAIL-CLOSED (trap 16: a list that fails closed
# when it is incomplete is fine; one that fails open is what this ledger is made of). Add a
# field to `_IDENTITY_FIELDS` and it is watched by the post-birth lock until someone states,
# here, that it is a conclusion rather than a product axis. Wrong-way failure is a refused
# run, which is recoverable; the other way is grading a product the user never submitted.
_PRODUCT_IDENTITY_FIELDS = tuple(
    field for field in _IDENTITY_FIELDS if field not in _EVALUATION_FIELDS
)

_AXIS_IDENTITY_FIELDS = {
    "buyer": _IDENTITY_FIELDS,
    "job": _IDENTITY_FIELDS,
    "mechanism": _IDENTITY_FIELDS + (
        "data_sources",
        "data_source",
        "data_source_tag",
        "data_access_model",
        "data_acquisition_notes",
    ),
    # CHANNEL reads product-identity copy ONLY (2026-08-14). It used to append six SEO/CAC
    # fields, every one of which is (a) absent from `_IDENTITY_FIELDS`, so the post-birth
    # snapshot does NOT lock it, and (b) written by the pipeline AFTER birth —
    # `_repair_blank_idea_fields` fills `programmatic_seo_opportunity`,
    # `content_generation_model`, `organic_discovery_queries` and both `estimated_cac_*`.
    # So the delivery clause was being judged against prose the PIPELINE authored, not the
    # user's pitch: a repudiation cue ("without", "rather than") in generated SEO copy near a
    # delivery term could newly fail `seed_clause_drift` at the post-tail check and discard a
    # clean, fully-paid run. A user's stated delivery ("a simple web app") is already carried by
    # `delivery_format`, `description`, `short_description` and `value_proposition` inside
    # `_IDENTITY_FIELDS`, so the real signal is retained.
    # `distribution_channel` additionally does not exist on `BaseSolutionIdea` at all — it was
    # inert, like the RawConcept-only names in `_IDENTITY_FIELDS`.
    "channel": _IDENTITY_FIELDS,
    "scope": _IDENTITY_FIELDS,
    "business_model": _IDENTITY_FIELDS + ("pricing_strategy", "tags"),
}

# A user-seed may gain implementation detail, but a new external source must not
# become the product's required route or differentiator. Keep route fields separate
# from the broad identity corpus: otherwise repeating the original pitch anywhere
# lets an additive replacement mechanism pass with 100% token coverage.
_ROUTE_FIELDS = (
    "market_fit_claimed_route",
    "data_route",
    "data_source_hint",
    "data_sources",
    "data_source",
    "data_source_tag",
)

# `differentiation_locus` STAYS HERE — removal was attempted and MEASURED as a regression
# (2026-08-15, S11). The proposal was that a field the pipeline re-derives after birth cannot
# honestly mint a route assertion. The premise is right and the conclusion is not, because this
# tuple has a SECOND consumer that the minting argument does not reach: `promoted_core =
# bool(core_contexts)` in `unpitched_core_dependencies` reads `_CORE_PROMISE_FIELDS` alone (not
# the merged core+support list) to answer "has this already-declared external source been
# promoted into the product's differentiation?" — and `differentiation_locus` is by its model
# contract the field that names WHERE the differentiation lives, so it is the most on-point
# member of the tuple for that exact question.
#
# THE MEASUREMENTS, so this is not re-argued from first principles:
#   * As a MINTING source it is inert: over 608 unique `differentiation_locus` values in every
#     captured artifact in the repo, ONE mints a required-external-route assertion, and that one
#     is a `source_frame == "pain"` demoted candidate this user_seed-only subsystem never sees.
#     On the 20 real `user_seed` candidates carrying the field it is 0. So dropping it from
#     `_ROUTE_ASSERTION_FIELDS` alone changes nothing — 0 verdict flips over 658 real candidates
#     x 2 seed settings, and 0 over all 22 corpus cases.
#   * As a PROMOTION signal it is load-bearing: dropping it from this tuple flips 19 real
#     candidates LOOSER and 1 TIGHTER, two of them on the `user_seed` population. The sharpest
#     is a real user_seed candidate whose locus reads "The cross-referenced index of clinical
#     trial cohorts and public health datasets mapped to specific GLP-1 regain timelines" with
#     `NHANES public datasets` declared in `data_sources`: HEAD flags it, the removal does not.
#     That is precisely the class this gate exists to catch.
# Net: the only removal that closes the S11 field-set gap is the one that opens a hole. The gap
# is documented at the two `changed_seed_identity_fields` call sites that carry the S19 comment
# block — `UnifiedSolutionCrew.execute_seed_pipeline`'s post-WAVE diff and
# `ResearchFlow._inject_validate_seed`'s pre-injection diff (the third call site, the post-TAIL
# diff in the same crew method, defers to the first) — and pinned by MEASUREMENT in
# `tests/unit/utils/test_seed_identity_corpus.py`.
_CORE_PROMISE_FIELDS = (
    "concept_name",
    "one_liner",
    "solution_name",
    "headline",
    "short_description",
    "value_proposition",
    "description",
    "why_it_works",
    "innovation_angle",
    "differentiation_factors",
    "differentiation_locus",
    "core_features",
    "mechanism_tag",
    "project_type",
    "delivery_format",
    "target_personas",
)

_FIRST_PARTY_ROUTE_CUES = (
    "user-provided",
    "user supplied",
    "customer-provided",
    "customer supplied",
    "clinic-provided",
    "clinic supplied",
    "first-party",
    "uploaded by",
    "user uploaded",
    "customer uploaded",
    "clinic uploaded",
    "uploaded clinic",
    "user uploads",
    "customer uploads",
    "clinic uploads",
    "own data",
)

_EXTERNAL_ROUTE_CUES = (
    "external",
    "third-party",
    "third party",
    " api",
    "api ",
    "feed",
    "directory",
    "registry",
    "database",
    "credential",
    "token",
    "api key",
)

_REQUIRED_ROUTE_CUES = (
    "not optional",
    "require",
    "requires",
    "requiring",
    "required",
    "must",
    "depends on",
    "dependent on",
    "relies on",
    "needs",
    "cannot work without",
    "cannot operate without",
    "essential",
    "indispensable",
    "primary",
    "differentiator",
)

_OPTIONAL_ROUTE_CUES = (
    "optional",
    "supporting",
    "not required",
    "does not require",
    "do not require",
    "not require",
    "without requiring",
    "works without",
    "can work without",
    "may annotate",
    "can enrich",
    "must not depend",
    "must not use",
    "does not depend",
    "cannot depend",
    "need not",
    "not primary",
    "not the primary",
)

_SUPPORTING_ROUTE_FIELDS = (
    "technical_approach",
    "data_acquisition_notes",
)

# Fields a REQUIRED-route assertion may be minted FROM (see
# `_required_external_route_assertions`). Deliberately excludes
# `data_acquisition_notes`: by its model contract that field is a DISCLOSURE — "access
# model + rough cost; for 'unofficial'/'paywalled' name the tool + the ToS/cost risk" —
# so honest cost/ToS prose there ("… requires paid OpenAI and Anthropic API access, …
# api pricing, rate limits, and terms must be monitored") was being read as the product
# PROMISING a new core dependency, and killed a live "Check my idea" run at the birth
# identity lock. Matches this module's own contract: "a source mentioned only in
# data/technical fields … is not product identity". The field stays in
# `_SUPPORTING_ROUTE_FIELDS` so it can still say whether an ALREADY-declared route is
# required or optional — it just cannot invent one.
_ROUTE_ASSERTION_FIELDS = (*_CORE_PROMISE_FIELDS, "technical_approach")

_ROUTE_ACCESS_WORDS = (
    "api credential credentials customer external key provided supplied third party "
    "token uploaded user clinic"
)


def content_tokens(text: str) -> set[str]:
    """Distinctive stemmed tokens of `text` (public: report layer + crew share it)."""
    from .text_stemmer import stem_tokens
    from .validation.dedup import STOPWORDS, normalize_text

    return stem_tokens({
        token
        for token in normalize_text(text or "").split()
        if len(token) > 2 and token not in STOPWORDS
    })


_content_tokens = content_tokens


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(f"{_flatten(k)} {_flatten(v)}" for k, v in value.items())
    if isinstance(value, Iterable):
        return " ".join(_flatten(item) for item in value)
    return str(value)


def capture_gate_input(candidate: Any) -> dict:
    """The candidate fields a seed-identity gate actually reads, for the offline replay corpus.

    WHY: the gates run on the candidate AS IT EXISTS AT EACH GATE, but what the pipeline persists
    is the FINAL merged artifact — after the worker's post-merge save and the pool contract have
    written route fields. Feeding the persisted artifact back through the gates therefore measures
    a shape production never evaluates (`tests/unit/utils/test_seed_identity_corpus.py` records
    that trap in detail). Without capture, every honest pair in the corpus is unassertable and the
    gates can only be tuned by shipping a change and waiting for a user to complain — which is how
    all four production false positives were found.

    Deliberately cheap: a plain field read, no LLM, no I/O. Values are truncated only in the
    RENDERING layer, never here — token-overlap verdicts depend on the full text, so a trimmed
    capture would replay differently from the run it came from.

    THE UNION IS DERIVED FROM THE GATES, NOT LISTED (2026-08-15, S11). It used to be
    `_IDENTITY_FIELDS + _ROUTE_FIELDS + _SUPPORTING_ROUTE_FIELDS`, which omitted
    `differentiation_locus` — the one field `unpitched_core_dependencies` reads that is in
    none of those three. MEASURED, not argued: a candidate whose `differentiation_locus`
    carries the route's REQUIRED role ("… requires the external Acme Compliance Registry feed
    as its primary source", with `Acme Compliance Registry` in `data_sources`) flagged
    `['Acme Compliance Registry']` live and `[]` on replay — the capture was LOSSY on exactly
    the field S11 is about, so a refusal it caused could not be reproduced from the trace, and
    `TestCaptureIsFaithfulEnoughToReplay` could not see it because no case carried one.
    Adding `_ROUTE_ASSERTION_FIELDS` closes it by DERIVATION rather than by naming the field:
    the measured read set of `unpitched_core_dependencies` is
    `_ROUTE_FIELDS | _ROUTE_ASSERTION_FIELDS | _CORE_PROMISE_FIELDS | _SUPPORTING_ROUTE_FIELDS
    | {requires_data_aggregation}`, and `_CORE_PROMISE_FIELDS` is a subset of
    `_ROUTE_ASSERTION_FIELDS` while `requires_data_aggregation` is in `_IDENTITY_FIELDS`, so
    this union is complete by construction and stays complete when those tuples change.
    """
    fields = dict.fromkeys((
        *_IDENTITY_FIELDS, *_ROUTE_FIELDS, *_SUPPORTING_ROUTE_FIELDS,
        *_ROUTE_ASSERTION_FIELDS,
    ))
    return {f: getattr(candidate, f, None) for f in fields
            if getattr(candidate, f, None) not in (None, "", [], {})}


def seed_identity_snapshot(candidate: Any) -> dict[str, str]:
    """Identity fields that later evaluators may not rewrite or newly populate.

    Scoring and red-team passes may add evidence and scores, but every product-copy
    field (including a blank one) is fixed once Check-my-idea birth completes.

    READS `_PRODUCT_IDENTITY_FIELDS`, NOT `_IDENTITY_FIELDS` (2026-08-15, S19). The three
    fields in `_EVALUATION_FIELDS` are conclusions the pipeline writes ABOUT the product by
    design, so a diff over them measures our own machinery rather than the user's idea — it
    destroyed a completed paid run (job 8580c179) doing exactly that. The reasons, per field
    and measured by driving the writer, are at `_EVALUATION_FIELDS`.

    THIS IS THE ONLY CONSUMER THAT NARROWS. Every other reader of `_IDENTITY_FIELDS` wants the
    field set as TEXT rather than as a change detector, and narrowing them would TIGHTEN the
    gates rather than loosen them: `_AXIS_IDENTITY_FIELDS` (via `seed_clause_drift`) and
    `_candidate_identity_text` (via the retention floor) count how much of the pitch survives
    SOMEWHERE in the candidate, so removing places to look can only lose retained terms;
    `structured_synthesis_fidelity_failures` is the same shape on the exact-synthesis path;
    and `capture_gate_input` is a replay union that must stay complete or the corpus replays
    a shape production never evaluated. All four were checked and all four still read the
    full tuple.
    """
    return {
        field: " ".join(_flatten(getattr(candidate, field, None)).lower().split())
        for field in _PRODUCT_IDENTITY_FIELDS
    }


def changed_seed_identity_fields(snapshot: dict[str, str], candidate: Any) -> list[str]:
    """Identity fields whose established non-empty value was rewritten."""
    return [
        field
        for field, original in snapshot.items()
        if " ".join(_flatten(getattr(candidate, field, None)).lower().split()) != original
    ]


_PROVENANCE_ECHO_CUES = (
    "original brief",
    "original research brief",
    "submitted pitch",
    "submitted product",
    "user brief",
    "user's brief",
)


def _is_provenance_echo(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    return any(cue in normalized for cue in _PROVENANCE_ECHO_CUES)


def _candidate_identity_text(candidate: Any) -> str:
    """Product assertions only, excluding inert copies of the submitted brief."""
    import re

    assertions: list[str] = []
    for field in _IDENTITY_FIELDS:
        text = _flatten(getattr(candidate, field, None))
        assertions.extend(
            segment
            for segment in re.split(r"[.!?;\n]+", text)
            if segment.strip()
            and not _is_provenance_echo(segment)
        )
    return " ".join(assertions)


def _route_values(candidate: Any) -> list[str]:
    values: list[str] = []
    for field in _ROUTE_FIELDS:
        value = getattr(candidate, field, None)
        items = value if isinstance(value, (list, tuple, set)) else [value]
        for item in items:
            text = _flatten(item).strip()
            if text and text not in values:
                values.append(text)
    return values


def _is_first_party_route(route: str) -> bool:
    import re

    normalized = " ".join(
        (route or "").lower().replace("_", " ").replace("-", " ").split()
    )
    padded = f" {normalized} "
    normalized_external_cues = (
        " ".join(cue.replace("-", " ").split()) for cue in _EXTERNAL_ROUTE_CUES
    )
    if any(f" {cue} " in padded for cue in normalized_external_cues):
        return False
    if re.search(r"\bupload(?:ed|s|ing)?\b", normalized) and re.search(
        r"\b(?:csv|file|spreadsheet|document|record|dataset|export)\b",
        normalized,
    ):
        return True
    return any(
        " ".join(cue.replace("-", " ").split()) in normalized
        for cue in _FIRST_PARTY_ROUTE_CUES
    )


def _normalize_route_language(text: str) -> str:
    """Normalize contractions before classifying a route's required role."""
    import re

    normalized = re.sub(r"[’ʼ`´]", "'", text or "")
    replacements = {
        r"\bisn['’]t\b": "is not",
        r"\baren['’]t\b": "are not",
        r"\bwasn['’]t\b": "was not",
        r"\bweren['’]t\b": "were not",
        r"\bdoesn['’]t\b": "does not",
        r"\bdon['’]t\b": "do not",
        r"\bdidn['’]t\b": "did not",
        r"\bwon['’]t\b": "will not",
        r"\bwouldn['’]t\b": "would not",
        r"\bshouldn['’]t\b": "should not",
        r"\bcouldn['’]t\b": "could not",
        r"\bcan['’]t\b": "cannot",
        r"\bmustn['’]t\b": "must not",
        r"\bneedn['’]t\b": "need not",
        r"\bain['’]t\b": "is not",
        r"\bisnt\b": "is not",
        r"\barent\b": "are not",
        r"\bdoesnt\b": "does not",
        r"\bdont\b": "do not",
        r"\bdidnt\b": "did not",
        r"\bwont\b": "will not",
        r"\bwouldnt\b": "would not",
        r"\bshouldnt\b": "should not",
        r"\bcouldnt\b": "could not",
        r"\bcant\b": "cannot",
        r"\bmustnt\b": "must not",
        r"\bneednt\b": "need not",
    }
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return " ".join(normalized.lower().split())


def _route_role_contexts(
    candidate: Any,
    route_terms: set[str],
    fields: tuple[str, ...],
) -> list[str]:
    """Return only clauses that mention this route's distinctive terms."""
    import re

    threshold = 1 if len(route_terms) == 1 else min(2, len(route_terms))
    all_route_terms = set().union(*(
        content_tokens(route) - content_tokens(_ROUTE_ACCESS_WORDS)
        for route in _route_values(candidate)
    ))
    contexts: list[str] = []
    for field in fields:
        text = _flatten(getattr(candidate, field, None))
        clauses = re.split(r"[.!?;\n]+", text)
        for index, clause in enumerate(clauses):
            major_units: list[str] = []
            for major_unit in re.split(
                r"\s*(?:,\s*\band\b|,?\s*(?:\bwhile\b|\bwhereas\b|"
                r"(?<!anything )\bbut\b|\byet\b|\bthough\b|\bor\b))\s*",
                clause,
                flags=re.IGNORECASE,
            ):
                first_and = re.search(r"\band\b", major_unit, flags=re.IGNORECASE)
                leading = major_unit[:first_and.start()] if first_and else ""
                normalized_leading = _normalize_route_language(leading)
                leading_has_role = bool(normalized_leading) and (
                    _requires_route(normalized_leading)
                    or any(
                        _contains_role_cue(normalized_leading, cue)
                        for cue in _OPTIONAL_ROUTE_CUES
                    )
                )
                if first_and and leading_has_role:
                    major_units.extend([
                        leading,
                        major_unit[first_and.end():],
                    ])
                else:
                    major_units.append(major_unit)
            matched_clause = False
            for major_index, major_unit in enumerate(major_units):
                if len(route_terms & content_tokens(major_unit)) < threshold:
                    continue
                matched_clause = True
                normalized_major = _normalize_route_language(major_unit)
                grouped_role = re.search(r"\b(?:both|all)\b", normalized_major) and (
                    _requires_route(normalized_major)
                    or any(
                        _contains_role_cue(normalized_major, cue)
                        for cue in _OPTIONAL_ROUTE_CUES
                    )
                )
                if grouped_role:
                    contexts.append(normalized_major)
                    continue
                role_units = re.split(
                    r"\s*(?:,|\band\b|\bwith\b)\s*",
                    major_unit,
                    flags=re.IGNORECASE,
                )
                matching_indexes = [
                    unit_index
                    for unit_index, unit in enumerate(role_units)
                    if len(route_terms & content_tokens(unit)) >= threshold
                ]
                for unit_index in matching_indexes:
                    attached = [role_units[unit_index]]
                    for continuation in role_units[unit_index + 1:]:
                        continuation_tokens = content_tokens(continuation)
                        if continuation_tokens & all_route_terms:
                            break
                        attached.append(continuation)
                    contexts.append(_normalize_route_language(" ".join(attached)))
                for continuation_major in major_units[major_index + 1:]:
                    continuation_tokens = content_tokens(continuation_major)
                    if continuation_tokens & all_route_terms:
                        break
                    normalized_continuation = _normalize_route_language(continuation_major)
                    if _requires_route(normalized_continuation) or any(
                        _contains_role_cue(normalized_continuation, cue)
                        for cue in _OPTIONAL_ROUTE_CUES
                    ):
                        contexts.append(normalized_continuation)
            if matched_clause:
                for followup_clause in clauses[index + 1:index + 3]:
                    followup = _normalize_route_language(followup_clause)
                    followup_tokens = content_tokens(followup)
                    if (followup_tokens & all_route_terms) - route_terms:
                        break
                    if re.match(
                        r"^(?:it|this|that|the (?:source|feed|route|integration|dependency|api))\b",
                        followup,
                    ) or _requires_route(followup) or any(
                        _contains_role_cue(followup, cue) for cue in _OPTIONAL_ROUTE_CUES
                    ):
                        contexts.append(followup)
                    else:
                        break
    return contexts


def _alias_route_role_contexts(seed_text: str, alias_phrase: str) -> list[str]:
    """Return role text local to a route alias, not the whole mixed-route sentence."""
    import re

    alias_pattern = r"\b" + r"[^a-z0-9]+".join(
        re.escape(word) for word in alias_phrase.split()
    ) + r"\b"
    contexts: list[str] = []
    for clause in re.split(r"[.!?;\n]+", seed_text):
        major_units: list[str] = []
        for major_unit in re.split(
            r"\s*(?:,\s*\band\b|,?\s*(?:\bwhile\b|\bwhereas\b|"
            r"(?<!anything )\bbut\b|\byet\b|\bthough\b|\bor\b))\s*",
            clause,
            flags=re.IGNORECASE,
        ):
            first_and = re.search(r"\band\b", major_unit, flags=re.IGNORECASE)
            leading = major_unit[:first_and.start()] if first_and else ""
            normalized_leading = _normalize_route_language(leading)
            leading_has_role = bool(normalized_leading) and (
                _requires_route(normalized_leading)
                or any(
                    _contains_role_cue(normalized_leading, cue)
                    for cue in _OPTIONAL_ROUTE_CUES
                )
            )
            if first_and and leading_has_role:
                major_units.extend([leading, major_unit[first_and.end():]])
            else:
                major_units.append(major_unit)

        for major_unit in major_units:
            normalized_major = _normalize_route_language(major_unit)
            if not re.search(alias_pattern, normalized_major):
                continue
            grouped_role = re.search(r"\b(?:both|all)\b", normalized_major) and (
                _requires_route(normalized_major)
                or any(
                    _contains_role_cue(normalized_major, cue)
                    for cue in _OPTIONAL_ROUTE_CUES
                )
            )
            if grouped_role:
                contexts.append(normalized_major)
                continue
            role_units = re.split(
                r"\s*(?:,|\band\b|\bwith\b)\s*",
                major_unit,
                flags=re.IGNORECASE,
            )
            for unit_index, unit in enumerate(role_units):
                if not re.search(alias_pattern, _normalize_route_language(unit)):
                    continue
                attached = [unit]
                for continuation in role_units[unit_index + 1:]:
                    normalized_continuation = _normalize_route_language(continuation)
                    if any(
                        _contains_role_cue(normalized_continuation, cue)
                        for cue in _EXTERNAL_ROUTE_CUES
                    ):
                        break
                    attached.append(continuation)
                contexts.append(_normalize_route_language(" ".join(attached)))
    return contexts


def _contains_role_cue(context: str, cue: str) -> bool:
    import re

    return bool(re.search(rf"(?<!\w){re.escape(cue)}(?!\w)", context))


def _requires_route(context: str) -> bool:
    """Recognize required-role language without treating its negation as required."""
    import re

    context = _normalize_route_language(context)
    if "not optional" in context:
        return True
    if re.search(
        r"(?:\b(?:not|never)\s+not\s+requir(?:e|es|ing|ed)\b|"
        r"\banything\s+but\s+optional\b|\bfar\s+from\s+optional\b)",
        context,
    ):
        return True
    optional_role = re.search(
        r"(?:\bnever\b[^.!?;]*\brequir(?:e|es|ing|ed)\b|"
        r"^\s*no\b[^.!?;]*\brequir(?:e|es|ing|ed)\b|"
        r"\bnot\s+(?:mandatory|essential|primary)\b|"
        r"\bcan\s+(?:work|operate|function|run)\s+without\b|"
        r"\b(?:do|does|did)\s+not\s+(?:rely|depend)\s+on\b|"
        r"\bindependent\s+of\b|\bsecondary\b[^.!?;]*\bonly\b)",
        context,
    )
    if optional_role:
        return False
    without_negated_required = re.sub(
        r"(?:not requir(?:e|es|ing|ed)|without[^.!?;]*requir(?:e|es|ing|ed)|"
        r"must not[^.!?;]*|need not[^.!?;]*|"
        r"(?:do|does|did|will|would|should|could|can) not[^.!?;]*depend[^.!?;]*|"
        r"not (?:the )?primary)",
        "",
        context,
    )
    return any(
        cue != "not optional" and _contains_role_cue(without_negated_required, cue)
        for cue in _REQUIRED_ROUTE_CUES
    )


def _required_external_route_assertions(candidate: Any) -> list[str]:
    """Find required external routes asserted in product copy without metadata."""
    import re

    assertions: list[str] = []
    fields = dict.fromkeys(_ROUTE_ASSERTION_FIELDS)
    external_cues = tuple(cue.strip() for cue in _EXTERNAL_ROUTE_CUES)
    for field in fields:
        text = _flatten(getattr(candidate, field, None))
        for clause in re.split(r"[.!?;\n]+", text):
            context = _normalize_route_language(clause)
            if not context or not _requires_route(context):
                continue
            if not any(_contains_role_cue(context, cue) for cue in external_cues):
                continue
            if context not in assertions:
                assertions.append(context)
    return assertions


def _route_assertion_is_represented(assertion: str, routes: list[str]) -> bool:
    assertion_tokens = content_tokens(assertion)
    for route in routes:
        route_tokens = content_tokens(route) - content_tokens(_ROUTE_ACCESS_WORDS)
        if not route_tokens:
            continue
        threshold = 1 if len(route_tokens) == 1 else min(2, len(route_tokens))
        if len(assertion_tokens & route_tokens) >= threshold:
            return True
    return False


def unpitched_core_dependencies(seed_text: str, candidate: Any) -> list[str]:
    """External routes absent from the pitch that became a required/core mechanism.

    Supporting routes are allowed: a source mentioned only in data/technical fields,
    or explicitly marked optional, is not product identity. First-party input routes
    are implementation detail too. A route is core when the independent calibration
    critic says the mechanism *needs* it (`market_fit_claimed_route`), or when its new
    distinctive terms are promoted into buyer-facing/differentiation fields.

    This is deliberately provenance/role based, not a regulator or vendor blacklist.
    """
    import re

    seed_tokens = content_tokens(seed_text)
    claimed = _flatten(getattr(candidate, "market_fit_claimed_route", None)).strip()
    claimed_tokens = content_tokens(claimed)
    failures: list[str] = []
    routes = _route_values(candidate)

    aggregation_required = getattr(candidate, "requires_data_aggregation", False) is True
    placeholder_routes = {"", "na", "none", "null", "optional", "tbd", "unknown"}
    if aggregation_required and not routes:
        failures.append("required data aggregation route is unspecified")
    elif aggregation_required:
        failures.extend(
            f"required data aggregation route is invalid: {route}"
            for route in routes
            if (
                re.sub(r"[^a-z0-9]+", "", _normalize_route_language(route))
                in placeholder_routes
                or not content_tokens(route)
            )
        )
    for assertion in _required_external_route_assertions(candidate):
        if not _route_assertion_is_represented(assertion, routes):
            routes.append(assertion)

    aggregation_required_route_seen = False
    for route in routes:
        if _is_first_party_route(route):
            if aggregation_required:
                aggregation_required_route_seen = True
            continue
        route_tokens = content_tokens(route)
        # Match product copy against the route's identity, not generic access
        # wrappers. Otherwise "Customer-supplied Plaid token" requires two
        # matches and a required "Plaid" mechanism escapes detection.
        route_identity_tokens = route_tokens - content_tokens(_ROUTE_ACCESS_WORDS)
        route_identity_tokens = route_identity_tokens or route_tokens
        novel = route_identity_tokens - seed_tokens
        matching_tokens = novel or route_identity_tokens
        if not matching_tokens:
            continue

        core_contexts = _route_role_contexts(
            candidate, matching_tokens, _CORE_PROMISE_FIELDS,
        )
        support_contexts = _route_role_contexts(
            candidate, matching_tokens, _SUPPORTING_ROUTE_FIELDS,
        )
        contexts = [*core_contexts, *support_contexts]
        # A data-source name is not itself a role assertion (for example the
        # literal vendor name "CORE Registry"). Required/optional semantics must
        # come from candidate copy that describes how the route is used.
        role_text = contexts
        copy_required = any(_requires_route(context) for context in role_text)
        explicitly_optional = any(
            any(_contains_role_cue(context, cue) for cue in _OPTIONAL_ROUTE_CUES)
            for context in role_text
        )
        explicitly_required = copy_required or (
            aggregation_required and not explicitly_optional
        )
        if aggregation_required and explicitly_required:
            aggregation_required_route_seen = True
        normalized_route = _normalize_route_language(route)
        route_words = re.findall(r"[a-z0-9]+", normalized_route)
        seed_word_text = " ".join(
            re.findall(r"[a-z0-9]+", _normalize_route_language(seed_text))
        )
        route_word_text = " ".join(route_words)
        seed_mentions_exact_route = bool(
            route_word_text
            and re.search(rf"\b{re.escape(route_word_text)}\b", seed_word_text)
        )
        alias_access_words = {
            *_ROUTE_ACCESS_WORDS.split(),
            "database", "directory", "feed", "registry", "route", "source",
        }
        alias_leading_words = {"external", "optional", "required", "supporting"}
        alias_identity_words = list(route_words)
        while alias_identity_words and alias_identity_words[0] in alias_leading_words:
            alias_identity_words.pop(0)
        while alias_identity_words and alias_identity_words[-1] in alias_access_words:
            alias_identity_words.pop()
        alias_phrase = ""
        for prefix_length in range(len(alias_identity_words), 0, -1):
            prefix = " ".join(alias_identity_words[:prefix_length])
            if re.search(
                rf"\b{re.escape(prefix)}\s+"
                r"(?:api|credential|credentials|database|directory|feed|key|"
                r"registry|route|source|token)\b",
                seed_word_text,
            ):
                alias_phrase = prefix
                break
        if (
            not alias_phrase
            and len(alias_identity_words) == 1
            and re.search(
                rf"\b(?:require|requires|requiring|required|through|using|via)\s+"
                rf"(?:the\s+)?{re.escape(alias_identity_words[0])}\b",
                seed_word_text,
            )
        ):
            alias_phrase = alias_identity_words[0]
        if alias_phrase and not seed_mentions_exact_route:
            alias_pattern = r"\b" + r"[^a-z0-9]+".join(
                re.escape(word) for word in alias_phrase.split()
            ) + r"\b"
            alias_match = re.search(alias_pattern, normalized_route)
            unmatched_tail = (
                normalized_route[alias_match.end():]
                if alias_match
                else normalized_route
            )
            if re.match(
                r"\s*(?:[,|/:;&+]|\b(?:and|plus|with)\b)",
                unmatched_tail,
            ):
                alias_phrase = ""
        seed_mentions_route = seed_mentions_exact_route or bool(alias_phrase)
        if alias_phrase and not seed_mentions_exact_route:
            seed_route_contexts = _alias_route_role_contexts(seed_text, alias_phrase)
        else:
            seed_route_contexts = _route_role_contexts(
                type("SeedRouteContext", (), {"description": seed_text})(),
                route_identity_tokens,
                ("description",),
            )
        seed_requires_route = seed_mentions_route and any(
            _requires_route(context) for context in seed_route_contexts
        )
        seed_marks_route_optional = seed_mentions_route and not seed_requires_route and any(
            any(_contains_role_cue(context, cue) for cue in _OPTIONAL_ROUTE_CUES)
            for context in seed_route_contexts
        )
        if seed_marks_route_optional and explicitly_required:
            failures.append(route)
            continue
        if copy_required and seed_mentions_route and not seed_requires_route:
            failures.append(route)
            continue
        if copy_required and seed_requires_route:
            continue
        route_threshold = (
            1 if len(route_identity_tokens) == 1
            else min(2, len(route_identity_tokens))
        )
        claimed_core = bool(
            claimed_tokens
            and len(route_identity_tokens & claimed_tokens) >= route_threshold
        )
        promoted_core = bool(core_contexts)
        if not seed_mentions_route and (
            explicitly_required
            or ((claimed_core or promoted_core) and not explicitly_optional)
        ):
            failures.append(route)
            continue
        if not novel:
            continue
        threshold = 1 if len(novel) == 1 else min(2, len(novel))
        claimed_core = bool(
            claimed_tokens
            and len(novel & claimed_tokens) >= threshold
        )
        if explicitly_required or (
            (claimed_core or promoted_core) and not explicitly_optional
        ):
            failures.append(route)

    if aggregation_required and not aggregation_required_route_seen:
        failures.append("required data aggregation has no required route")

    return failures


def seed_fidelity_score(seed_text: str, candidate: Any) -> float:
    """Return distinctive seed-token coverage across a candidate's identity fields."""
    seed_tokens = _content_tokens(seed_text)
    if not seed_tokens:
        return 1.0
    candidate_text = _candidate_identity_text(candidate)
    shared = seed_tokens & _content_tokens(candidate_text)
    return len(shared) / len(seed_tokens)


def seed_retention_floor_ok(seed_text: str, candidate: Any) -> bool:
    """The PURE retention floor: ~60% of the pitch's stemmed content tokens must survive
    somewhere in the candidate's product copy.

    Split out of `is_seed_faithful` on 2026-08-14 by the seed-authority reorder. It is the one
    part of the deterministic layer that makes no semantic claim — it does not decide whether
    the candidate is the same PRODUCT, only whether it still talks about the same THINGS.

    WHERE IT RUNS, AND WHAT A WRONG REFUSAL COSTS AT EACH (re-derived by AST scan over `src/`,
    2026-08-15 — the previous version of this paragraph said "four call sites … a wrong refusal
    is non-destructive: each of those callers keeps the previous candidate", and the second half
    was FALSE at one of them). Three sites, of which only TWO are vetoes:

      * `_enhance_idea_mechanism`'s caller (`unified_solution_crew.py`) and the v4 improvement
        loop, both through `is_seed_faithful`. A refusal here discards a REVISION and keeps the
        candidate that already exists (`return idea` / `break`), so it is genuinely recoverable.
        These two are the only remaining VETOES on this function.
      * `_refine_single_concept(frame='user_seed')`, which calls this function directly, and
        where the verdict is now ADVISORY (2026-08-15, S22) — logged, non-binding, and carried
        to the birth judge through `seed_identity_evidence`. It was a veto until then, and its
        refusal kept nothing: it replaced the spec the refine LLM had just written with
        `_synthesize_idea_from_concept`'s no-LLM stub. Measured, one substituted refine model
        (`openrouter/x-ai/grok-4.3`; production's Luna had no credit), same pitch, only the
        refined-FROM concept varying: refining the pitch-shaped fallback 3/3 cleared this floor
        (16, 16, 15), refining real generated concepts 2/7 (15, 14 vs 12, 11, 12, 11, 13). A
        spec written in its own words retains fewer pitch tokens than one that parrots the
        pitch, so as a veto this floor systematically preferred the echo.
      * The seed-cell CONCEPT PREFILTER was the fourth site and is gone (2026-08-15). It applied
        this floor to a `RawConcept`, and refusing every concept there MINTED a candidate out of
        the pitch — the opposite of keeping one. Measured on the real 03d20ff6 run state with
        the production generator: 11 of 12 generated concepts fell under this floor (5-12 of 23,
        floor 14), while real refined specs for the same pitch score 11-19 depending on what
        they were refined FROM. Same threshold, different object. Do not re-add a call on
        concept-shaped input.

    HOW MUCH SMALLER A CONCEPT IS, re-derived 2026-08-15 (S22) because the previous number here
    was wrong: a real `RawConcept` from the production generator has **5-6** of the 25 fields
    `_candidate_identity_text` reads non-empty, not 4 — `data_access_model` and
    `data_acquisition_notes` are generator-populated, and `delivery_format` is present on 8 of
    the 12 captured concepts. 5-6 is a FLOOR, not a count: the capture dump records 9 hand-picked
    keys, so `mechanism_tag`, `data_route`, `data_source_hint` and `data_source_tag` are
    invisible to that measurement. Identity text: **314-363 chars, median 329** across the 12
    (the previous "210-261, median 236" is false). For scale, the corpus's HONEST candidates run
    400-6494 (median 3474) — but its ADVERSARIAL candidates run 117-403, i.e. the same order as
    a concept, which is why nearly all of them fall under this floor in a corpus A/B.

    So the property to check at any NEW no-LLM call site is not "is there a judge" but "what
    exists when this returns False" — and if the answer is "something derived from the pitch",
    the refusal is destructive and this function is the wrong tool.

    It is NOT a birth verdict. At birth it is reported through `seed_identity_evidence` as
    advisory evidence, because it over-refuses on exactly the cases the reorder exists to keep:
    the corpus's `instances_named_ok` retains 12 of 23 stemmed tokens against a floor of 14
    and is nonetheless indisputably the same product.
    """
    seed_tokens = _content_tokens(seed_text)
    if not seed_tokens:
        return True
    candidate_text = _candidate_identity_text(candidate)
    shared = seed_tokens & _content_tokens(candidate_text)
    minimum_retained = max(1, (len(seed_tokens) * 3 + 4) // 5)
    if len(shared) < minimum_retained:
        logger.warning(
            f"[SeedFidelity] rejected — retained {len(shared)}/{len(seed_tokens)} seed terms, "
            f"needed {minimum_retained}; missing: {sorted(seed_tokens - shared)[:12]}"
        )
        return False
    return True


def is_seed_faithful(
    seed_text: str,
    candidate: Any,
    *,
    exact_terms: bool = False,
) -> bool:
    """Require seed-term retention without an unpitched core external dependency.

    AUTHORITY (2026-08-14 reorder). This function is a VERDICT, and it is no longer the birth
    verdict for a free-text user seed. It survives as:
      * the deterministic guard on the TWO remaining no-LLM call sites — the novelty-enhance
        revision and the v4 improvement loop — where a refusal discards a proposed REVISION and
        keeps the candidate that already exists.

    "WHERE REFUSAL IS RECOVERABLE" USED TO BE ASSERTED OF EVERY CALL SITE, AND IT WAS FALSE AT
    ONE (2026-08-15). The seed-cell concept prefilter called this function on every generated
    concept and, when nothing passed, discarded all of them and minted a `RawConcept` out of the
    user's pitch. There was no previous candidate to keep: a wrong refusal there CREATED the
    pitch-shaped one, which `_synthesize_idea_from_concept` then pasted into five report fields
    for two paying users (jobs 03d20ff6, bab9f696). That call site is removed, and the count is
    re-derived by AST scan rather than inherited. Before adding a third, answer the question this
    sentence used to assume: what exists when this returns False? See
    `seed_retention_floor_ok` for the same note on the floor half, and note that the two
    functions have DIFFERENT site counts — this one has two callers, the floor is reached from
    three, because `_refine_single_concept` calls the floor alone. Since 2026-08-15 (S22) that
    third site is ADVISORY, so the deterministic layer's remaining VETOES are exactly this
    function's two revision sites.
    It is NOT any part of the birth verdict. At birth its two components are reported only as
    evidence (see `seed_identity_evidence`), and when the LLM judge cannot be reached birth
    REFUSES outright (`identity_judge_unavailable`) rather than falling back to this function.
    That fallback existed for one round and was removed on 2026-08-14 after it was measured
    accepting a buyer substitution whose evidence was clean on every axis.

    Prompts require those product-identity terms to remain visible in the product copy.
    The route-role check catches an additive replacement that repeats every seed term
    while making a research-derived source the required mechanism. This remains a
    deterministic identity backstop, not a semantic judge of product quality.

    ``exact_terms`` IS DELIBERATELY INERT (2026-08-14). It used to demand 100% retention of
    every stemmed content token; the parameter is kept so the two callers need not change and
    a future reader finds this note instead of re-adding the rule.

    WHY IT WAS REMOVED, with the measurements — do not restore it:

    * The property is unsatisfiable by a faithful rewrite. `_content_tokens` keeps
      near-function words: the live 7703f811 pitch stemmed to 23 tokens including
      'about', 'they', 'whether', 'out', 'find', 'work'. A rewrite that kept the product
      exactly dropped four of them ('find', 'out', 'platform', 'work') and the run was
      discarded at the birth lock.
    * The cap added on 2026-08-13 was calibrated on SURVIVORSHIP. Runs that completed had
      17-25 tokens, so the cap was set at 25 — but they completed because their rewrites
      happened to retain everything, not because 25 is safe. 7703f811 is 23 tokens, under
      the cap, and still failed. Live e1b42702 (62 tokens) failed the same way.
    * It is REDUNDANT with a strictly better gate that fires under the identical condition.
      Callers pass ``exact_terms=bool(identity_terms)``, and `execute_seed_pipeline` runs the
      stated-clause gate on `if identity_terms and self._current_seed_evaluation is None` —
      while this function's exact branch is only reachable when `_current_seed_evaluation is
      None`. So whenever the 100% rule tightened, `seed_clause_drift` (mechanism / audience /
      problem / delivery) and then `_semantic_seed_identity_matches` were about to run anyway.
      A single critical verb swap ("drafts" -> "analyzes") is clause drift; those gates catch
      it by meaning, this one caught it by spelling.

    What remains is the proportional floor (~60%), which is what a deterministic lexical
    backstop can honestly assert, plus the route-role check above.

    Logs WHY on rejection: this is the only guard in the seed chain whose callers print a
    verdict without a reason, which is what made e1b42702 read as inexplicable.
    """
    unpitched = unpitched_core_dependencies(seed_text, candidate)
    if unpitched:
        logger.warning(
            "[SeedFidelity] rejected — unpitched core data route(s): "
            + ", ".join(str(route) for route in unpitched)
        )
        return False
    return seed_retention_floor_ok(seed_text, candidate)


def structured_synthesis_fidelity_failures(
    proposal: dict, candidate: Any,
) -> list[str]:
    """Return exact Concept Forge identity clauses missing from candidate copy.

    This deliberately reads only product identity fields, never the attached
    `synthesis_evaluation` provenance. Otherwise a drifted candidate would pass
    simply because the original brief was serialized beside it.
    """
    identity_text = " ".join(
        _flatten(getattr(candidate, field, None))
        for field in _IDENTITY_FIELDS
    )
    identity_tokens = _content_tokens(identity_text)
    failures: list[str] = []

    def require(
        label: str, text: str, fraction: float, floor: int,
        candidate_tokens: set[str],
    ) -> None:
        tokens = _content_tokens(text)
        if not tokens:
            return
        required = min(len(tokens), max(floor, ceil(len(tokens) * fraction)))
        if len(tokens & candidate_tokens) < required:
            failures.append(label)

    require(
        "proposedTitle",
        str(proposal.get("proposedTitle") or ""),
        0.5,
        1,
        identity_tokens,
    )
    # An exact Concept Forge option may be refined, but its core product copy
    # must retain most of the selected workflow. A lower threshold let a title,
    # persona, and recycled domain nouns conceal a different mechanism.
    require(
        "proposedBrief",
        str(proposal.get("proposedBrief") or ""),
        0.6,
        3,
        identity_tokens,
    )

    exact = proposal.get("evaluation")
    axes = exact.get("changedAxes") if isinstance(exact, dict) else None
    if isinstance(axes, list):
        for index, axis in enumerate(axes):
            if not isinstance(axis, dict):
                failures.append(f"changedAxes[{index}]")
                continue
            label = str(axis.get("axis") or index)
            axis_fields = _AXIS_IDENTITY_FIELDS.get(label, _IDENTITY_FIELDS)
            axis_tokens = _content_tokens(" ".join(
                _flatten(getattr(candidate, field, None))
                for field in axis_fields
            ))
            require(
                f"changedAxes.{label}.to",
                str(axis.get("to") or ""),
                0.6,
                1,
                axis_tokens,
            )
    return failures


# ── per-clause drift detection for "Check my idea" seeds (quality pass Q4/Q6) ──

_DRIFT_CLAUSES = ("mechanism", "audience", "problem", "delivery")

_DRIFT_AXIS_BY_CLAUSE = {
    "mechanism": "mechanism",
    "audience": "buyer",  # the buyer axis is what pulls in target_personas
    "problem": "job",
    "delivery": "channel",
}

# Contrast cues that repudiate a term occurring later in the SAME sentence. Token
# overlap alone is negation-blind: a seed can argue AGAINST the pitch using the
# pitch's own vocabulary ("instead of ... another AI reply writer") and still pass
# a shared-token check.
_REPUDIATION_CUES = (
    "instead of", "rather than", "unlike", "avoid", "is not", "are not",
    "do not", "does not", "isn't", "aren't", "don't", "doesn't", "without",
    "never", "no longer", "versus", "not just", "not another",
)


def _sentence_segments(value: Any) -> list[str]:
    """Sentence-scoped segments of one identity field. List items are their own
    segments — concatenating fields (or items) lets a cue at the end of one text
    poison a term at the start of the next."""
    import re

    if value is None:
        return []
    if isinstance(value, str):
        parts = value
    elif isinstance(value, dict):
        return [seg for item in value.items()
                for seg in _sentence_segments(f"{item[0]} {item[1]}")]
    elif isinstance(value, Iterable):
        return [seg for item in value for seg in _sentence_segments(item)]
    else:
        parts = str(value)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", parts) if s.strip()]


def _stem_occurrences(stem: str, sentence: str) -> tuple[int, int]:
    """(clean, repudiated) occurrence counts of `stem` in one sentence.

    A sentence-INITIAL cue ("Rather than X, the product does Y") introduces the
    rejected alternative and then asserts — its scope ends at the first comma, so
    the asserted half stays clean. Mid-sentence cues scope to the end of the
    sentence ("... an escalation request rather than a draft").
    """
    import re

    from .text_stemmer import stem_word

    lower = sentence.lower()
    cue_scopes: list[tuple[int, int]] = []
    for cue in _REPUDIATION_CUES:
        for pos in _find_all(lower, cue):
            if pos == 0:
                comma = lower.find(",", pos)
                end = comma if comma != -1 else len(lower)
            else:
                end = len(lower)
            cue_scopes.append((pos, end))
    clean = repudiated = 0
    for match in re.finditer(r"\w+", lower):
        if stem_word(match.group()) != stem:
            continue
        if any(start < match.start() < end for start, end in cue_scopes):
            repudiated += 1
        else:
            clean += 1
    return clean, repudiated


def _find_all(haystack: str, needle: str) -> list[int]:
    positions = []
    start = 0
    while (pos := haystack.find(needle, start)) != -1:
        positions.append(pos)
        start = pos + 1
    return positions


def seed_clause_drift(
    identity_terms: dict | None,
    candidate: Any,
    inferred_fields: list[str] | None = None,
) -> list[str]:
    """Clauses of the user's pitch the evaluated seed no longer embodies.

    Per STATED clause (inferred or term-less clauses are skipped), the clause
    drifted when:
      (a) at least one clause term appears ONLY in repudiated positions (a
          contrast cue earlier in the same sentence of an axis-scoped identity
          field), or
      (b) no clause term appears in the axis-scoped identity fields at all.
      (c) the candidate retains those terms but promotes an unpitched external
          route into the required mechanism or core differentiation.

    Deliberately NOT "≥1 shared token" (passes a seed that repositioned against
    the pitched mechanism while reusing its vocabulary) and NOT "all terms must
    survive" (a merely-absent term is not repudiation). Seed-pipeline consumers use
    this as a fail-closed identity gate before accepting a transformed candidate.
    """
    inferred = set(inferred_fields or [])
    stated_text = " ".join(
        term
        for terms in (identity_terms or {}).values()
        for term in (terms or [])
        if isinstance(term, str)
    )
    additive_mechanism = bool(
        stated_text and unpitched_core_dependencies(stated_text, candidate)
    )
    drifted: list[str] = []
    for clause in _DRIFT_CLAUSES:
        if clause in inferred:
            continue
        terms = (identity_terms or {}).get(clause) or []
        stems = content_tokens(" ".join(t for t in terms if isinstance(t, str)))
        if not stems:
            continue
        segments = [
            segment
            for field in _AXIS_IDENTITY_FIELDS[_DRIFT_AXIS_BY_CLAUSE[clause]]
            for segment in _sentence_segments(getattr(candidate, field, None))
            if not _is_provenance_echo(segment)
        ]
        clean_stems: set[str] = set()
        fully_repudiated = False
        for stem in stems:
            clean = repudiated = 0
            for segment in segments:
                c, r = _stem_occurrences(stem, segment)
                clean += c
                repudiated += r
            if clean or repudiated:
                if clean:
                    clean_stems.add(stem)
            if repudiated and not clean:
                fully_repudiated = True
        minimum_retained = len(stems) if clause == "mechanism" else 1
        if fully_repudiated or len(clean_stems) < minimum_retained or (
            clause == "mechanism" and additive_mechanism
        ):
            drifted.append(clause)
    return drifted


# ── evidence collection for the seed-authority reorder (2026-08-14) ─────────────────────

def seed_identity_evidence(
    seed_text: str,
    candidate: Any,
    identity_terms: dict | None = None,
    inferred_fields: list[str] | None = None,
) -> dict:
    """Every deterministic seed-identity finding, WITHOUT a verdict.

    WHY THERE IS NO VERDICT HERE. Three lexical checks used to be sequenced IN FRONT of the LLM
    judge at seed birth, each able to veto alone. Four paid production runs were destroyed that
    way, and each fix was a threshold tuned on one sample that broke on the next run. The
    checks are good EVIDENCE and bad JUDGES: they are token-overlap heuristics, so they cannot
    tell a category instance from a substitution ("DeepSeek" is an AI assistant; no amount of
    stemming knows that). This function is what they became.

    Measured on `tests/fixtures/seed_identity_corpus.json`, the corpus case `instances_named_ok`
    — a legitimate elaboration that MUST be accepted — trips all three at once:
        unpitched routes 4 · clause drift ['mechanism'] · retention 12/23 against a floor of 14.
    So promoting ANY single one of them back to a veto re-breaks the case the reorder exists to
    fix. That is the standing argument against "just add one more check here".

    Returns plain data so `capture_gate_input`-style replay stays possible and the birth trace
    can record exactly what the judge was shown.
    """
    seed_tokens = _content_tokens(seed_text)
    shared = seed_tokens & _content_tokens(_candidate_identity_text(candidate))
    floor = max(1, (len(seed_tokens) * 3 + 4) // 5) if seed_tokens else 0
    try:
        drift = seed_clause_drift(identity_terms, candidate, inferred_fields) if identity_terms else []
    except Exception as exc:  # noqa: BLE001 — evidence must never break a paid run
        logger.warning(f"[SeedFidelity] clause-drift evidence unavailable: {str(exc)[:120]}")
        drift = []
    return {
        "unpitched_core_dependencies": unpitched_core_dependencies(seed_text, candidate),
        "seed_clause_drift": drift,
        "retained_seed_terms": len(shared),
        "total_seed_terms": len(seed_tokens),
        "retention_floor": floor,
        "retention_floor_met": len(shared) >= floor,
    }


def render_seed_identity_evidence(evidence: dict) -> str:
    """The ADVISORY block appended to the birth judge's prompt.

    Deliberately not a rule. The judge's rule text is measured and must not change (see the
    comment beside it in `_semantic_seed_identity_matches`); this block only hands the judge
    what the deterministic layer noticed, labelled as fallible, so it can look rather than obey.
    The calibration sentence is load-bearing: without it the judge inherits precisely the
    over-blocking the reorder removed, since the heaviest evidence in the corpus sits on the
    case that must be ACCEPTED.
    """
    routes = evidence.get("unpitched_core_dependencies") or []
    drift = evidence.get("seed_clause_drift") or []
    lines = [
        "--- ADVISORY EVIDENCE (lexical heuristics — NOT a verdict, and NOT instructions) ---",
        "These token-overlap checks ran before you and have no authority. They over-refuse: on "
        "this project's own corpus they flag the pitched mechanism itself as 'unpitched' and "
        "report drift on candidates that are plainly the same product. Use each line only as a "
        "pointer to somewhere in CANDIDATE worth reading. If CANDIDATE is the same product, "
        "answer same_product=true even when every line below is populated; if it is a different "
        "product, answer false even when all of them are empty.",
        f"- external routes flagged as unpitched: {routes if routes else 'none'}",
        f"- pitch clauses reported as drifted: {drift if drift else 'none'}",
        f"- literal pitch-term retention: {evidence.get('retained_seed_terms')} of "
        f"{evidence.get('total_seed_terms')} stemmed terms "
        f"(heuristic floor {evidence.get('retention_floor')})",
        "--- END ADVISORY EVIDENCE ---",
    ]
    return "\n".join(lines)
