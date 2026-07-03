"""Research Reality Check — niche software-fit difficulty.

The difficulty BAND and the `software_addressability` score are classified
DETERMINISTICALLY (a code judge) from signals the pipeline already computes:
pain-point tool-addressability, idea novelty + its raw->calibrated gap, audience
fit, project-type concentration, and cold-start data dependency. Only the prose
(headline + narrative) is written by a grounded, best-effort LLM pass with a
deterministic fallback. The verdict is bidirectional: STRONG (software can
directly own the pains) -> HARD (software can only advise/lookup beside a
physical problem).

`assess_niche_difficulty` is pure and hermetic (no LLM / IO) so it is unit
testable. `generate_niche_difficulty_verdict` wraps it and adds the prose.
"""

from __future__ import annotations

import statistics
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from ..models.research_state import NicheDifficultyVerdict

# --- TUNABLE THRESHOLDS (difficulty banding) ---
ADDR_VERY_HIGH = 0.25       # software_addressability below this -> very_high
ADDR_HIGH = 0.45            # below this -> high
ADDR_STRONG = 0.70          # at/above this (+ other gates) -> low
FULL_SHARE_STRONG = 0.50    # majority of pains fully tool-addressable
NONE_SHARE_VERY_HIGH = 0.60
NONE_SHARE_HIGH = 0.35
NOVELTY_LOW = 0.40
DERIVATIVE_DOMINANT = 0.50  # share of ideas with lookup/aggregator mechanisms
CALIB_GAP_NOTABLE = 0.15    # median(raw - calibrated) novelty downgrade
COLD_START_HEAVY = 0.50
AUDIENCE_FIT_WEAK = 0.50
SATURATION_DUP = 0.35       # share of brainstormed concepts dropped as already-existing -> crowded
MIN_SAMPLE = 3              # below this (pains AND ideas) -> low_confidence

# Surfaced when the data + pains are solid but the tool ecosystem is mature: a large share of
# brainstormed concepts were flagged as versions of products that already ship.
_SATURATION_CHALLENGE = (
    "The data and the pains are here, but the tool ecosystem looks mature — a large share of "
    "the brainstormed concepts were flagged as versions of products that already ship. The bar "
    "here is differentiation, not feasibility; find a sharper wedge, or consider a niche with "
    "the same data richness but fewer incumbents."
)

# Mechanism tags / project types that signal a derivative "lookup / reference"
# shape (software organizes information rather than owning the workflow).
_DERIVATIVE_TOKENS = (
    "lookup", "directory", "aggregat", "comparison", "compare",
    "database", "index", "catalog", "reference", "advice", "checker",
    "benchmark", "registry",
)
# data_access_model values that mean the data isn't sitting there ready to use.
_COLD_START_ACCESS = {"blocked", "restricted", "unofficial"}

_BANDS = ("low", "medium", "high", "very_high")


class NicheDifficultyFactPack(BaseModel):
    """Deterministic signal bundle — the grounding for the verdict prose."""

    n_pains: int
    n_ideas: int
    none_share: float
    partial_share: float
    full_share: float
    software_addressability: float
    median_novelty: Optional[float] = None
    novelty_calibration_gap: Optional[float] = None
    project_type_hhi: float = 0.0
    dominant_project_type: Optional[str] = None
    derivative_mechanism_share: float = 0.0
    audience_fit_ratio: Optional[float] = None
    cold_start_share: float = 0.0
    concept_duplication_rate: Optional[float] = None
    audience_scope: Optional[str] = None
    # Willingness-to-pay signals from the pains' commercial intent (None = no pains carried it)
    commercial_intent_max: Optional[float] = None
    high_commercial_share: Optional[float] = None
    difficulty_level: str = "medium"
    low_confidence: bool = False
    flags: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)


class NicheDifficultyNarrative(BaseModel):
    """LLM output. The headline is LLM-written but its RATING word is fixed by the band (validated
    below), so it stays in sync while still being tailored to the niche."""

    headline: str = Field(
        ..., description="Verdict line, EXACTLY 'Software Fit: <fixed rating> — <niche-specific clause>'"
    )
    narrative_summary: str = Field(..., description="2-4 sentence candid verdict")


def _share(items, predicate) -> float:
    if not items:
        return 0.0
    return sum(1 for it in items if predicate(it)) / len(items)


def _median(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def assess_niche_difficulty(
    pains, ideas, niche_context, concept_duplication_rate: Optional[float] = None
) -> Optional[NicheDifficultyFactPack]:
    """Classify niche software-fit difficulty from persisted signals.

    `concept_duplication_rate` (optional) is the share of brainstormed concepts the novelty
    critic flagged as already-existing — a tool-ecosystem saturation signal the surviving ideas
    can't show. Returns None only when there is nothing to judge (no pains AND no ideas),
    so the caller can leave the field null and the UI hides the section.
    """
    pains = pains or []
    ideas = ideas or []
    if not pains and not ideas:
        return None

    none_share = _share(pains, lambda p: getattr(p, "tool_addressable", "full") == "none")
    partial_share = _share(pains, lambda p: getattr(p, "tool_addressable", "full") == "partial")
    full_share = _share(pains, lambda p: getattr(p, "tool_addressable", "full") == "full")
    software_addressability = round(full_share * 1.0 + partial_share * 0.4 + none_share * 0.0, 3)

    median_novelty = _median([getattr(i, "novelty_score", None) for i in ideas])
    gaps = [
        getattr(i, "novelty_score_raw") - getattr(i, "novelty_score")
        for i in ideas
        if getattr(i, "novelty_score_raw", None) is not None
        and getattr(i, "novelty_score", None) is not None
    ]
    novelty_calibration_gap = _median(gaps) if gaps else None

    # Project-type concentration (Herfindahl), guarding None.
    ptypes = [getattr(i, "project_type", None) for i in ideas if getattr(i, "project_type", None)]
    project_type_hhi = 0.0
    dominant_project_type = None
    if ptypes:
        counts: dict[str, int] = {}
        for t in ptypes:
            counts[t] = counts.get(t, 0) + 1
        project_type_hhi = round(sum((c / len(ptypes)) ** 2 for c in counts.values()), 3)
        dominant_project_type = max(counts, key=counts.get)

    def _is_derivative(idea) -> bool:
        tag = (getattr(idea, "mechanism_tag", None) or "").lower()
        ptype = (getattr(idea, "project_type", None) or "").lower()
        blob = f"{tag} {ptype}"
        return any(tok in blob for tok in _DERIVATIVE_TOKENS)

    derivative_mechanism_share = _share(ideas, _is_derivative)

    audience_scope = getattr(niche_context, "audience_scope", None) if niche_context else None
    audience_fit_ratio = None
    if audience_scope == "segment_of_niche":
        tagged = [getattr(i, "audience_fit", None) for i in ideas]
        decided = [v for v in tagged if v is not None]
        if decided:
            audience_fit_ratio = round(sum(1 for v in decided if v) / len(decided), 3)

    def _is_cold_start(idea) -> bool:
        if getattr(idea, "requires_data_aggregation", False):
            return True
        dam = (getattr(idea, "data_access_model", None) or "").lower()
        return dam in _COLD_START_ACCESS

    cold_start_share = _share(ideas, _is_cold_start)

    # Willingness-to-pay: the pains' commercial-intent distribution. 0.6 is the same cutoff
    # compute_opportunity_level uses for a "High" opportunity — when NOTHING crosses it, the
    # niche's monetization shape (free tool + distribution vs subscription) is a verdict-level
    # fact the founder needs, independent of how good the ideas are.
    ci_values = [getattr(p, "commercial_intent", None) for p in pains]
    ci_present = [c for c in ci_values if isinstance(c, (int, float))]
    commercial_intent_max = round(max(ci_present), 3) if ci_present else None
    high_commercial_share = (round(sum(1 for c in ci_present if c >= 0.6) / len(ci_present), 3)
                             if ci_present else None)

    # --- Friction flags (drive both band escalation and the key-points list) ---
    flags: list[str] = []
    challenges: list[str] = []

    if full_share < FULL_SHARE_STRONG:
        flags.append("tool_addressability")
        challenges.append(
            "Most pains are only partly software-addressable — a tool can advise, "
            "organize, and warn, but can't remove the root cause. Build for the "
            "decision/advice layer, not the fix."
        )
    if derivative_mechanism_share >= DERIVATIVE_DOMINANT and (median_novelty or 1.0) < NOVELTY_LOW:
        flags.append("derivative")
        challenges.append(
            "Ideas cluster into lookup / directory / aggregator shapes — the niche "
            "rewards a best-in-class reference tool, not a novel mechanism."
        )
    if audience_scope == "too_broad" or (
        audience_fit_ratio is not None and audience_fit_ratio < AUDIENCE_FIT_WEAK
    ):
        flags.append("scope")
        challenges.append(
            "The corpus drifts from the stated audience — tighten the wedge or the "
            "product will end up serving the wrong user."
        )
    if cold_start_share >= COLD_START_HEAVY:
        flags.append("cold_start")
        challenges.append(
            "Most ideas need a data corpus that doesn't exist yet — plan a cold-start "
            "play (seed it, scrape it, or partner) before the product is useful."
        )
    if novelty_calibration_gap is not None and novelty_calibration_gap >= CALIB_GAP_NOTABLE:
        flags.append("calibration")
        challenges.append(
            "Raw idea scores ran optimistic and were corrected down — the obvious "
            "framings here are weaker than they first look."
        )
    # Tool-ecosystem saturation — orthogonal to fit. Fire only when fit ISN'T the main problem
    # (addressability is decent and the data is reachable), so this reads as "good niche, crowded
    # tools" rather than piling onto a hard-fit verdict.
    saturated = (
        concept_duplication_rate is not None
        and concept_duplication_rate >= SATURATION_DUP
        and cold_start_share < COLD_START_HEAVY
        and software_addressability >= ADDR_HIGH
    )
    if saturated:
        flags.append("saturated_tooling")
        challenges.append(_SATURATION_CHALLENGE)

    # --- Banding ---
    if none_share >= NONE_SHARE_VERY_HIGH or software_addressability < ADDR_VERY_HIGH:
        difficulty = "very_high"
    elif none_share >= NONE_SHARE_HIGH or software_addressability < ADDR_HIGH:
        difficulty = "high"
    elif (
        software_addressability >= ADDR_STRONG
        and full_share >= FULL_SHARE_STRONG
        and (median_novelty or 0.0) >= NOVELTY_LOW
        and not (novelty_calibration_gap is not None and novelty_calibration_gap >= CALIB_GAP_NOTABLE)
    ):
        difficulty = "low"
    else:
        difficulty = "medium"

    # Escalate one band if the niche is nominally easy but carries >=2 frictions.
    if difficulty in ("low", "medium") and len(flags) >= 2:
        difficulty = _BANDS[min(_BANDS.index(difficulty) + 1, len(_BANDS) - 1)]

    low_confidence = len(pains) < MIN_SAMPLE and len(ideas) < MIN_SAMPLE

    # --- Key points (bidirectional): strengths for a strong niche, frictions otherwise.
    if difficulty == "low" or software_addressability >= ADDR_STRONG:
        strengths: list[str] = []
        if full_share >= FULL_SHARE_STRONG:
            strengths.append(
                "Most pains are workflow or data problems a tool can directly own."
            )
        if (median_novelty or 0.0) >= NOVELTY_LOW:
            strengths.append("There's room for a genuinely novel angle, not just a clone.")
        if cold_start_share < COLD_START_HEAVY:
            strengths.append("Usable data is reachable without a heavy cold-start lift.")
        key_points = strengths or challenges
    else:
        key_points = challenges

    # Saturation is orthogonal to fit — surface it even when the verdict is otherwise strong
    # ("great data + clear pains, but a mature tool ecosystem").
    if saturated and _SATURATION_CHALLENGE not in key_points:
        key_points = [*key_points, _SATURATION_CHALLENGE]

    # Weak willingness-to-pay is orthogonal to fit AND to idea quality — surface it even on a
    # strong-fit niche (mirrors the saturation append). NOT an escalation flag: it changes the
    # monetization SHAPE, not the difficulty of building.
    if commercial_intent_max is not None and commercial_intent_max < 0.6:
        key_points = [*key_points, _WEAK_WTP_CHALLENGE]

    return NicheDifficultyFactPack(
        n_pains=len(pains),
        n_ideas=len(ideas),
        commercial_intent_max=commercial_intent_max,
        high_commercial_share=high_commercial_share,
        none_share=round(none_share, 3),
        partial_share=round(partial_share, 3),
        full_share=round(full_share, 3),
        software_addressability=software_addressability,
        median_novelty=median_novelty,
        novelty_calibration_gap=(round(novelty_calibration_gap, 3) if novelty_calibration_gap is not None else None),
        project_type_hhi=project_type_hhi,
        dominant_project_type=dominant_project_type,
        derivative_mechanism_share=round(derivative_mechanism_share, 3),
        audience_fit_ratio=audience_fit_ratio,
        cold_start_share=round(cold_start_share, 3),
        concept_duplication_rate=(round(concept_duplication_rate, 3) if concept_duplication_rate is not None else None),
        audience_scope=audience_scope,
        difficulty_level=difficulty,
        low_confidence=low_confidence,
        flags=flags,
        key_points=key_points,
    )


# FIT language comes from the ADDRESSABILITY band, not the difficulty band. difficulty_level
# measures overall difficulty INCLUDING frictions (cold-start, saturation, calibration) and its
# ≥2-flags escalation can push a strong-fit niche to "high" — mapping THAT to "Software Fit:
# Limited" printed a contradiction next to an 88% addressability meter (codex-review finding,
# 2026-07-02). Fit rating = can software address the pains; frictions color the clause/key points.
_FIT_HEADLINES = {
    "strong": "Software Fit: Strong — a tool can directly own these pains",
    "moderate": "Software Fit: Moderate — a useful tool, with real caveats",
    "limited": "Software Fit: Limited — software mostly advises here",
    "very limited": "Software Fit: Hard — software can only sit beside the problem",
}

# The one rating word per addressability band. The LLM writes the headline but must use this exact
# word, so the headline can never drift out of sync with the classified fit (validated post-call).
_FIT_RATING = {"strong": "Strong", "moderate": "Moderate", "limited": "Limited",
               "very limited": "Hard"}


_WEAK_WTP_CHALLENGE = (
    "No pain shows strong buying signals — plan a free-tool + distribution monetization "
    "(lead-gen, sponsorship, a cheap team tier), not subscription pricing."
)


def _wtp_judgment(commercial_intent_max, high_commercial_share) -> str:
    """Willingness-to-pay signal + the judgment it implies (same pattern as saturation —
    a bare number reads wrong in prose; the phrase carries the monetization-shape verdict)."""
    if commercial_intent_max is None:
        return "n/a"
    if commercial_intent_max < 0.6:
        return ("weak — no pain crosses the strong-buying-signal bar; the winning shape here "
                "is a free tool with built-in distribution (lead-gen, sponsorship, a cheap "
                "team tier), NOT subscription SaaS")
    if (high_commercial_share or 0.0) >= 0.25:
        return ("strong — buyers demonstrably carry purchase intent across several pains; "
                "direct paid pricing is viable")
    return ("moderate — some pains carry real buying intent; a paid tier is plausible if it "
            "targets those pains specifically")


def _fit_rating(software_addressability: float) -> str:
    """Rating word for the 'Software Fit' headline — from addressability, never difficulty."""
    return _FIT_RATING[_addressability_band(software_addressability)]


def _fit_headline(software_addressability: float) -> str:
    return _FIT_HEADLINES[_addressability_band(software_addressability)]


def _addressability_band(score: float) -> str:
    """Plain word for software_addressability — user-facing text never shows the raw %/score."""
    if score >= ADDR_STRONG:       # 0.70
        return "strong"
    if score >= ADDR_HIGH:         # 0.45
        return "moderate"
    if score >= ADDR_VERY_HIGH:    # 0.25
        return "limited"
    return "very limited"


def _calibration_gap_word(gap: Optional[float]) -> str:
    """Plain word for the novelty optimism-correction — never the raw decimal."""
    if gap is None:
        return "n/a"
    return "notable" if gap >= CALIB_GAP_NOTABLE else "minor"


def _share_word(share: Optional[float]) -> str:
    """Proportion word for a 0-1 share. The LLM prose anchors on whatever it sees —
    hand it a percentage and it echoes '49% of pains'; hand it a word and it writes
    prose. So shares NEVER reach the prompt as numbers."""
    if share is None:
        return "n/a"
    if share <= 0.02:
        return "none"
    if share < 0.15:
        return "a small minority"
    if share < 0.35:
        return "about a quarter"
    if share < 0.65:
        return "about half"
    if share < 0.85:
        return "most"
    return "nearly all"


def _shape_concentration_word(hhi: float) -> str:
    """Is the most common idea shape actually DOMINANT, or just the plurality? A 20%-share
    plurality narrated as 'the dominant shape' misleads — HHI decides the honest word."""
    if hhi >= 0.5:
        return "one shape genuinely dominates the pool"
    if hhi >= 0.3:
        return "the pool leans toward this shape but stays mixed"
    return "the pool is varied — no single shape dominates"


def _saturation_judgment(rate: Optional[float]) -> str:
    """Saturation share + the judgment the number implies — a bare '6%' reads as a
    warning in prose when it actually means the space is open."""
    if rate is None:
        return "n/a"
    if rate < 0.15:
        return "low — the obvious tools are largely NOT already built"
    if rate < 0.35:
        return "moderate — some obvious angles are already shipping products"
    return "high — most obvious angles are already shipping products"


def _fallback_narrative(fp: NicheDifficultyFactPack, niche: Optional[str]) -> tuple[str, str]:
    """Deterministic templated prose used when the LLM is skipped or fails. FIT statements come
    from the addressability band; difficulty (frictions) colors the follow-on via key_points."""
    where = fp.dominant_project_type or "tooling"
    fit_band = _addressability_band(fp.software_addressability)
    if fit_band in ("limited", "very limited"):
        lead = (
            "This niche is hard to solve with software. "
            f"{fp.n_pains - int(round(fp.full_share * fp.n_pains))} of {fp.n_pains} pains "
            "sit beyond what a tool can fix — software can advise, organize, and warn, "
            "but not remove the root cause. The realistic shape is a "
            f"{where}-style advice/lookup layer, not a mechanism that solves the problem."
        )
    elif fit_band == "strong":
        lead = (
            "This niche is a strong fit for software — the pains are workflow or data "
            "problems a tool can directly own."
        )
        if fp.difficulty_level in ("high", "very_high"):
            lead += (
                " The difficulty is NOT fit: succeeding here carries real frictions — "
                "see the factors below."
            )
        else:
            lead += " There's room for a real product rather than a thin reference."
    else:
        lead = (
            "This niche is a moderate fit for software. "
            "A tool earns its keep, but the easy framings are weaker than they look — "
            "pick the wedge carefully."
        )
    if fp.key_points:
        lead += " " + fp.key_points[0]
    if fp.low_confidence:
        lead += " (Limited sample — treat as directional.)"
    return _fit_headline(fp.software_addressability), lead


def generate_niche_difficulty_verdict(
    fact_pack: NicheDifficultyFactPack,
    niche: Optional[str],
    niche_context,
) -> tuple[NicheDifficultyVerdict, Optional[object]]:
    """Build the verdict: deterministic fields + best-effort grounded LLM prose.

    Returns (verdict, usage) where usage is the LLM TokenUsage if the call ran,
    else None. The verdict is always populated (deterministic fallback first).
    """
    fp = fact_pack
    headline, narrative = _fallback_narrative(fp, niche)
    usage = None

    try:
        from .llm_service import LLMService
        from .prompts import load_prompt, safe_format
        from .score_helpers import score_band
        from ..config.settings import settings

        target_audience = getattr(niche_context, "user_target_audience", None) if niche_context else None
        template = load_prompt("niche_difficulty_verdict")
        prompt = safe_format(
            template,
            niche=niche or "this niche",
            target_audience=target_audience or "the stated audience",
            rating_word=_fit_rating(fp.software_addressability),
            difficulty_level=fp.difficulty_level,
            # EVERYTHING quantitative goes to the LLM as WORDS (bands / proportion words /
            # judgment phrases), never numbers — the model anchors on and echoes any digit it
            # sees ("software can only address 49% of the pains… already 6% saturated"),
            # producing stat-soup prose the reader can't act on.
            software_addressability=_addressability_band(fp.software_addressability),
            none_share=_share_word(fp.none_share),
            partial_share=_share_word(fp.partial_share),
            full_share=_share_word(fp.full_share),
            dominant_project_type=fp.dominant_project_type or "n/a",
            shape_concentration=_shape_concentration_word(fp.project_type_hhi),
            derivative_mechanism_share=_share_word(fp.derivative_mechanism_share),
            median_novelty=("n/a" if fp.median_novelty is None else score_band(fp.median_novelty)),
            novelty_calibration_gap=_calibration_gap_word(fp.novelty_calibration_gap),
            cold_start_share=_share_word(fp.cold_start_share),
            concept_duplication_rate=_saturation_judgment(fp.concept_duplication_rate),
            audience_scope=fp.audience_scope or "n/a",
            audience_fit_ratio=_share_word(fp.audience_fit_ratio),
            willingness_to_pay=_wtp_judgment(fp.commercial_intent_max, fp.high_commercial_share),
            key_points=" | ".join(fp.key_points) or "n/a",
            low_confidence=fp.low_confidence,
        )
        result, usage = LLMService.invoke_structured(
            prompt=prompt,
            output_model=NicheDifficultyNarrative,
            temperature=0.7,
            model_name=settings.function_calling_llm,
        )
        # Accept the LLM headline ONLY if it carries the fit rating word — otherwise the
        # deterministic fit headline stands. Guarantees the rating stays in sync while letting the
        # LLM tailor the clause after the em-dash.
        rating = _fit_rating(fp.software_addressability)
        cand = result.headline.strip()
        if cand and f"software fit: {rating}".lower() in cand.lower():
            headline = cand
        elif cand:
            logger.warning(
                f"[Niche Difficulty] LLM headline '{cand[:60]}' missing rating '{rating}' — "
                "keeping deterministic headline."
            )
        if result.narrative_summary.strip():
            narrative = result.narrative_summary.strip()
    except Exception as e:  # noqa: BLE001 — best-effort; deterministic fallback already set
        logger.warning(f"[Niche Difficulty] prose LLM failed: {e}. Using deterministic narrative.")

    verdict = NicheDifficultyVerdict(
        difficulty_level=fp.difficulty_level,
        software_addressability=fp.software_addressability,
        headline=headline,
        narrative_summary=narrative,
        key_challenges=fp.key_points,
        low_confidence=fp.low_confidence,
    )
    return verdict, usage
