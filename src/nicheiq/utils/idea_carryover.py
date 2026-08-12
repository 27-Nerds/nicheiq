"""Field carry-over for ideas REBUILT from a narrow LLM schema.

Three paths rebuild an existing idea from an ad-hoc schema that names only the handful of
fields the LLM is asked to rewrite — the parity pivot, the variant merge and the red-team
revision — then validate it into a fresh ``BaseSolutionIdea`` and re-stamp a short hand-
written list of carry-overs. Everything the schema omits is silently reset to its default.
That "reset-then-stamp" shape has now failed three times, each time found by accident:
``source_frame`` (Fix #6), then ``project_type`` + ``mechanism_tag``.

Live consequence in run 8ef396eb: HouseNutIndex was the run's one accepted parity pivot and
the only one of 16 refined ideas with ``project_type: None`` — 26 fields in all came back
null — and that null failed ``SolutionSnapshot`` validation, silently deleting the finished
report's entire go/no-go verdict. The same nulls appear on red-team revisions and merges in
five other runs.

This inverts the default: PRESERVE, then reset. A field is carried only when the revision
left it empty, so a rebuild can never clobber what the LLM actually produced, and most fields
added to ``BaseSolutionIdea`` later are carried without anyone remembering to add them here.
Identity-defining fields such as ``delivery_format`` are re-derived for an identity-changing
rebuild; callers performing a same-product enrichment must opt into that distinct mode.
``NEVER_CARRY`` is hand-maintained under these rules:

  (1) it evaluates the OLD product or the OLD market position, and the revision must
      re-earn it — ``_score_wave`` recomputes every one of these; carrying it would also
      defeat the accept-guards, which compare the revision's composite against the original
      and require its own parity finding to clear.
  (2) it is user-facing copy that SUMMARIZES a field the revision rewrote, so carrying it
      would describe a product that no longer exists.
  (3) it is CODE-FILLED durable identity, owned by the identity minter.
"""

from __future__ import annotations

from enum import Enum

from ..models.delivery_format import infer_delivery_format, normalize_delivery_format


class CarryForwardMode(str, Enum):
    """Whether a reconstruction preserves or changes the product's identity."""

    IDENTITY_CHANGING_REBUILD = "identity_changing_rebuild"
    SAME_PRODUCT_ENRICHMENT = "same_product_enrichment"

# Rule (1): evaluation state the revision must re-earn.
_RE_EARNED = frozenset({
    "incumbent_parity", "adjacent_market_parity", "market_fit_claimed_route",
    "red_team_verdict", "red_team_caveats", "red_team_findings", "red_team_revised",
    "red_team_vocab_mismatch",
    "calibration_notes", "refine_binding_constraint", "duplicate_of",
    "novelty_score", "seo_scalability_score", "solo_dev_feasibility", "obviousness_score",
    "market_fit_score_raw", "technical_feasibility_score_raw", "novelty_score_raw",
    "seo_scalability_score_raw", "obviousness_score_raw", "solo_dev_feasibility_raw",
    # `_classify_idea_angles` SKIPS ideas that already carry a winning_angle, so carrying it
    # would pin the revision to the original product's GTM judgement.
    "winning_angle", "angle_rationale", "differentiation_locus",
    # Visibility is re-decided for the rebuilt idea by its own accept-guard.
    "candidate_status",
})

# Rule (2): copy that summarizes a rewritten field.
_STALE_SUMMARY = frozenset({
    "headline", "short_description", "why_it_works_short", "novelty_rationale",
})

# Rule (3): CODE-FILLED durable identity. The identity minter owns these; copying one onto a
# rebuilt idea would hand a merge the identity of a single member it absorbed.
_MINTED_IDENTITY = frozenset({
    "idea_id", "idea_revision", "identity_origin", "identity_operation_id",
    "evaluation_id", "evaluation_source_message_id", "proposed_title",
    "synthesis_evaluation", "generation_operation_id", "generation_batch_ordinal",
    # Stamped by the rebuild that produced `rev`; the ORIGINAL was not itself a rebuild,
    # so carrying its value would mislabel where this product came from.
    "rebuild_origin",
})

# Rule (4): POSITIONING AND ECONOMICS OF THE OLD PRODUCT. A rebuild changes what the product
# is; these describe how it is priced, sold, differentiated and sourced, so they are only
# true of the product they were written for. None of the narrow rebuild schemas name them,
# so preserve-then-reset would have carried all seven verbatim onto a different product.
#
# `differentiation_factors` is the self-defeating one: a parity pivot exists BECAUSE the
# original's differentiation collided with an incumbent, so carrying it forward preserves
# the exact claim the pivot was performed to escape. `organic_discovery_queries` is the
# costliest — those queries seed keyword work for a product that no longer exists.
#
# Every field here is in `_REPAIRABLE_TEXT_FIELDS` / `_REPAIRABLE_LIST_FIELDS`, and
# `_repair_blank_idea_fields` now runs on an accepted pivot/merge, so clearing them is not
# data loss: they are rewritten against the revision's own description in one fill-in call
# ("keep the product name, mechanism, data route and description EXACTLY as given").
_OLD_POSITIONING = frozenset({
    "pricing_strategy", "differentiation_factors", "organic_discovery_queries",
    "estimated_cac_organic", "estimated_cac_paid",
    "content_generation_model", "data_acquisition_notes",
})

NEVER_CARRY = _RE_EARNED | _STALE_SUMMARY | _MINTED_IDENTITY | _OLD_POSITIONING

_IDENTITY_CHANGING_FIELDS = frozenset({"delivery_format"})


def _is_empty(value) -> bool:
    """Empty = nothing was produced. 0, 0.0 and False are real values, not absences."""
    if value is None:
        return True
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return False
    return not value


def _not_produced(value, field) -> bool:
    """True when the rebuild produced nothing for this field.

    A field whose model default is NOT empty ("source_frame" defaults to 'pain',
    "requires_data_aggregation" to False) is indistinguishable from a produced value by
    emptiness alone, so a value still sitting at its default also counts as absent — the
    narrow rebuild schemas do not name these fields at all.
    """
    if _is_empty(value):
        return True
    try:
        return value == field.get_default(call_default_factory=True)
    except Exception:  # noqa: BLE001 — an exotic default must not block carry-over
        return False


def carry_forward_idea_fields(
    orig,
    rev,
    *,
    mode: CarryForwardMode = CarryForwardMode.IDENTITY_CHANGING_REBUILD,
) -> list[str]:
    """Fill fields the rebuilt `rev` left empty according to its reconstruction mode.

    Mutates `rev` in place and returns the names carried (for logging). Never overwrites a
    value the revision produced, and never touches `NEVER_CARRY`. Identity-changing rebuilds
    re-derive their primary delivery format from the rebuilt product instead of copying it.
    """
    if orig is None or rev is None:
        return []

    carried: list[str] = []
    for name, field in type(rev).model_fields.items():
        if name in NEVER_CARRY:
            continue
        if mode == CarryForwardMode.IDENTITY_CHANGING_REBUILD and name in _IDENTITY_CHANGING_FIELDS:
            continue
        if not _not_produced(getattr(rev, name, None), field):
            continue
        source = getattr(orig, name, None)
        if _is_empty(source):
            continue
        try:
            setattr(rev, name, source)
        except Exception:  # noqa: BLE001 — a single uncopyable field must not fail the rebuild
            continue
        carried.append(name)

    if mode == CarryForwardMode.IDENTITY_CHANGING_REBUILD:
        rebuilt_text = " ".join(
            str(getattr(rev, field, None) or "")
            for field in ("description", "value_proposition", "technical_approach")
        )
        rev.delivery_format = (
            normalize_delivery_format(getattr(rev, "delivery_format", None))
            or infer_delivery_format(rebuilt_text)
            or "other"
        )
    return carried
