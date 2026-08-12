"""Pure commercial-route classification shared by ideation and research flow."""

from enum import Enum
from typing import get_args

from ..models.solution_idea import CommercialValueCaptureMode


class CommercialLane(str, Enum):
    DIRECT = "direct"
    NON_DIRECT = "non_direct"
    UNKNOWN = "unknown"


_CAPTURE_MODES = frozenset(get_args(CommercialValueCaptureMode))
_NON_DIRECT_MODES = _CAPTURE_MODES - {"direct_user_payment"}


def _commercial_route_raw(item, field: str):
    """Read nested provenance first without erasing typed booleans."""
    route = getattr(item, "commercial_route", None)
    if route is not None:
        return route.get(field) if isinstance(route, dict) else getattr(route, field, None)
    return getattr(item, field, None)


def commercial_route_value(item, field: str) -> str | None:
    """Read nested typed provenance first; flat fields are legacy-only fallback."""
    value = _commercial_route_raw(item, field)
    normalized = str(value or "").strip().lower()
    return normalized or None


def assess_commercial_lane(item) -> CommercialLane:
    """Classify only complete, coherent typed route evidence.

    A non-direct capture name alone is insufficient: the front door must be free/freemium,
    an actual payer must be named, and a real JSON ``False`` must establish that the source
    user can use the utility without payment. Missing or contradictory evidence is conservative.
    """
    access = commercial_route_value(item, "access_model")
    capture = commercial_route_value(item, "value_capture_mode")
    payer = commercial_route_value(item, "payer")
    source_payment = _commercial_route_raw(item, "source_user_payment_required")
    if capture == "direct_user_payment" or source_payment is True:
        return CommercialLane.DIRECT
    if (
        access in {"free", "freemium"}
        and capture in _NON_DIRECT_MODES
        and payer is not None
        and source_payment is False
    ):
        return CommercialLane.NON_DIRECT
    return CommercialLane.UNKNOWN


def has_credible_public_corpus(item) -> bool:
    """True only for a typed, finite public-dataset page corpus.

    Free-text page descriptions and query examples are intentionally irrelevant here.
    """
    route = getattr(item, "commercial_route", None)
    if route is None:
        return False
    origin = route.get("corpus_origin") if isinstance(route, dict) else getattr(
        route, "corpus_origin", None)
    dimensions = route.get("enumerable_dimensions") if isinstance(route, dict) else getattr(
        route, "enumerable_dimensions", None)
    normalized = {
        " ".join(str(axis).lower().split())
        for axis in (dimensions if isinstance(dimensions, list) else [])
        if isinstance(axis, str) and axis.strip()
    }
    data_access = str(getattr(item, "data_access_model", None) or "").strip().lower()
    # RawConcept declares ``data_route`` and must name a bulk route. Refined ideas do not retain
    # that birth-only field; their route verifier's durable verdict is ``data_access_model``.
    # Treat an ad-hoc/missing attribute on those legacy/refined records as absent provenance, not
    # as a refutation, while still honoring an explicit NO-BULK marker when the field exists.
    route_declared = "data_route" in getattr(type(item), "model_fields", {}) or hasattr(
        item, "data_route")
    data_route = str(getattr(item, "data_route", None) or "").strip().lower()
    route_refuted = (
        bool(getattr(item, "critic_no_route", False))
        or (route_declared and data_route in {"", "no-bulk", "none", "n/a"})
    )
    return (
        assess_commercial_lane(item) is CommercialLane.NON_DIRECT
        and data_access == "public"
        and not route_refuted
        and origin == "public_dataset"
        and len(normalized) >= 2
    )
