"""The ONE data-provenance vocabulary + the alias map that folds legacy labels onto it.

`DataAccessTag` (models/solution_idea.py) is the single source of truth: it is the Literal
`IdeaTags.data_access` is typed with, so a label that passes the screen here survives the tag
copy verbatim instead of being silently nulled by `utils.idea_tags`.

Why this module exists: the accept-lists were duplicated across six write sites and had drifted
apart — one was a 10-value SUPERSET (it let `none`/`official`/`licensed` through the pool
contract only for them to be nulled downstream), and four others shared a 6-tuple that accepted
`none` while REJECTING the canonical `blocked`/`unverified`, erasing the very labels that drive
the feasibility cap, the market-fit rule-b cap and the pre-rank filter.

This module must NOT import from `crews/` (the crews import it — a reverse import cycles).
"""

from __future__ import annotations

from typing import Optional, get_args

from nicheiq.models.solution_idea import DataAccessTag

# public | freemium | paywalled | unofficial | restricted | blocked | unverified
DATA_ACCESS_VOCAB = frozenset(get_args(DataAccessTag))

# Legacy / off-vocab labels that carry REAL meaning, folded onto the canonical tag rather than
# dropped. Anything not listed here is genuinely unknown and abstains (see callers).
DATA_ACCESS_ALIASES = {
    # 'none' / 'not-data-dependent' are what the models emit for pure-computation or
    # first-party-input products (calculators, planners, user-supplied-data tools). There is no
    # external source, hence no access barrier — exactly what 'public' means for scoring
    # purposes. This is the same call `verify_data_routes` already makes for `self_sourced`
    # ideas in crews/idea_improvement_loop_v4.py.
    "none": "public",
    "not-data-dependent": "public",
    # 'official' = an official/first-party API or publication. Mirrors `_canonicalize_route`
    # in crews/idea_improvement_loop_v4.py, which folds the v4 verifier's `official` verdict
    # onto 'public' when the route is obtainable.
    "official": "public",
    # 'licensed' = data obtained under a paid commercial license — a cost barrier, i.e.
    # 'paywalled'. Never observed in any artifact; folded for completeness.
    "licensed": "paywalled",
}


def normalize_data_access(value: Optional[str]) -> Optional[str]:
    """Lowercase/strip `value`, apply `DATA_ACCESS_ALIASES`, and return it if it is a canonical
    `DataAccessTag` — otherwise None, so each caller picks its own fallback (abstain to
    'unverified', divert prose to notes, ...)."""
    v = (value or "").strip().lower()
    if not v:
        return None
    v = DATA_ACCESS_ALIASES.get(v, v)
    return v if v in DATA_ACCESS_VOCAB else None


def note_route_label(owner, path: str, resolved: Optional[str]) -> None:
    """Tally a GENERATOR-emitted `data_access_model` label (bundles / variant merge / parity
    pivot / red-team revision) on `owner` — the crew instance that owns the run.

    Only two outcomes are counted, because only those two cost anything: `resolved is None`
    (off-vocab — the caller abstains to 'unverified') and 'blocked' (a self-report that drives
    the same irreversible feasibility caps as the search-grounded verifier's verdict). Their
    rate was previously unmeasurable — the warning logs fired per abstention but nothing
    recorded how often either actually happens. Counter only; never raises."""
    try:
        counts = getattr(owner, "_route_label_counts", None)
        if not isinstance(counts, dict):
            counts = {}
            owner._route_label_counts = counts
        counts["labels"] = counts.get("labels", 0) + 1
        key = ("off-vocab" if resolved is None
               else ("blocked" if resolved == "blocked" else None))
        if key:
            counts[f"{key}:{path}"] = counts.get(f"{key}:{path}", 0) + 1
    except Exception:  # a counter must never break a birth path
        pass


def route_label_summary(owner) -> Optional[str]:
    """One-line per-run summary of `note_route_label`'s tally, or None when nothing was
    recorded. Emitted once at the end of the flow."""
    counts = getattr(owner, "_route_label_counts", None)
    if not isinstance(counts, dict) or not counts:
        return None
    total = counts.get("labels", 0)
    flagged = sorted((k, v) for k, v in counts.items() if k != "labels")
    return (f"{total} generator-emitted data_access_model label(s); "
            + (", ".join(f"{k}={v}" for k, v in flagged) if flagged
               else "none blocked or off-vocab"))
