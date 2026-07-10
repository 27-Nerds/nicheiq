"""Typed generation-frame registry (Multi-Frame Idea Generation Portfolio).

Pure module — no crew imports, no I/O. Defines the frame contract every non-pain generation
cell renders through: a `FrameFocus` (one concrete seed) formatted by its `FrameSpec` into a
brief the ideator sees, plus the market-fit anchor clause the reviewer scores against.

The 'pain' spec's `focus_header` and `mf_anchor` reproduce the CURRENT strings VERBATIM —
see `unified_solution_crew.py::_build_partitioned_block` ("THE ONE PAIN TO SOLVE:") and
`idea_improvement_loop.py::_reviewer_system` (market_fit clause) — this is a regression lock,
not a rewrite: the pain frame's on-the-wire prompt text must not change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# Appended to every NON-pain frame's brief: keeps generation tethered to the validated,
# code-fillable pain_points_addressed contract (coverage net / dedup / IdeaGenerationResult
# validator all require it) even when the seed is not a pain itself.
_ANCHOR_GROUNDING_LINE = (
    "Ground every concept in the ANCHOR PAINS listed — a concept serving none of them will be "
    "rejected."
)


@dataclass(frozen=True)
class FrameFocus:
    """One concrete generation seed for a typed frame cell (pain, gap, data-asset, ...).

    `payload` and `anchor_pain_titles` are excluded from equality/hash (compare=False) — they
    carry generation data, not identity. A FrameFocus's identity is (frame, key).
    """

    frame: str
    key: str
    payload: dict = field(compare=False)
    anchor_pain_titles: list[str] = field(compare=False)
    provenance_label: str = ""


@dataclass(frozen=True)
class FrameSpec:
    """Registry entry describing how to render and anchor one generation frame."""

    frame: str
    brief_formatter: Callable[[FrameFocus], str]
    focus_header: str
    mf_anchor: str
    always_allow_zero: bool


def _pain_brief(focus: FrameFocus) -> str:
    """Pain frame: the crew pre-renders the pain block via `_format_one_pain`; this just
    passes it through unchanged so the on-the-wire prompt text stays byte-identical."""
    return focus.payload.get("pain_text", "")


def _gap_brief(focus: FrameFocus) -> str:
    p = focus.payload
    lines = []
    if p.get("incumbent_name"):
        lines.append(f"INCUMBENT: {p['incumbent_name']}")
    if p.get("pricing"):
        lines.append(f"  Pricing: {p['pricing']}")
    if p.get("gap"):
        lines.append(f"  Structural gap: {p['gap']}")
    if p.get("dissatisfaction_quote"):
        lines.append(f"  Buyer complaint: {p['dissatisfaction_quote']}")
    lines.append(
        "\nAn indie tool can win by displacing part of this incumbent's job — design a product "
        "that does the ONE thing the incumbent structurally won't — for the buyer who already "
        "feels that gap."
    )
    lines.append(_ANCHOR_GROUNDING_LINE)
    return "\n".join(lines)


# Data-currency gate (2026-07-10, live-motivated): a merged data_asset idea assumed a WEEKLY
# feed from a source that is actually a 1908-2017 HISTORICAL index (the NYC-marriage-index case)
# — the frame brief must force the ideator to check cadence instead of assuming freshness.
_DATA_ASSET_CADENCE_NOTE = (
    "State the source's actual publication cadence; a product needing fresher data than the "
    "source publishes is unbuildable — say so instead of assuming."
)


def _data_asset_brief(focus: FrameFocus) -> str:
    p = focus.payload
    lines = []
    if p.get("route_text"):
        lines.append(f"DATA ROUTE: {p['route_text']}")
    lines.append(
        "What product becomes valuable because it sits on top of this data and creates "
        "switching costs — not 'data exists' but 'data creates buyer value'."
    )
    if p.get("cadence_note"):
        lines.append(p["cadence_note"])
    lines.append(_ANCHOR_GROUNDING_LINE)
    return "\n".join(lines)


def _workflow_brief(focus: FrameFocus) -> str:
    p = focus.payload
    lines = []
    if p.get("job_statement"):
        lines.append(f"JOB: {p['job_statement']}")
    if p.get("steps_text"):
        lines.append(f"  Steps: {p['steps_text']}")
    if p.get("tools_text"):
        lines.append(f"  Tools involved: {p['tools_text']}")
    lines.append(
        "Design a product that owns the most painful STEP of this job end-to-end."
    )
    lines.append(_ANCHOR_GROUNDING_LINE)
    return "\n".join(lines)


def _focus_seed_text(focus: FrameFocus) -> str:
    """The IDENTITY-bearing seed text of a focus (gap/route/tool/job) — deliberately excludes the
    generic instructional prose (`_ANCHOR_GROUNDING_LINE` and the brief_formatter's directive
    sentences), so token overlap below measures SPECIFIC linkage, not boilerplate."""
    p = focus.payload
    parts = (
        p.get("incumbent_name", ""), p.get("gap", ""), p.get("dissatisfaction_quote", ""),
        p.get("route_text", ""),
        p.get("job_statement", ""), p.get("steps_text", ""), p.get("tools_text", ""),
    )
    return " ".join(str(x) for x in parts if x)


def _content_tokens(text: str) -> set[str]:
    from .text_stemmer import stem_tokens
    from .validation.dedup import STOPWORDS, normalize_text

    return stem_tokens({
        t for t in normalize_text(text or "").split()
        if len(t) > 2 and t not in STOPWORDS
    })


# Conservative: a focus needs >=2 shared distinctive stemmed tokens with a pain's own text before
# that pain counts as SPECIFICALLY linked (Codex BLOCKER-2) — a single incidental word match (e.g.
# both mention "pricing") is not enough to anchor a whole idea's market_fit to that pain.
_ANCHOR_MIN_SHARED_TOKENS = 2


def anchor_pains_for_frame_focus(focus: FrameFocus, pains: list, cap: int = 5) -> list[str]:
    """SPECIFIC linkage gate for a non-pain frame focus: a validated pain is anchored to `focus`
    only when its title + description + representative_quotes share >= `_ANCHOR_MIN_SHARED_TOKENS`
    distinctive stemmed tokens with the focus's own identity text (the incumbent/gap/route/tool/
    job — never the generic instructional prose). Returns EXACT `PainPoint.title` strings, ranked
    by shared-token strength (desc), capped at `cap`. Empty when nothing clears the bar — the
    caller MUST drop the focus at mint time rather than falling back to a generic 'top pains' set
    (that would defeat the whole point of a typed, evidence-linked frame)."""
    seed = _content_tokens(_focus_seed_text(focus))
    if not seed:
        return []
    scored: list[tuple[int, str]] = []
    for p in pains or []:
        title = getattr(p, "title", "") or ""
        if not title:
            continue
        desc = getattr(p, "description", "") or ""
        quotes = " ".join((getattr(p, "representative_quotes", None) or [])[:3])
        shared = len(seed & _content_tokens(f"{title} {desc} {quotes}"))
        if shared >= _ANCHOR_MIN_SHARED_TOKENS:
            scored.append((shared, title))
    scored.sort(key=lambda t: -t[0])
    return [title for _, title in scored[:cap]]


FRAME_REGISTRY: dict[str, FrameSpec] = {
    "pain": FrameSpec(
        frame="pain",
        brief_formatter=_pain_brief,
        focus_header="THE ONE PAIN TO SOLVE:",
        mf_anchor="does it solve THE SOURCE PAIN BELOW for THIS audience?",
        always_allow_zero=False,
    ),
    "gap": FrameSpec(
        frame="gap",
        brief_formatter=_gap_brief,
        focus_header="THE INCUMBENT GAP TO EXPLOIT:",
        mf_anchor="does it exploit the named incumbent gap for buyers who actually complain about it",
        always_allow_zero=True,
    ),
    "data_asset": FrameSpec(
        frame="data_asset",
        brief_formatter=_data_asset_brief,
        focus_header="THE VERIFIED DATA ASSET:",
        mf_anchor=(
            "does it turn the named data asset into buyer value and switching costs — not just "
            "'the data exists' — and the source actually publishes at the cadence the product needs"
        ),
        always_allow_zero=True,
    ),
    "workflow": FrameSpec(
        frame="workflow",
        brief_formatter=_workflow_brief,
        focus_header="THE JOB THE PERSONA IS TRYING TO GET DONE:",
        mf_anchor="does it own the most painful step of the named job end-to-end for this persona",
        always_allow_zero=True,
    ),
}
