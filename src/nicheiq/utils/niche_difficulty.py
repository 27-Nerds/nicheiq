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

import re
import statistics
from functools import lru_cache
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from ..models.research_state import AudienceDriftNotice, NicheDifficultyVerdict

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
SATURATION_DUP = 0.35       # share of brainstormed concepts dropped as already-existing -> crowded
MIN_SAMPLE = 3              # below this (pains AND ideas) -> low_confidence
# Web-verified competition + usage-shape thresholds (2026-07-06, from the parity/adjacent probes
# and the usage_cadence tag). Informational only — they color key_points/prose, never the band.
SUBSTITUTE_HEAVY = 0.25     # >= this share of ideas face a free/DIY route to the same outcome
INCUMBENT_DENSE = 0.50      # >= this share have a web-verified shipped/partial incumbent
ADJACENT_MONEY = 0.50       # >= this share have an adjacent-market commercial incumbent
EPISODIC_HEAVY = 0.50       # >= this share are episodic/one-shot usage products
PAYABILITY_WEAK_MEAN = 0.40 # mean segment payability below this = weak wallets overall

# Incumbent map + SERP-ownership probes (2026-07-10): additional market-awareness evidence,
# informational only — they color key_points, never the band.
TOOLING_DENSE = 8           # >= this many web-verified incumbent-map rows = a dense tool ecosystem
SERP_OWNED_HEAVY = 0.5      # >= this share of distribution-angle ideas face SERPs already owned

# Surfaced when the data + pains are solid but the tool ecosystem is mature: a large share of
# brainstormed concepts were flagged as versions of products that already ship.
_SATURATION_CHALLENGE = (
    "The data and the pains are here, but the tool ecosystem looks mature — a large share of "
    "the brainstormed concepts were flagged as versions of products that already ship. The bar "
    "here is differentiation, not feasibility; find a sharper wedge, or consider a niche with "
    "the same data richness but fewer incumbents."
)

# These constants are FACTS, never prescriptions. They are rendered to the reader as
# `key_challenges` AND interpolated into the verdict prompt, so a recommended commercial shape
# written here is a hard-coded license that no prompt rewrite can withdraw (D1 round 15: round 14
# deleted the license from the prompt YAML and the same prescriptions survived as these strings).
# Every constant below is enforced clean by
# tests/unit/test_niche_difficulty_constants_are_facts.py.
#
# What "clean" means is precisely the contract in `has_zero_price_prescription` / the named rules,
# and round 16 narrowed it in one direction while keeping it: the forbidden move is prescribing a
# shape in which THIS AUDIENCE DOES NOT PAY. Naming the free/DIY route as the bar a PAID product
# has to clear, or naming which PAID shape survives episodic use, contradicts no wallet reading —
# round 15 deleted both on an object-blind read of the detector and they are restored here.
_SUBSTITUTE_CHALLENGE = (
    "A meaningful share of these outcomes is already obtainable free or DIY (an official data "
    "source, a spreadsheet, a manual routine) — the real competition here comes from that "
    "free/DIY route rather than from another startup. A paid product here must beat that free "
    "route on convenience and completeness, not merely exist."
)
_EPISODIC_CHALLENGE = (
    "Most products in this niche would be used episodically — opened around an event, idle "
    "between events. Engagement restarts at each event rather than running continuously. "
    "Subscriptions churn in that shape; favor one-time purchases, credits, or usage-based pricing."
)
_ADJACENT_MONEY_CHALLENGE = (
    "The mechanisms here already earn revenue in an adjacent commercial market with stronger "
    "wallets: demand for them is demonstrably strongest one market over, and the same product "
    "sold to that adjacent buyer may be the better business; sold here, it runs against those "
    "vendors' marketing budgets."
)
_INCUMBENT_DENSE_CHALLENGE = (
    "Web checks found shipping products covering most of these ideas' core mechanisms — the "
    "bar is head-on differentiation against named incumbents, not filling an empty field."
)


class MarketCrowdingBrief(BaseModel):
    """Pure pre-ideation market-crowding facts; never reads generated ideas."""

    incumbent_count: int = 0
    priced_count: int = 0
    software_addressability: Optional[float] = None
    segment_payability_mean: Optional[float] = None
    wallet_class: Optional[str] = None
    free_density: Optional[str] = None
    tooling_dense: bool = False
    key_point: Optional[str] = None
    generator_directive: Optional[str] = None


def derive_market_crowding_brief(
    pains=None, segments=None, niche_wallet_brief: Optional[dict] = None,
    incumbent_map: Optional[list[dict]] = None,
) -> MarketCrowdingBrief:
    """Build the one pre-idea crowding authority from already-cached pipeline signals."""
    pain_rows = list(pains or [])
    segment_rows = list(segments or [])
    incumbents = list(incumbent_map or [])
    addressable = [
        {"full": 1.0, "partial": 0.4, "none": 0.0}.get(
            (getattr(p, "tool_addressable", None) or "").strip().lower()
        )
        for p in pain_rows
    ]
    addressable = [v for v in addressable if v is not None]
    payability = [
        getattr(s, "payability_score", None) for s in segment_rows
        if isinstance(getattr(s, "payability_score", None), (int, float))
    ]
    incumbent_count = len(incumbents)
    priced_count = sum(
        1 for row in incumbents
        if any(ch.isdigit() or ch == "$" for ch in str((row or {}).get("pricing") or ""))
    )
    dense = incumbent_count >= TOOLING_DENSE
    key_point = _incumbent_density_challenge(incumbent_count, priced_count) if dense else None
    directive = None
    if dense:
        directive = (
            "Crowding authority: the verified incumbent map is dense. Use the named gaps in "
            "MARKET REALITY as hard differentiation constraints; do not propose a head-on clone."
        )
    wallet = niche_wallet_brief or {}
    return MarketCrowdingBrief(
        incumbent_count=incumbent_count,
        priced_count=priced_count,
        software_addressability=(round(sum(addressable) / len(addressable), 3)
                                 if addressable else None),
        segment_payability_mean=(round(sum(payability) / len(payability), 3)
                                 if payability else None),
        wallet_class=(wallet.get("wallet_class") or None),
        free_density=(wallet.get("free_density") or None),
        tooling_dense=dense,
        key_point=key_point,
        generator_directive=directive,
    )


def _wallet_challenge(evidence: str) -> str:
    """Niche wallet probe (2026-07-09): a Phase-1 signal, not a validated verdict — Deep
    Research does the real pricing validation."""
    evidence_clause = f" ({evidence})" if evidence else ""
    return (
        f"Community spend norms point to a free-tool culture{evidence_clause} — products here "
        "are measured against those free options on convenience and completeness. Thin early "
        "signal; Deep Research validates."
    )


def _publishable_wallet_evidence(evidence: str) -> str:
    """Gate the probe evidence BEFORE it is interpolated into the sanctioned statement.

    The parenthetical is a free-text slot filled from model-produced web summary text, sitting
    inside the one statement the whole publication contract rests on. A price list is
    publishable; a clause arguing that buyers refuse to pay is the exact contradiction the
    contract exists to prevent, and it must not ride in on the statement's coat-tails.
    """
    text = (evidence or "").strip()
    if not text:
        return ""
    # A refusal marker needs no topic word to disqualify the slot: the slot's own host sentence
    # supplies the topic, and "nobody upgrades" has no reading that belongs inside it.
    if (
        _paying_wallet_copy_rule_labels(text)
        or has_negative_commercial_stance(text)
        or _WALLET_REFUSAL_RE.search(text)
    ):
        logger.warning(
            "[Niche Difficulty] wallet probe evidence carries its own commercial stance "
            f"({text[:80]!r}); publishing the sanctioned statement without it."
        )
        return ""
    return text


def _wallet_positive_note(evidence: str) -> str:
    """Niche wallet probe (2026-07-10): 'paying' reading is a positive/neutral signal — buyers
    here already spend on tooling, so willingness-to-pay isn't the primary risk. Still Phase-1;
    Deep Research does the real pricing validation."""
    evidence = _publishable_wallet_evidence(evidence)
    evidence_clause = f" ({evidence})" if evidence else ""
    return (
        f"Buyers in this niche demonstrably pay for tooling{evidence_clause}: willingness to pay "
        "is not the primary risk. Thin early signal; Deep Research validates."
    )


def paying_wallet_commercial_contract_copy(
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
) -> Optional[str]:
    """Return the deterministic commercial copy required by every paying-wallet voice."""
    if (
        (wallet_class or "").strip().lower() != "paying"
        or not (wallet_evidence or "").strip()
    ):
        return None
    return _wallet_positive_note("")


# A literal price in the probe evidence is money the probe actually SAW, independent of how the
# classifier bucketed the niche. "$116-$565/mo" means somebody charges that and somebody pays it.
_PRICE_LITERAL_RE = re.compile(
    r"[$€£]\s?\d|\b\d+(?:[.,]\d+)?\s*(?:usd|eur|gbp)\b",
    re.IGNORECASE,
)


def wallet_evidence_shows_real_prices(
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
) -> bool:
    """True when the wallet probe's own evidence carries literal prices.

    Scope gap found in round 14: run 0c9b6f29 is classified ``mixed``, not ``paying``, so the
    positive contract never engaged — and it published "pivot away from subscription SaaS and
    toward free, lead-generation tools" beside its own evidence of "$116-$565/mo". The
    contradiction is identical; only the classifier's bucket differed. The evidence, not the
    bucket, is what a prescription contradicts.

    ``free-culture`` is deliberately excluded even when a price appears: there the priced tool
    is the thing the free route is beating, and calling that a paying wallet inverts the
    finding.
    """
    normalized = (wallet_class or "").strip().lower()
    if normalized not in {"paying", "mixed"}:
        return False
    return bool(_PRICE_LITERAL_RE.search(wallet_evidence or ""))


# The niche-level monetization guidance the REPORT stands behind, one line per wallet reading.
# It lives here rather than in idea_portfolio_summary because it is wallet-derived deterministic
# copy like everything else in this module, and because the sanctioned-statement list below has to
# recognise it: it is persisted onto the verdict card (`NicheDifficultyVerdict.
# monetization_guidance`), so the paying-wallet invariant scans it like any other card string.
#
# Each line REPORTS what the wallet evidence shows and names the open question. None of them
# selects a commercial shape — that is exactly the license D1 keeps finding relocated.
_MONETIZATION_GUIDANCE = {
    "paying": (
        "Verified niche prices show buyers already pay for tooling, so paid pricing — "
        "subscription included — stays on the table; the open question is which pain and which "
        "paid wedge converts."
    ),
    "mixed-priced": (
        "Verified prices show part of this niche already pays for tooling, so paid pricing stays "
        "on the table for the segment that holds the budget; the open question is which segment "
        "that is."
    ),
    "mixed": (
        "Wallets here are mixed: the segment holding budget authority is the one to price to, "
        "and the unbudgeted segment is a distribution question rather than a revenue one."
    ),
    "free-culture": (
        "Established routes here are free: convenience, completeness and trust are the ground a "
        "product competes on before price is even a question."
    ),
}
_MONETIZATION_GUIDANCE_UNKNOWN = (
    "No verified wallet reading for this niche yet — each idea's own pricing note is the only "
    "monetization guidance the reader gets."
)


def monetization_guidance(niche_wallet_brief: Optional[dict]) -> str:
    """The deterministic monetization line for this run — the ONLY niche-level guidance about
    how the product makes money that the report is willing to stand behind.

    Derived from the wallet class and whether its evidence carries literal prices; never from
    prose. It is persisted onto the verdict card so it genuinely reaches the reader, and passed
    into the analyst prompts as read-only context so they can be told plainly that
    commercial-shape selection is out of their remit."""
    wallet = dict(niche_wallet_brief or {})
    wallet_class = (wallet.get("wallet_class") or "").strip().lower()
    evidence = wallet.get("evidence")
    if wallet_class == "paying" and (evidence or "").strip():
        return _MONETIZATION_GUIDANCE["paying"]
    if wallet_class == "mixed" and wallet_evidence_shows_real_prices(wallet_class, evidence):
        return _MONETIZATION_GUIDANCE["mixed-priced"]
    return _MONETIZATION_GUIDANCE.get(wallet_class, _MONETIZATION_GUIDANCE_UNKNOWN)


def _incumbent_density_challenge(incumbent_count: int, priced_count: int) -> str:
    """Incumbent-map probe (2026-07-10): a web-verified count of tools already serving this
    niche — a Phase-1 signal, not a validated competitive audit. Deep Research does the real
    competitive analysis."""
    return (
        f"The niche already runs a dense tool ecosystem ({incumbent_count} tools web-verified, "
        f"{priced_count} with published pricing) — new products compete for attention inside an "
        "existing stack. Thin early signal; Deep Research validates."
    )


_SERP_OWNED_CHALLENGE = (
    "Most distribution-angle concepts face SERPs already owned by authorities/incumbents — "
    "organic discovery is an uphill route here. Thin early signal; Deep Research validates."
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


_AUDIENCE_STOPWORDS = {
    "a", "an", "and", "across", "for", "high", "in", "of", "the", "their",
    "to", "with", "workflow", "workflows", "seeking", "managing", "needing",
}
_AUDIENCE_TOKEN_ALIASES = {
    "clinics": "provider",
    "clinic": "provider",
    "hospitals": "provider",
    "hospital": "provider",
    "practices": "provider",
    "practice": "provider",
    "veterinarians": "veterinary",
    "veterinarian": "veterinary",
    "vets": "veterinary",
    "vet": "veterinary",
    "locations": "location",
    "sites": "location",
    "site": "location",
    "multilocation": "multi",
    "multiple": "multi",
    "singlelocation": "single",
    "generalist": "general",
    "specialist": "specialty",
}
_AUDIENCE_CONTRADICTIONS = (
    ({"single"}, {"multi", "corporate", "group", "network", "chain"}),
    ({"independent"}, {"corporate", "enterprise"}),
    ({"general"}, {"specialty", "emergency", "referral"}),
)


def _audience_tokens(value: Optional[str]) -> set[str]:
    """Normalize wording while preserving buyer-defining qualifiers."""
    collapsed = re.sub(r"(?<=\w)[-/](?=\w)", "", (value or "").lower())
    raw = re.findall(r"[a-z0-9]+", collapsed)
    return {
        _AUDIENCE_TOKEN_ALIASES.get(token, token)
        for token in raw
        if token not in _AUDIENCE_STOPWORDS
    }


def _audiences_align(left: Optional[str], right: Optional[str]) -> bool:
    """Conservative semantic match for labels, not a fuzzy substring guess."""
    left_tokens = _audience_tokens(left)
    right_tokens = _audience_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    for first, second in _AUDIENCE_CONTRADICTIONS:
        if ((left_tokens & first and right_tokens & second)
                or (left_tokens & second and right_tokens & first)):
            return False
    overlap = len(left_tokens & right_tokens)
    containment = overlap / min(len(left_tokens), len(right_tokens))
    union = overlap / len(left_tokens | right_tokens)
    return containment >= 0.6 or union >= 0.45


def _source_segment(candidate) -> str:
    if isinstance(candidate, str):
        return candidate.strip()
    if isinstance(candidate, dict):
        return str(candidate.get("source_segment") or "").strip()
    return str(getattr(candidate, "source_segment", None) or "").strip()


def detect_recommendation_audience_drift(
    requested_audience: Optional[str],
    dossier_primary_segment: Optional[str],
    recommended_candidates,
) -> Optional[AudienceDriftNotice]:
    """Compare requested -> dossier primary -> RECOMMENDED candidate provenance.

    ``recommended_candidates`` is intentionally already recommendation-scoped. Passing the
    whole candidate pool would recreate the bug this contract prevents. The notice fires only
    when at least two of the three normalized relationships disagree, which keeps harmless
    wording changes quiet while still catching a recommendation that follows a different buyer.
    """
    requested = (requested_audience or "").strip()
    primary = (dossier_primary_segment or "").strip()
    sources = list(dict.fromkeys(
        source for source in (_source_segment(item) for item in (recommended_candidates or []))
        if source
    ))
    if not requested or not primary or not sources:
        return None

    relationships = (
        _audiences_align(requested, primary),
        all(_audiences_align(requested, source) for source in sources),
        all(_audiences_align(primary, source) for source in sources),
    )
    if sum(not agrees for agrees in relationships) < 2:
        return None

    recommended = "; ".join(sources)
    message = (
        f'You asked to reach “{requested}”. The dossier centers “{primary}”, while the '
        f'recommendation is built for “{recommended}”. Validate that buyer shift before '
        "funding or building the recommendation."
    )
    return AudienceDriftNotice(
        requested_audience=requested,
        dossier_primary_segment=primary,
        recommended_source_segments=sources,
        message=message,
    )


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
    audience_drift_notice: Optional[AudienceDriftNotice] = None
    # Willingness-to-pay signals from the pains' commercial intent (None = no pains carried it)
    commercial_intent_max: Optional[float] = None
    high_commercial_share: Optional[float] = None
    # Deterministic buyer evidence for the buyer-class narration: Stage-4 segment names with
    # their budget sensitivity (+ wallet class when payability ran), words only (None = no
    # audience mapping available).
    segment_budget_brief: Optional[str] = None
    # Mean evidence-blended segment payability (None = payability not scored this run)
    segment_payability_mean: Optional[float] = None
    # Web-verified competition signals aggregated from the parity + adjacent probes
    # (2026-07-06): shares over the FINAL idea set. substitute = a free/DIY route already
    # delivers the outcome; verified incumbents = shipped/partial parity; adjacent = a
    # commercial product monetizes the mechanism in an audience-independent market.
    substitute_share: float = 0.0
    verified_incumbent_share: float = 0.0
    adjacent_incumbent_share: float = 0.0
    # Share of ideas whose buyer USES them episodically / one-shot (tags.usage_cadence)
    episodic_usage_share: float = 0.0
    # Niche wallet probe (2026-07-09): community spend-norm classification from
    # `_niche_wallet_brief` (paying|mixed|free-culture), None when the probe didn't run.
    wallet_class: Optional[str] = None
    wallet_evidence: Optional[str] = None
    # Incumbent-map probe (2026-07-10): web-verified tool count + how many carry published
    # pricing, from the `incumbent_map` rows (None = the probe didn't run).
    incumbent_count: Optional[int] = None
    priced_count: Optional[int] = None
    # SERP-ownership probe (2026-07-10): share of distribution/SEO-angle ideas stamped
    # SERP-owned (None = the probe didn't run).
    serp_owned_share: Optional[float] = None
    difficulty_level: str = "medium"
    low_confidence: bool = False
    flags: list[str] = Field(default_factory=list)
    #: Frictions only. Never mixed with strengths — see the key-points block in the builder.
    key_points: list[str] = Field(default_factory=list)
    key_strengths: list[str] = Field(default_factory=list)


# Closed vocabulary for the niche's buyer class (who actually pays here), and the payability
# tier each class implies. LLM-classified in the narrative call, vocab-validated post-call.
BUYER_CLASSES = ("budgeted-business", "smb-operator", "prosumer", "indie-hobbyist",
                 "consumer", "mixed")
_BUYER_CLASS_PAYABILITY = {
    "budgeted-business": "high", "smb-operator": "medium", "mixed": "medium",
    "prosumer": "low", "indie-hobbyist": "low", "consumer": "low",
}
_BUYER_CLASS_NOTES = {
    "budgeted-business": "Buyers here are businesses with real budget authority — direct paid "
                         "pricing is viable.",
    "smb-operator": "Buyers here are small-business operators — price-aware but used to paying "
                    "for tools that save time or win customers.",
    "mixed": "Buyers here span several wallet types — pick the segment with budget authority "
             "and price for it.",
    "prosumer": "Buyers here are prosumers paying out of pocket — expect low price ceilings "
                "and high churn on subscriptions.",
    # "free-tool distribution" stays deleted (it is the zero-price prescription D1 is about);
    # the two PAID shapes it sat beside are restored — neither contradicts a paying wallet.
    "indie-hobbyist": "Buyers here are indie/hobbyist builders spending personal money "
                      "episodically — historically a low-price-ceiling segment, and the person "
                      "who uses the tool is the person whose own money funds it; favor one-time "
                      "pricing or an adjacent buyer with budget.",
    "consumer": "Buyers here are consumers — low price points and high support load, and the "
                "products already serving them carry a wide range of commercial shapes.",
}


# A verified paying wallet contradicts the generic consumer/indie payability notes, so those two
# classes get a reconciled note instead. They are module constants because the publication
# contract has to recognise them as sanctioned statements, not re-derive them from prose.
_PAYING_WALLET_CONSUMER_BUYER_NOTE = (
    "The end user may be a consumer, but verified niche pricing shows that buyers already "
    "fund tooling. Validate whether the paying customer is the user, an organization, or "
    "an adjacent sponsor before choosing the pricing model."
)
_PAYING_WALLET_INDIE_BUYER_NOTE = (
    "The end user may be an indie or hobbyist buyer, while verified niche pricing shows "
    "that paid tooling already exists. Validate whether the paid customer is the user, a "
    "team, or an adjacent buyer."
)


# The narrative of last resort, used when every richer path has failed. It is deterministic copy
# this module authors, so the sanctioned list below has to recognise it — otherwise the minimal
# fallback hands back a verdict that fails the very invariant it exists to satisfy.
_MINIMAL_PAYING_WALLET_NARRATIVE = (
    "This niche has verified paying buyers. Validate which pain and paid wedge will convert."
)


_PAYING_WALLET_MONETIZATION_DIRECTIVE = (
    "MONETIZATION DIRECTIVE: verified prices show buyers already pay for tooling. Paid pricing, "
    "including subscription pricing, remains viable. Match pricing to the addressed pain and "
    "validate which paid wedge will convert."
)


# The WTP ladder the generator prices against. It is deliberately SHAPE-BLIND: it names the
# evidence a pricing choice has to rest on and refuses the house default, without nominating a
# commercial shape of its own. The previous ladder lived hard-coded in
# `unified_solution_tasks.yaml` and in `_refine_single_concept`, where a wallet reading could not
# reach it; those copies are deleted and this is the single source (D1 round 15, Priority 3).
_MONETIZATION_WTP_LADDER = (
    "Read the addressed pain's WTP (shown as \"WTP x/10\" in the pain block above) and match the "
    "monetization model to THAT number rather than to a house default: at WTP >= 5/10 the buying "
    "signal is real and paid pricing needs no special justification; below it, whichever model "
    "you pick has to name the evidence behind it in the rationale. Never fall back on \"Freemium "
    "with 3 tiers\"."
)


def derive_monetization_directive(pains, segments, niche_wallet_brief=None) -> str:
    """A deterministic, PRE-ideation monetization prior for the pricing prompt, from the same
    signals assess_niche_difficulty uses (segment payability mean + pain commercial-intent) — NOT
    the LLM-classified buyer_class, which doesn't exist yet at ideation time. The per-pain WTP stays
    the override so a mostly-weak niche's one genuinely commercial pain can still price as a
    subscription (avoids over-suppression on mixed niches).

    A wallet brief whose EVIDENCE carries literal prices takes precedence over every corpus-derived
    branch below, `mixed` included: the contradiction D1 names is quoting a niche's real prices in
    one paragraph and steering the generator away from charging in the next, and the bucket the
    classifier chose is not what makes that a contradiction — the prices are. Callers that omit the
    brief silently lose this branch, which is how the paying-wallet directive stayed unreachable in
    production for a whole round; both production call sites now pass it.
    """
    wallet = niche_wallet_brief or {}
    wallet_class = (wallet.get("wallet_class") or "").strip().lower()
    wallet_evidence = (wallet.get("evidence") or "").strip()
    if (wallet_class == "paying" and wallet_evidence) or wallet_evidence_shows_real_prices(
        wallet_class, wallet_evidence
    ):
        return f"{_PAYING_WALLET_MONETIZATION_DIRECTIVE} {_MONETIZATION_WTP_LADDER}"

    ci_present = [c for c in (getattr(p, "commercial_intent", None) for p in (pains or []))
                  if isinstance(c, (int, float))]
    commercial_intent_max = max(ci_present) if ci_present else None
    has_commercial_pain = commercial_intent_max is not None and commercial_intent_max >= 0.6

    pay_scores = [p for p in (getattr(s, "payability_score", None) for s in (segments or []))
                  if isinstance(p, (int, float))]
    payability_mean = (sum(pay_scores) / len(pay_scores)) if pay_scores else None
    weak_wallet = payability_mean is not None and payability_mean < PAYABILITY_WEAK_MEAN
    mean_clause = f" (mean segment payability {payability_mean:.2f})" if payability_mean is not None else ""

    override = ("Subscription is correct and expected for an idea whose addressed pain shows "
                "WTP ≥ 5/10 — key that exception to the WTP number, and never blanket-refuse a "
                "recurring model.")

    if weak_wallet and not has_commercial_pain:
        return ("MONETIZATION DIRECTIVE — weak-wallet niche" + mean_clause + ": buyers pay out of "
                "pocket with low price ceilings, and no pain in this run crosses the "
                "commercial-intent bar. That is the evidence, not a verdict on the shape. "
                + _MONETIZATION_WTP_LADDER + " " + override)
    if weak_wallet and has_commercial_pain:
        return ("MONETIZATION DIRECTIVE — mostly weak-wallet niche" + mean_clause + " with a few "
                "genuinely commercial pains: the wallet evidence is thin overall and strong on "
                "those pains. " + _MONETIZATION_WTP_LADDER + " " + override)
    if payability_mean is not None:
        return ("MONETIZATION DIRECTIVE — wallets look viable" + mean_clause + ": price to the "
                "addressed pain's WTP; direct paid / subscription pricing is on the table where WTP "
                "supports it. " + _MONETIZATION_WTP_LADDER)
    return ("MONETIZATION DIRECTIVE: match pricing to the addressed pain's WTP (shown as WTP x/10) "
            "and project type — freemium subscription is not the automatic answer for every idea. "
            + _MONETIZATION_WTP_LADDER)


class NicheDifficultyNarrative(BaseModel):
    """LLM output. The headline is LLM-written but its RATING word is fixed by the band (validated
    below), so it stays in sync while still being tailored to the niche."""

    headline: str = Field(
        ..., description="Verdict line, EXACTLY 'Software Fit: <fixed rating> — <niche-specific clause>'"
    )
    narrative_summary: str = Field(..., description="2-4 sentence candid verdict")
    buyer_class: str = Field(
        "", description="EXACTLY one of: budgeted-business | smb-operator | prosumer | "
                        "indie-hobbyist | consumer | mixed"
    )


def _facts_only(points: list[str], *, label: str) -> list[str]:
    """Drop any deterministic point that PRESCRIBES a commercial shape rather than stating one.

    The fact pack is where the contradiction becomes structural: its `key_points` are rendered as
    `key_challenges` AND interpolated verbatim into the verdict prompt, so one prescribing string
    reaches the reader and the model at once, and no downstream filter can withdraw it. Every
    module-level constant that can land here is enforced clean by
    tests/unit/test_niche_difficulty_constants_are_facts.py — but this function also appends
    INLINE literals, and the next one added will not be a constant for that test to enumerate. So
    the list is validated where it is built rather than trusted, which is the half of the guard
    that does not depend on a string having a name.

    A dropped point is logged at ERROR: reaching this is a code defect, not a data condition.
    """
    kept = []
    for point in points:
        violations = _paying_wallet_copy_rule_labels(point)
        if violations:
            logger.error(
                f"[Niche Difficulty] deterministic {label} entry prescribes a commercial shape "
                f"({violations}); dropping it: {point[:120]!r}"
            )
            continue
        kept.append(point)
    return kept


def _share(items, predicate) -> float:
    if not items:
        return 0.0
    return sum(1 for it in items if predicate(it)) / len(items)


def _median(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def assess_niche_difficulty(
    pains, ideas, niche_context, concept_duplication_rate: Optional[float] = None,
    segments=None, niche_wallet_brief: Optional[dict] = None,
    incumbent_map: Optional[list[dict]] = None, serp_owned_share: Optional[float] = None,
    dossier_primary_segment: Optional[str] = None, recommended_candidates=None,
) -> Optional[NicheDifficultyFactPack]:
    """Classify niche software-fit difficulty from persisted signals.

    `concept_duplication_rate` (optional) is the share of brainstormed concepts the novelty
    critic flagged as already-existing — a tool-ecosystem saturation signal the surviving ideas
    can't show. `segments` (optional) are the Stage-4 audience segments — their names + budget
    sensitivity become the buyer-class evidence brief. `recommended_candidates` must contain
    only the recommendation, never the whole pool; together with the requested audience and
    dossier primary it drives the drift notice. `niche_wallet_brief` (optional) is the
    niche wallet probe's `{wallet_class, evidence, free_density}` dict — `free-culture` surfaces a
    caution key_point (unless the substitute/WTP challenges already cover it), `paying` surfaces a
    positive/neutral key_point, `mixed` surfaces nothing. `incumbent_map` (optional) is a list of
    web-verified competitor rows (`{name, pricing, focus, gap, source}`) — a dense count (>=
    TOOLING_DENSE) surfaces a caution key_point about an already-crowded tool ecosystem.
    `serp_owned_share` (optional) is the fraction of distribution/SEO-angle ideas stamped
    SERP-owned by the probe — a heavy share (>= SERP_OWNED_HEAVY) surfaces a caution key_point
    about organic-discovery difficulty. All three are None by default (probe didn't run), which
    reproduces today's output byte-identically. Returns None only when there is nothing to judge
    (no pains AND no ideas), so the caller can leave the field null and the UI hides the section.
    """
    pains = pains or []
    ideas = ideas or []
    if not pains and not ideas:
        return None

    crowding = derive_market_crowding_brief(
        pains, segments, niche_wallet_brief, incumbent_map)

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

    requested_audience = (
        getattr(niche_context, "user_target_audience", None) if niche_context else None
    )
    if not dossier_primary_segment and segments:
        dossier_primary_segment = getattr(segments[0], "segment_name", None)

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

    # Buyer evidence brief: segment names + budget sensitivity (+ evidence-blended wallet class
    # when payability ran), words only for the LLM; the numeric mean stays a fact-pack field.
    segment_budget_brief = None
    seg_lines = []
    pay_scores = []
    for s in (segments or [])[:5]:
        name = (getattr(s, "segment_name", "") or "").strip()
        if not name:
            continue
        budget = (getattr(s, "budget_sensitivity", "") or "unknown").strip()
        pay = getattr(s, "payability_score", None)
        pay_cls = getattr(s, "payability_class", None)
        if isinstance(pay, (int, float)):
            pay_scores.append(pay)
        wallet = f"; wallet: {pay_cls}" if pay_cls else ""
        seg_lines.append(f"{name} (budget sensitivity: {budget}{wallet})")
    if seg_lines:
        segment_budget_brief = "; ".join(seg_lines)
    segment_payability_mean = round(sum(pay_scores) / len(pay_scores), 2) if pay_scores else None

    # Web-verified competition + usage-shape aggregates (2026-07-06): shares over the FINAL
    # idea set from the parity/adjacent probes and the usage_cadence tag.
    substitute_share = _share(
        ideas, lambda i: str(getattr(i, "incumbent_parity", "") or "").startswith("substitute"))
    verified_incumbent_share = _share(
        ideas, lambda i: str(getattr(i, "incumbent_parity", "") or "").startswith(("shipped", "partial")))
    adjacent_incumbent_share = _share(
        ideas, lambda i: bool(getattr(i, "adjacent_market_parity", None)))
    episodic_usage_share = _share(
        ideas, lambda i: getattr(getattr(i, "tags", None), "usage_cadence", None)
        in ("episodic", "one-shot"))

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
    if audience_scope == "too_broad":
        flags.append("scope")
        challenges.append(
            "The stated audience is too broad to support one coherent buyer recommendation — "
            "tighten the wedge before choosing a product."
        )
    # `detect_recommendation_audience_drift` compares WORDING, and its message used to land in
    # `key_points` -> `key_challenges`, which `NicheRealityCheck` renders. So the run shipped two
    # differently-worded buyer warnings authored by two different comparators, and the wording one
    # reached the reader on 12 of the 14 runs where the typed axes find no stated difference at
    # all. Read the three phrases on typed buyer axes instead, and let that notice be the only one
    # anybody sees. The lexical comparator is no longer called from this module at all.
    #
    # `key_challenges` gets the POINTER, not the message: this list is niche-scoped on the public
    # share boundary while `audience_drift_notice` is pool-scoped, so the message itself would be
    # served verbatim on the stale-pool path that withholds both labelled copies of it. See
    # `audience_axes.AUDIENCE_DRIFT_CHALLENGE`. `_refresh_recommendation_audience_drift` in the
    # flow re-strips and re-appends the same pointer, so both surfaces share one snapshot time.
    from .audience_axes import AUDIENCE_DRIFT_CHALLENGE
    from .audience_axes import detect_audience_drift as _detect_typed_audience_drift

    audience_drift_notice = _detect_typed_audience_drift(
        requested_audience, dossier_primary_segment, recommended_candidates
    )
    if audience_drift_notice is not None:
        flags.append("audience_drift")
        challenges.append(AUDIENCE_DRIFT_CHALLENGE)
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

    # --- Key points, split by polarity.
    # These used to share one bidirectional `key_points` list surfaced as `key_challenges`.
    # The conditional appends below fire on a STRONG niche too, so that single list came out
    # genuinely mixed — and every consumer then had to guess. ReportBrief guessed "risk" and
    # printed "There's room for a genuinely novel angle" as the primary concern. Keep the two
    # polarities apart here, where each point's sign is known for certain.
    key_strengths: list[str] = []
    if difficulty == "low" or software_addressability >= ADDR_STRONG:
        if full_share >= FULL_SHARE_STRONG:
            key_strengths.append(
                "Most pains are workflow or data problems a tool can directly own."
            )
        if (median_novelty or 0.0) >= NOVELTY_LOW:
            key_strengths.append("There's room for a genuinely novel angle, not just a clone.")
        if cold_start_share < COLD_START_HEAVY:
            key_strengths.append("Usable data is reachable without a heavy cold-start lift.")
    # Frictions always survive. The old single list computed `strengths or challenges`, so on a
    # strong-fit niche the computed frictions were dropped outright — including the ones that had
    # just escalated the difficulty band. That was a workaround for having one list to fill; with
    # two, a strong niche can show both its strengths and what still makes it hard.
    key_points = list(challenges)

    # Saturation is orthogonal to fit — surface it even when the verdict is otherwise strong
    # ("great data + clear pains, but a mature tool ecosystem").
    if saturated and _SATURATION_CHALLENGE not in key_points:
        key_points = [*key_points, _SATURATION_CHALLENGE]

    wallet_class = (niche_wallet_brief or {}).get("wallet_class")
    wallet_evidence = ((niche_wallet_brief or {}).get("evidence") or "").strip()
    wallet_is_verified_paying = wallet_class == "paying" and bool(wallet_evidence)

    # Reconcile corpus purchase intent with the web-verified wallet before either signal reaches
    # user-facing prose. This is informational only and never changes the difficulty band.
    weak_wtp_judgment = None
    if commercial_intent_max is not None and commercial_intent_max < 0.6:
        weak_wtp_judgment = _wtp_judgment(
            commercial_intent_max,
            high_commercial_share,
            wallet_class,
            wallet_evidence,
        )
        key_points = [*key_points, weak_wtp_judgment]

    # Web-verified competition + usage-shape notes (2026-07-06): informational appends in the
    # same spirit — they never touch the band or the escalation flags.
    if substitute_share >= SUBSTITUTE_HEAVY:
        key_points = [*key_points, _SUBSTITUTE_CHALLENGE]
    if verified_incumbent_share >= INCUMBENT_DENSE:
        key_points = [*key_points, _INCUMBENT_DENSE_CHALLENGE]
    if (adjacent_incumbent_share >= ADJACENT_MONEY
            and segment_payability_mean is not None
            and segment_payability_mean < PAYABILITY_WEAK_MEAN):
        # The strategic inversion: mechanisms proven to monetize elsewhere + weak wallets HERE.
        key_points = [*key_points, _ADJACENT_MONEY_CHALLENGE]
    if episodic_usage_share >= EPISODIC_HEAVY and weak_wtp_judgment not in key_points:
        # Usage shape, distinct from buying signals; skip when the WTP challenge already carries
        # the monetization-shape advice (two pricing warnings read as nagging).
        key_points = [*key_points, _EPISODIC_CHALLENGE]

    # Niche wallet probe (2026-07-09): a 'free-culture' spend norm is a Phase-1 signal that a
    # paid wedge must beat the free route. Skip the append when the substitute/WTP challenges
    # already carry that warning (two "buyers won't pay" notes read as nagging).
    if (
        wallet_class == "free-culture"
        and _SUBSTITUTE_CHALLENGE not in key_points
        and weak_wtp_judgment not in key_points
    ):
        key_points = [*key_points, _wallet_challenge(wallet_evidence)]
    elif wallet_is_verified_paying:
        # Positive/neutral signal: buyers here already pay for tooling. 'mixed' (and any other
        # reading) adds nothing — neutral default. Goes to strengths: it is the one append in
        # this block that is not a friction.
        key_strengths = [*key_strengths, _wallet_positive_note(wallet_evidence)]

    # Incumbent-map probe (2026-07-10): a dense web-verified tool count is a caution signal —
    # new entrants compete for attention inside an existing stack, not an empty field.
    incumbent_count = crowding.incumbent_count if incumbent_map else None
    priced_count = crowding.priced_count if incumbent_map else None
    if crowding.key_point:
        key_points = [*key_points, crowding.key_point]

    # SERP-ownership probe (2026-07-10): a heavy share of distribution-angle ideas facing
    # already-owned SERPs is a caution signal about organic-discovery difficulty.
    if serp_owned_share is not None and serp_owned_share >= SERP_OWNED_HEAVY:
        key_points = [*key_points, _SERP_OWNED_CHALLENGE]

    return NicheDifficultyFactPack(
        n_pains=len(pains),
        n_ideas=len(ideas),
        key_points=_facts_only(key_points, label="key_points"),
        key_strengths=_facts_only(key_strengths, label="key_strengths"),
        commercial_intent_max=commercial_intent_max,
        high_commercial_share=high_commercial_share,
        segment_budget_brief=segment_budget_brief,
        segment_payability_mean=segment_payability_mean,
        substitute_share=round(substitute_share, 3),
        verified_incumbent_share=round(verified_incumbent_share, 3),
        adjacent_incumbent_share=round(adjacent_incumbent_share, 3),
        episodic_usage_share=round(episodic_usage_share, 3),
        wallet_class=wallet_class,
        wallet_evidence=wallet_evidence or None,
        incumbent_count=incumbent_count,
        priced_count=priced_count,
        serp_owned_share=(round(serp_owned_share, 3) if serp_owned_share is not None else None),
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
        audience_drift_notice=audience_drift_notice,
        difficulty_level=difficulty,
        low_confidence=low_confidence,
        flags=flags,
    )


# FIT language comes from the ADDRESSABILITY band, not the difficulty band. difficulty_level
# measures overall difficulty INCLUDING frictions (cold-start, saturation, calibration) and its
# ≥2-flags escalation can push a strong-fit niche to "high" — mapping THAT to "Software Fit:
# Limited" printed a contradiction next to an 88% addressability meter (codex-review finding,
# 2026-07-02). Fit rating = can software address the pains; frictions color the clause/key points.
_FIT_HEADLINES = {
    "strong": "Software Fit: Strong. A tool can directly own these pains",
    "moderate": "Software Fit: Moderate. A useful tool, with real caveats",
    "limited": "Software Fit: Limited. Software mostly advises here",
    "very limited": "Software Fit: Hard. Software can only sit beside the problem",
}

# The one rating word per addressability band. The LLM writes the headline but must use this exact
# word, so the headline can never drift out of sync with the classified fit (validated post-call).
_FIT_RATING = {"strong": "Strong", "moderate": "Moderate", "limited": "Limited",
               "very limited": "Hard"}


_WEAK_WTP_CHALLENGE = (
    "No pain in this run crosses the buying-signal bar. Treat this as a corpus evidence gap "
    "about what the captured discussions recorded, not as a settled verdict on the market."
)

# The pre-2026-08-10 wording of the statement above. It survives ONLY so a checkpoint persisted
# under the old prose is still recognised as the same finding on resume; nothing writes it.
_LEGACY_WEAK_WTP_MARKER = "No pain shows strong buying signals"

_PAYING_WALLET_CORPUS_CHALLENGE = (
    "The captured discussions in this run contain no explicit purchase intent. Treat this as a "
    "corpus evidence gap, not proof of weak market willingness to pay: web-verified prices show "
    "buyers already pay for tooling, so subscription pricing remains viable. Validate which pain "
    "and paid wedge will convert. Thin early signal; Deep Research validates."
)


def _wtp_judgment(
    commercial_intent_max,
    high_commercial_share,
    wallet_class=None,
    wallet_evidence=None,
) -> str:
    """Reconcile corpus purchase intent with the web-verified wallet reading."""
    if commercial_intent_max is None:
        return "n/a"
    if commercial_intent_max < 0.6:
        if wallet_class == "paying" and wallet_evidence:
            return _PAYING_WALLET_CORPUS_CHALLENGE
        return _WEAK_WTP_CHALLENGE
    if (high_commercial_share or 0.0) >= 0.25:
        return ("Strong corpus purchase-intent signal: buyers carry purchase intent across "
                "several pains; "
                "direct paid pricing is viable")
    return ("Moderate corpus purchase-intent signal: some pains carry real buying intent; a "
            "paid tier is plausible if it "
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
        if fp.difficulty_level in ("high", "very_high"):
            lead += (
                " Overall difficulty still rates high — that's frictions (cold start, "
                "crowded tooling), not a worse fit; see the factors below."
            )
    if fp.key_points:
        lead += " " + fp.key_points[0]
    if fp.low_confidence:
        lead += " (Limited sample — treat as directional.)"
    return _fit_headline(fp.software_addressability), lead


_PAYING_WALLET_FORBIDDEN_COPY = (
    (
        "anti-subscription prescription",
        re.compile(
            r"\b(?:avoid|skip|reject|rule out|do not use|don't use|not)\b.{0,40}"
            r"(?:\bsubscription(?:\s+(?:pricing|saas))?\b"
            # The same prescription without the word "subscription": what a subscription IS.
            r"|\b(?:ongoing|recurring|monthly|repeating)\s+(?:fees?|charges?|billing|payments?)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "zero-price prescription",
        re.compile(
            r"\b(?:charge|bill|price)\s+(?:it\s+|them\s+|nothing\s+)?(?:nothing|zero|\$\s?0)\b"
            r"|\bkeep\s+the\s+(?:ask|price|charge)\s+at\s+zero\b",
            re.IGNORECASE,
        ),
    ),
    (
        "subscription declared non-viable",
        re.compile(
            r"\bsubscription(?:\s+(?:pricing|saas))?\b.{0,30}"
            r"\b(?:not viable|unviable|off the table)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "free-tool-only prescription",
        re.compile(
            r"(?:\b(?:build|use|offer|make|ship|plan|focus on|default to|stick to)\b"
            r".{0,40}\b(?:only|just)\b.{0,30}\bfree(?:[- ]tool)?\b|"
            r"\b(?:only|just)\b.{0,30}\b(?:a\s+)?free[- ]tool\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "market willingness to pay declared weak",
        re.compile(
            r"(?:\b(?:weak|low|little|no|zero)\b(?:[- ]|\s+)(?:market\s+)?"
            r"willingness[- ]to[- ]pay\b|\bwillingness[- ]to[- ]pay\b.{0,35}"
            r"\b(?:is|looks|remains|seems)\s+(?:weak|low|absent|nonexistent)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "buyers declared unwilling to pay",
        re.compile(
            r"\b(?:buyers?|customers?|the market)\b.{0,35}"
            r"\b(?:will not|won't|do not|don't)\s+pay\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "free-only buyer-class prescription",
        re.compile(
            r"\b(?:monetizes?|monetization)\b.{0,70}\b(?:stays?|remains?)\s+free\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        # Prescribing sponsor/ad/tip-jar funding INSTEAD of charging is the same conclusion as
        # "they won't pay", reached without a negative word. It belongs in the rule list rather
        # than the topic boundary: it is a named commercial prescription, not a vocabulary.
        "sponsor-funded free distribution prescribed",
        re.compile(
            r"\b(?:sponsor\w*|ad[- ](?:supported|funded)|advertis\w*|affiliate|tip[- ]jar|"
            r"underwrit\w*)\b.{0,120}?"
            r"\b(?:free|no[- ]charge|open to everyone|hosting bill)\b"
            r"|\b(?:free|no[- ]charge|open to everyone)\b.{0,120}?"
            r"\b(?:sponsor\w*|ad[- ](?:supported|funded)|advertis\w*|affiliate|tip[- ]jar|"
            r"underwrit\w*)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)

# Portfolio prose remains free-form, but its commercial stance does not. Once every SANCTIONED
# statement is removed, any remaining wallet/pricing vocabulary means the model wrote a second,
# unconstrained commercial claim. This is a topic boundary, not a negative-phrase list.
#
# The boundary must stay polarity-blind on purpose: it does not try to decide whether a novel
# money sentence is positive or negative, it simply refuses to publish any money sentence the
# codebase did not author. An allowlist that accepts a sentence merely for containing
# "buyers ... pay" is defeated by paraphrase, because a negative claim about money mentions
# money too.
#
# AUDIENCE NOUNS ARE NOT MONEY WORDS. "buyers", "customers", "sellers", "selling", "sold" name
# who the run is about, not a stance about their wallets ("home bakers selling cakes" cost a
# whole real narrative). Every genuine commercial claim about them carries a money word too
# ("buyers won't pay", "no money in this audience"), so dropping the audience nouns removes
# false positives without opening a hole.
_COMMERCIAL_COPY_TOPIC_RE = re.compile(
    r"\b(?:afford\w*|bill\w*|budget\w*|cards?|charg\w*|checkbooks?|churn\w*|costs?|"
    r"discount\w*|dollars?|expens\w*|fees?|free|invoic\w*|licen[cs]e[sd]?|"
    r"monet[iy][sz]\w*|money|monies|monthly|paid|pay\w*|price[sd]?|pricing|procurement|"
    r"purchas\w*|recurring|renew\w*|retainers?|revenue|spend\w*|sponsor\w*|subscri\w*|"
    r"tiers?|unpaid|upsell\w*|wallets?|willingness[- ]to[- ]pay)\b"
    r"|\bone[- ](?:time|off)\b|\bper[- ](?:seat|user|head|incident|unit)\b|\bline item\b"
    # Registers a wallet claim reaches for once the plain money nouns are watched.
    r"|\b(?:commercial|buying|purchase|spending)\s+appetite\b"
    r"|\bappetite\s+to\s+(?:pay|spend|buy)\b"
    # "plan" is only commercial in its pricing sense; "plan a cold-start play" and "the team
    # plans a migration" are not commercial claims.
    r"|\b(?:annual|basic|billing|enterprise|entry|free|growth|monthly|paid|payment|premium|"
    r"price|pricing|quarterly|recurring|seat|starter|subscription|tiered?|usage[- ]based|"
    r"yearly)[\s-]plans?\b",
    re.IGNORECASE,
)

# A PRICE is the most commercial thing a string can carry, and it carries no money NOUN.
# "$29-$99/mo; nobody upgrades" rode into the sanctioned statement's evidence slot on exactly
# this gap: the refusal was visible, the topic was not.
#
# Deliberately NOT part of the topic boundary above. A bare price list is what the evidence slot
# is FOR — "$99-399/mo DaySmart Vet" is the proof the contract rests on — so a price must not
# make a string a commercial claim the codebase did not author. It counts only for the
# polarity-AWARE tests, which additionally require an absence/refusal marker.
_MONEY_TOKEN_RE = re.compile(
    _COMMERCIAL_COPY_TOPIC_RE.pattern
    + r"|\$\s?\d|\b\d+(?:[.,]\d+)?\s?(?:/|per\s+)(?:mo\b|month|yr\b|year|seat|user|head|"
      r"unit|incident)"
      r"|\b\d+\s?(?:usd|eur|gbp|dollars?|euros?)\b",
    re.IGNORECASE,
)

_PAYING_WALLET_VERDICT_NEGATIVE_PARAPHRASE = re.compile(
    r"\b(?:subscriptions?|recurring\s+billing|paid\s+(?:pricing|model))\b.{0,50}"
    r"\b(?:will\s+not|won't|cannot|can't)\s+(?:work|sell|convert)\b",
    re.IGNORECASE | re.DOTALL,
)

_WILLINGNESS_TO_PAY_RE = re.compile(r"willingness[- ]to[- ]pay", re.IGNORECASE)


def _normalized_commercial_copy(copy: str) -> str:
    """Collapse the punctuation generations one deterministic statement has shipped under.

    ``_without_long_dashes`` rewrites " — " to ": ", so the same sanctioned sentence exists on
    disk in two forms, and "willingness to pay" / "willingness-to-pay" likewise. Normalizing
    both sides lets a sanctioned statement be recognised as a whole statement instead of as a
    loose neighbourhood of keywords.
    """
    return re.sub(r"\s+", " ", _WILLINGNESS_TO_PAY_RE.sub(
        "willingness-to-pay", _without_long_dashes(copy)
    )).strip()


# The sanctioned CONCLUSION, not token co-occurrence. Each entry is a statement this codebase
# authors deterministically; the evidence/count slots are the only free text they carry.
#
# The parenthetical is a FREE-TEXT SLOT filled from model-produced probe evidence, so it is
# captured as ``slot`` rather than swallowed: ``_unsanctioned_commercial_residue`` puts it back
# into the residue to be scanned. Deleting it unscanned let a whole contradicting sentence ride
# inside the one statement the contract rests on.
_SANCTIONED_WALLET_NOTE_RE = re.compile(
    r"Buyers in this niche demonstrably pay for tooling(?: \((?P<slot>[^()]{0,240})\))?: "
    r"willingness-to-pay is not the primary risk\."
    r"(?: Thin early signal; Deep Research validates\.)?",
    re.IGNORECASE,
)
_SANCTIONED_INCUMBENT_DENSITY_RE = re.compile(
    r"The niche already runs a dense tool ecosystem \(\d+ tools web-verified, \d+ with "
    r"published pricing\): new products compete for attention inside an existing stack\."
    r"(?: Thin early signal; Deep Research validates\.)?",
    re.IGNORECASE,
)

# Short sanctioned conclusions. Unlike the whole statements above these are fragments, so they
# only sanction a string that carries no negation/absence marker of its own — otherwise
# "budget authority is absent here" would sanction itself.
_SANCTIONED_COMMERCIAL_PHRASE_RE = re.compile(
    r"\bpublished pricing\b|\bverified niche pricing\b|\bbudget authority\b|"
    r"\bsubscription pricing remains viable\b|"
    r"\bpaid pricing\b[^.]{0,40}?\b(?:viable|plausible|on the table)\b",
    re.IGNORECASE,
)

# Absence/weakness markers. Used for two jobs: deciding whether a short sanctioned fragment is
# being asserted or denied, and (with a money word) detecting a negative commercial stance.
_COMMERCIAL_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|none|nobody|non|without|lacks?|lacking|absent|missing|thin|weak|"
    r"limited|little|scarce|shallow|rare|unlikely|wrong|worse|avoid\w*|skip\w*|reject\w*|"
    r"isn't|aren't|won't|can't|cannot|doesn't|don't|didn't|hardly|barely|instead|"
    # Registers a wallet contradiction uses when it declines to say "no": litotes, euphemism,
    # and the refusal verbs that carry the negative on their own.
    r"illusory|unsigned|unpaid|zero|cancel\w*|churn\w*|cut|expire[sd]?|"
    r"refus\w*|resent\w*|reluctan\w*|stall\w*|unused|unwilling|"
    # Grade and outcome words a wallet verdict reaches for when it avoids the absence words
    # above. "willingness to pay ... is quite low" and "is likely to fail due to weak buyer
    # payability" both shipped past the earlier vocabulary because none of these were in it.
    r"low|poorly|fails?|failed|failing|struggl\w*|uphill|discourag\w*)\b"
    r"|\b(?:far from|stops? short of|anything but|walk(?:s|ed|ing)? away)\b"
    # Deferred money is money withheld. A budget cycle that clears after the need is a wallet
    # friction claim with no negative word anywhere in it.
    r"|\b(?:long after|months? (?:after|later)|next (?:fiscal|budget|planning) (?:year|cycle))\b",
    re.IGNORECASE,
)

# The subset of the markers above that can only mean a refusal to pay, never a gap in something
# else. Only these are trusted to bind a stance across a sentence boundary.
_WALLET_REFUSAL_RE = re.compile(
    r"\b(?:nobody|never|refus\w*|declin\w*|resent\w*|reluctan\w*|stall\w*|unsigned|unpaid|"
    r"won't|cannot|can't|will not)\b"
    r"|\bwalk(?:s|ed|ing)? away\b",
    re.IGNORECASE,
)

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")

# A negation binds to its own clause. "…is the clinic owner, not the vet tech" says nothing
# about the polarity of "budget authority" earlier in the sentence.
_CLAUSE_BOUNDARY_RE = re.compile(r"([.,;:!?]+)")


@lru_cache(maxsize=1)
def _sanctioned_commercial_statements() -> tuple[re.Pattern, ...]:
    """Every whole statement this module is allowed to publish about money on a paying wallet."""
    fixed = (
        _PAYING_WALLET_CORPUS_CHALLENGE,
        _PAYING_WALLET_MONETIZATION_DIRECTIVE,
        _MINIMAL_PAYING_WALLET_NARRATIVE,
        _PAYING_WALLET_CONSUMER_BUYER_NOTE,
        _PAYING_WALLET_INDIE_BUYER_NOTE,
        # The generic notes for the classes a paying wallet does NOT override. The
        # consumer/indie-hobbyist generics are deliberately absent: they assert weak
        # willingness to pay and must stay rejected here.
        _BUYER_CLASS_NOTES["budgeted-business"],
        _BUYER_CLASS_NOTES["smb-operator"],
        _BUYER_CLASS_NOTES["mixed"],
        _BUYER_CLASS_NOTES["prosumer"],
        # The persisted niche-level monetization line. It is a card string like any other, so the
        # invariant scans it; it is deterministic run-authored copy, so it must be recognised.
        *_MONETIZATION_GUIDANCE.values(),
        _MONETIZATION_GUIDANCE_UNKNOWN,
    )
    return (
        _SANCTIONED_WALLET_NOTE_RE,
        _SANCTIONED_INCUMBENT_DENSITY_RE,
        *(
            re.compile(re.escape(statement), re.IGNORECASE)
            for statement in dict.fromkeys(
                _normalized_commercial_copy(statement) for statement in fixed
            )
        ),
    )


def _sanctioned_statement_residue(match: re.Match[str]) -> str:
    """Remove a sanctioned statement's fixed words but keep its free-text slot for scanning."""
    slot = match.groupdict().get("slot") if match.re.groupindex else None
    return f" {slot} " if slot else " "


def _strip_sanctioned_phrases(residue: str) -> str:
    """Drop short sanctioned fragments from every clause that is not denying them."""
    return "".join(
        clause if _COMMERCIAL_NEGATION_RE.search(clause)
        else _SANCTIONED_COMMERCIAL_PHRASE_RE.sub(" ", clause)
        for clause in _CLAUSE_BOUNDARY_RE.split(residue)
    )


def _unsanctioned_commercial_residue(copy: str) -> str:
    """Return what remains once every sanctioned commercial statement is removed."""
    residue = _normalized_commercial_copy(copy)
    for pattern in _sanctioned_commercial_statements():
        residue = pattern.sub(_sanctioned_statement_residue, residue)
    return _strip_sanctioned_phrases(residue)


def has_unsanctioned_commercial_claim(copy: str) -> bool:
    """True when the string makes a commercial claim this codebase did not author.

    Polarity-blind deny-by-default. Correct for the VERDICT CARD, whose commercial content is
    entirely deterministic. Do not use it on the portfolio summary — see
    ``has_negative_commercial_stance``.
    """
    return bool(_COMMERCIAL_COPY_TOPIC_RE.search(_unsanctioned_commercial_residue(copy)))


# A sentence that talks about money AND about the niche as a whole is making a NICHE-LEVEL
# wallet claim — the same claim the verdict card owns deterministically, so it gets the verdict
# card's polarity-blind boundary. A sentence about one idea's pricing or payability does not.
_NICHE_SCOPE_CUE_RE = re.compile(
    r"\b(?:niche|market|categor(?:y|ies)|segment|space|vertical|trade|audience|community|"
    r"buyers?|customers?|here)\b"
    # "these operators", "those shops": a plural audience referred to as a group.
    r"|\b(?:these|those)\s+(?!tools|ideas|concepts|products|solutions|features|platforms|"
    r"options|models|companies)\w+s\b",
    re.IGNORECASE,
)

# Terms that can only ever be a verdict on THIS niche's wallet. They need no scope cue: there is
# no per-idea sense of "checkbook" or "buying signals".
_NICHE_WALLET_VERDICT_RE = re.compile(
    r"\b(?:willingness[- ]to[- ]pay|checkbooks?|money|monies|purchase intent|"
    r"budget authority|procurement|invoic\w*|retainers?|unpaid)\b"
    r"|\bbuying signals?\b",
    re.IGNORECASE,
)

# The digest hands the model per-idea SCORES and tells it to report them in words ("strong",
# "moderate", "weak market fit"). The summary echoing "weak buyer payability" for a named idea is
# quoting this pipeline's own per-idea judgement, not asserting that the niche will not pay — so
# the score vocabulary, GRADE WORD INCLUDED, leaves the residue before any niche-level claim is
# looked for. Leaving the grade behind stranded a "weak" that then read as a wallet negation.
_PER_IDEA_SCORE_VOCAB_RE = re.compile(
    r"\b(?:strong|solid|good|decent|moderate|mixed|limited|weak|low|thin|poor)?[\s-]*"
    r"(?:buyer[- ]segment|buyer|segment|personal[- ]wallet|target|overall)?[\s-]*"
    r"(?:payability|market[- ]fit|commercial intent)\b",
    re.IGNORECASE,
)

# Product names are not commercial vocabulary. "PayoutClarity" is not the verb "pay", and
# "Turnover Market Rate Map" does not make a sentence about the market.
_PRODUCT_NAME_RE = re.compile(
    r"\b\w*[a-z]\w*[A-Z]\w*\b"                     # CamelCase: PayoutClarity, QuickPayCalc
    r"|(?<![.!?]\s)(?<!^)\b(?:[A-Z][a-z]+[\s-]){1,}[A-Z][a-z]+\b",  # Title Case Multi Word
    re.MULTILINE,
)


def _commercial_sentences(residue: str) -> list[str]:
    return [sentence for sentence in _SENTENCE_BOUNDARY_RE.split(residue) if sentence.strip()]


# ---------------------------------------------------------------------------------------------
# Zero-price / alternative-funding PRESCRIPTIONS.
#
# A prescription is a negative conclusion with no valence word in it. "Pivot toward a free,
# lead-generation tool", "open-source it", "fund it from donations" all conclude that this
# audience will not be charged, and they reach that conclusion without a single word any
# polarity-keyed mechanism can see. Four previous mechanisms keyed on negative vocabulary and
# were therefore structurally blind to the entire register, which is where D1 actually lives.
#
# This detector never asks whether a sentence is positive or negative about money. It asks two
# independent questions and requires both inside ONE sentence:
#
#   OBJECT — does the sentence name a commercial shape in which this audience does not pay a
#            recurring price (free / gift / lead-gen / open source / donations / sponsorship /
#            one-time / lifetime / perpetual / zero), or does it explicitly reject the shape in
#            which they do ("rather than something the shops buy")?
#   MOOD   — is that shape being RECOMMENDED rather than reported? Recommendation is a
#            comparatively closed pragmatic register in English — imperative, deontic modal,
#            evaluative-selection frame, directional pivot — unlike the open-ended semantic space
#            of "ways to say buyers will not pay", which is what defeated the phrase lists.
#
# The MOOD conjunct is the whole reason this is a contract and not another closed gate. Reporting
# an incumbent's free tier ("problems already addressed by free, integrated tools") carries the
# object with no mood and stays publishable; prescribing the same shape for the deliverable does
# not.
_ZERO_PRICE_SHAPE_RE = re.compile(
    # `X-free` is the WITHOUT-X adjective, not a price: "ad-free browsing", "risk-free trial",
    # "hassle-free onboarding", "commission-free", and — in this corpus — "gluten-free",
    # "fragrance-free", "cruelty-free". `\bfree\b` matched inside every one of them, so
    # "Offer a Pro tier with ad-free browsing at $9/month" read as a zero-price prescription.
    # The hyphen is the whole tell, and only the compounds whose left half is itself a PRICE word
    # ("cost-free", "fee-free", "near-free") mean what the bare word means.
    r"\b(?:cost|fee|charge|price|near|nearly|almost)[- ]free\b|"
    r"(?<![\w-])free\b|\bno[- ]charge\b|\bno[- ]cost\b|\bfree of charge\b|\bcomplimentary\b|"
    r"\bgratis\b|"
    # The object slot tolerates a short noun phrase for the same reason the hand-over pattern
    # below does: "giving the first month away" is the identical prescription on a longer object.
    r"\bgifts?\b|\bgiveaways?\b|"
    r"\bgiv(?:e|es|ing)\s+(?:it|them|this|that|the\s+(?:\w+\s+){0,3}\w+)\s+away\b|"
    r"\bpro[- ]bono\b|\bloss[- ]leaders?\b|\bmarketing asset\b|"
    r"\blead[- ](?:gen|generation)\b|\blead[\s-]magnets?\b|"
    r"\bopen[- ]?sourc\w*\b|\bpublic domain\b|\bcommunity[- ]run\b|"
    r"\bdonat\w*\b|\btip[- ]jars?\b|\bpatronage\b|"
    r"\bsponsor\w*\b|\bunderwrit\w*\b|\bad[- ](?:supported|funded)\b|\badvertis\w*\b|"
    r"\baffiliate\b|"
    r"\blifetime\b|\bone[- ](?:time|off)\b|\bperpetual\w*\b|\bin perpetuity\b|\bforever\b|"
    r"\bzero\b|\$\s?0\b|"
    r"\b(?:pay|paid|payment|charge[ds]?|bill(?:ed|ing)?|fees?|licen[cs]e[sd]?)\b[^.]{0,25}"
    r"\bonce\b|"
    # Somebody other than this audience pays. Found by probing the rule with novel
    # prescriptions of my own: the register above covers "no price" and misses "someone else's
    # price", which reaches the identical conclusion.
    r"\bgrant[- ]funded\b|\bpublicly[- ]funded\b|\bpublic utility\b|"
    r"\bcommunity[- ](?:maintained|run|owned|hosted|stewarded)\b|"
    r"\b(?:funded|underwritten|hosted|maintained|stewarded|carried)\s+by\s+"
    r"(?:the\s+|an?\s+)?(?:trade\s+|industry\s+)?"
    r"(?:association|body|consortium|foundation|community|vendors?|sponsors?|grants?)\b|"
    # "the whole thing over to the trade association" — the object slot has to tolerate a short
    # noun phrase, not just "the <word>", or the same hand-over escapes on a three-word object.
    r"\bhand(?:s|ed|ing)?\s+(?:it|them|this|the\s+(?:\w+\s+){0,3}\w+)\s+(?:over\s+)?to\s+the\s+"
    r"(?:community|association|industry|trade|public)\b",
    re.IGNORECASE,
)

# The same prescription stated backwards: recommend a shape by ruling out the paying one.
_PAYING_SHAPE_REJECTED_RE = re.compile(
    r"\b(?:rather than|instead of|as opposed to|in place of|in lieu of)\b[^.]{0,60}?"
    r"\b(?:buy\w*|purchas\w*|pay\w*|paid|sell\w*|sold|subscri\w*|charg\w*|monet[iy][sz]\w*|"
    r"recurring)\b",
    re.IGNORECASE,
)

# Swapping one PAID shape for another is a pricing opinion, not a zero-price prescription:
# "pivot to a usage-based pricing model rather than a traditional subscription" still has the
# audience paying. Only the rejection whose replacement is unpriced is a contradiction.
_PAID_SHAPE_RECOMMENDED_RE = re.compile(
    r"\b(?:pric\w*|paid|fees?|charg\w*|billing|monet[iy][sz]\w*|subscri\w*|retainers?|"
    r"per[- ](?:seat|user|head|unit|incident)|usage[- ]based|tiers?|tiered|premium|"
    r"upsell\w*|revenue|invoic\w*)\b",
    re.IGNORECASE,
)


# `one-time`, `one-off`, `lifetime`, `perpetual` and `forever` are in the object list because a
# non-recurring price is a weaker wallet claim than a subscription — but they are still PRICES.
# When EVERY zero-price object in a sentence comes from that family and the sentence recommends a
# paid shape alongside it ("Subscriptions churn in that shape; favor one-time purchases, credits,
# or usage-based pricing"), the sentence swaps one paid shape for another. That is the pricing
# opinion `_PAID_SHAPE_RECOMMENDED_RE` already exempts on the rejection path, applied to the
# object path. One genuinely unpriced object in the list ("...or a lead-gen tool") takes the
# exemption away, which is what keeps the episodic mutant caught.
_NON_RECURRING_PAID_SHAPE_RE = re.compile(
    r"^(?:lifetime|one[- ](?:time|off)|perpetual\w*|in perpetuity|forever)$",
    re.IGNORECASE,
)

# ...and the price has to be on the RECOMMENDED side of the comparison, exactly as
# `_rejects_the_paying_shape` requires. "Perpetual licences suit these operators better than
# recurring billing" carries a paid word too, but it is the shape being RULED OUT.
_SHAPE_COMPARISON_MARKER_RE = re.compile(
    r"\b(?:rather than|instead of|as opposed to|in place of|in lieu of|better than|more than)\b",
    re.IGNORECASE,
)


def _recommended_side(sentence: str) -> str:
    """The half of a shape comparison that is being ADVISED, or the whole sentence if there is no
    comparison. `_only_non_recurring_paid_shapes` reads it, so it cannot excuse a price that sits
    on the ruled-out side."""
    comparison = _SHAPE_COMPARISON_MARKER_RE.search(sentence)
    return sentence[:comparison.start()] if comparison else sentence


def _only_non_recurring_paid_shapes(sentence: str) -> bool:
    """True when the sentence's only zero-price objects are priced ones, sold alongside a price."""
    matches = list(_ZERO_PRICE_SHAPE_RE.finditer(sentence))
    if not matches:
        return False
    if not all(_NON_RECURRING_PAID_SHAPE_RE.match(match.group(0)) for match in matches):
        return False
    return bool(_PAID_SHAPE_RECOMMENDED_RE.search(_recommended_side(sentence)))


# WHY THERE IS NO "A PRICE APPEARS NEARBY" EXEMPTION HERE (D1 hardening round 3).
#
# Round 2 added one — `_priced_tier_recommended_alongside`, which excused any sentence whose
# recommended side carried an explicit price — to stop the modal `Freemium` rationale ("a free
# tier and a paid Pro tier is optimal") reading as a prescription. It re-opened the defect it was
# meant to sit beside: the live 0c9b6f29 sentence
#
#   "Given DaySmart Vet's $116-$565/mo pricing, the most logical path forward is to pivot away
#    from subscription SaaS and toward free, lead-generation tools that seed a data corpus."
#
# went silent, because the price it quotes is the run's OWN EVIDENCE. The gate only arms when
# prices are VERIFIED, so the copy naturally quotes them: the exemption was defeated by the very
# condition that enables the check. Ten more one-line walk-arounds ("Give it away free;
# competitors charge $49/mo") followed from the same reading.
#
# It is not needed. The `Freemium` false positive it was added for is on Stage 7's rationale path,
# and that path never reaches this object branch: `_wallet_contract_violation` returns early for a
# model in `ZERO_PRICE_PRICING_MODELS`, so by the time it asks the prose gate the model is always
# field-permitted and `rejection_only` is always True. Measured on the 44 shipped rationales in
# `output/final_report_*.json`, deleting it moves nothing — object-path fires 6/44, shipped-config
# fires 0/44, field refusals 11/44, identical either way — and on the fields the object path
# actually gates (the difficulty verdict card and `idea_portfolio_summary`) the corpus firing
# delta is 0.
def _rejects_the_paying_shape(sentence: str) -> bool:
    """True when the sentence rules out the audience paying and offers nothing priced instead."""
    match = _PAYING_SHAPE_REJECTED_RE.search(sentence)
    if match is None:
        return False
    return not _PAID_SHAPE_RECOMMENDED_RE.search(sentence[:match.start()])


# OBJECT-BLINDNESS (D1 round 16, Priority 3). The MOOD conjunct asks whether the sentence
# recommends; the OBJECT conjunct asked only whether a zero-price token appears ANYWHERE in it.
# So "a paid product here must beat the free route on convenience and completeness" — which
# prescribes the PAID product and names the free route as the thing it has to out-do — was read
# as a zero-price prescription, and round 15 deleted it. The free thing is the COMPETITOR there,
# not the recommendation, and the governor that precedes it says so.
# `more than` and `above` sat in this list bare, and bare they are degree adverbs far more often
# than comparatives with a rival on the right: "More than anything, the best route is a free
# sponsor-funded tool" is a prescription, and the degree adverb silenced it from inside the
# 60-character governor window of "free". Dropping them outright would cost the genuine report
# "worth more than the free DIY routine it replaces", so they keep their place on the condition
# that made them comparatives in the first place — the free shape has to be the thing on the
# other side of them, in the object slot, not somewhere later in the sentence.
_FREE_SHAPE_ON_THE_RIGHT = (
    r"(?=\s+(?:the\s+|a\s+|an\s+|any\s+|its\s+|their\s+)?(?:[\w/]+[- ]){0,2}"
    r"(?:\bfree\b|\bno[- ]charge\b|\bno[- ]cost\b|\bgratis\b|\bcomplimentary\b|\bDIY\b|"
    r"\bopen[- ]?sourc\w*\b|\bzero\b|\bdonat\w*\b|\bsponsor\w*\b|\bad[- ](?:supported|funded)\b|"
    r"\badvertis\w*\b|\baffiliate\b|\blead[- ](?:gen|generation)\b|\bcommunity\b))"
)
_ZERO_PRICE_AS_RIVAL_RE = re.compile(
    r"\b(?:beat|beats|beating|out[- ]?perform\w*|out[- ]?do(?:es|ing)?|"
    r"against|compet(?:e|es|ed|ing)\s+(?:with|against)|"
    r"rather than paying|instead of paying)\b"
    rf"|\b(?:more than|above){_FREE_SHAPE_ON_THE_RIGHT}",
    re.IGNORECASE,
)

# The same role assigned from the right instead of the left: "the free/DIY route is the real
# competitor here, not another startup" is a REPORT, and it was firing inside the very remit
# paragraph that tells the model to report exactly that.
_ZERO_PRICE_AS_RIVAL_PREDICATE_RE = re.compile(
    r"\b(?:is|are|remains?|stays?)\s+(?:still\s+)?(?:the\s+|a\s+|an\s+)?(?:real\s+|true\s+|"
    r"actual\s+|main\s+|primary\s+)?"
    r"(?:competitor|competition|rival|alternative|substitute|incumbent|benchmark|"
    r"the\s+bar|baseline)\b",
    re.IGNORECASE,
)
# A governor binds the object it precedes, not the whole sentence. 60 characters is one clause's
# worth of intervening modifiers ("must beat the entrenched, officially-published free route").
_RIVAL_GOVERNOR_WINDOW = 60
# The right-side role assignment reaches further, because the object it labels can be a whole
# noun phrase ("obtainable free ... the free/DIY route is the real competitor here"). It is safe
# to look further: the search below still stops at the first predicate opener in between.
_RIVAL_PREDICATE_WINDOW = 120

# ...and only while nothing between them opens a NEW predicate. Without this, "beat the free route
# by giving it away" would be read as governed throughout and the genuine prescription in its
# second half would escape behind the rival framing in its first.
_INTERVENING_PREDICATE_RE = re.compile(
    r"\b(?:by|and|or|but|then|while|so|through|via|using|instead|rather|"
    r"keep|make|treat|position|hand|hands|handing|give|gives|giving|gift|ship|build|offer|"
    r"launch|release|publish|fund|distribute|monet[iy][sz]e|default|run|sell|bundle|seed|start)\b",
    re.IGNORECASE,
)


# The transitive half of `_INTERVENING_PREDICATE_RE`: verbs that would SHIP the shape they take
# as an object. The conjunctions are deliberately absent — "…, so the bar is completeness" is a
# continuation of the report, not a hand-back.
_RIVAL_HANDED_BACK_RE = re.compile(
    r"\b(?:keep|make|treat|position|hand|hands|handing|give|gives|giving|gift|ship|build|offer|"
    r"launch|release|publish|fund|distribute|monet[iy][sz]e|default|run|sell|bundle|seed|start)\b",
    re.IGNORECASE,
)


def _governed_by_rival_marker(sentence: str, start: int) -> bool:
    """True when the zero-price object at ``start`` is the thing being competed AGAINST."""
    window_start = max(0, start - _RIVAL_GOVERNOR_WINDOW)
    governor = None
    # Searched without an `endpos` so the comparative's free-shape lookahead can see the object it
    # is a comparative WITH; the object itself still has to start after the governor.
    for match in _ZERO_PRICE_AS_RIVAL_RE.finditer(sentence, window_start):
        if match.start() >= start:
            break
        governor = match
    if governor is not None and not _INTERVENING_PREDICATE_RE.search(
        sentence[governor.end():start]
    ):
        return True
    forward = sentence[start:start + _RIVAL_PREDICATE_WINDOW]
    predicate = _ZERO_PRICE_AS_RIVAL_PREDICATE_RE.search(forward)
    if not predicate or _INTERVENING_PREDICATE_RE.search(forward[:predicate.start()]):
        return False
    # ...and the role survives only while nothing after it takes the shape back as an object.
    # "A free community edition is the real alternative you should ship" calls the shape a rival
    # and then RECOMMENDS it, and without this the predicate rule labelled the prescription itself
    # as the competition. Only the ship-it verbs count: "Open-source alternatives are the benchmark
    # this has to clear" carries a deontic modal whose subject is the product, not the rival, and
    # is still a report.
    return not _RIVAL_HANDED_BACK_RE.search(forward[predicate.end():])


def _zero_price_object_is_the_rival(sentence: str) -> bool:
    """True when EVERY zero-price mention in the sentence is the thing to beat, not the thing to do.

    Every one, deliberately: "beat the free route by giving it away" recommends a zero-price shape
    in its second half, and one governed mention must not license the other.
    """
    matches = list(_ZERO_PRICE_SHAPE_RE.finditer(sentence))
    if not matches:
        return False
    return all(_governed_by_rival_marker(sentence, match.start()) for match in matches)

_RECOMMENDATION_MOOD_RE = re.compile(
    # Imperative. Requiring a determiner/pronoun object is what separates the prescription
    # "Open-source the whole thing" from the report "Open-source alternatives already cover it".
    # An imperative can sit behind a fronted subordinate clause ("Rather than selling seats, run
    # it as an ad-supported comparison site") and its object can be a bare prepositional phrase
    # ("Monetize through affiliate links"). Both escaped a branch anchored at the verb with a
    # determiner/pronoun object, which is two of the seven known backstop leaks.
    # The fronted clause is not only the contrastive one. "For a niche this price-sensitive,
    # default to a free tool funded by affiliate links", "Since WTP is thin here, open-source the
    # whole thing" and "Subscriptions churn in this trade; give the tool away" are the same
    # imperative behind an ordinary subordinate clause, and they were six of the ten known recall
    # misses. The allowance is the selection branch's, verbatim: a PUNCTUATED clause, which is what
    # keeps a bare subject ("Buyers favor free tools") from counting as one.
    r"^[\s\-*•]*"
    r"(?:[^,;.]{0,70}[,;]\s+)?"
    r"(?:so|then|instead|rather|therefore|ideally|realistically|for now)?[,\s]*"
    r"(?:just\s+|simply\s+|probably\s+)?"
    r"(?:keep|make|treat|position|hand|give|gift|ship|build|offer|launch|release|publish|price|"
    r"fund|open[- ]?source|distribute|monet[iy][sz]e|default|focus|stick|pivot|plan|consider|"
    r"target|leave|run|put|sell|bundle|seed|start|remain|stay)\b"
    r"\s+(?:it|them|this|that|these|those|the|a|an|your|our|its|their|to|on|with|as|for|"
    r"through|via|from|by|into|toward|towards|against|around|off|out)\b"
    r"|^[\s\-*•]*(?:take|charge|bill|collect|accept)\s+(?:payment|money|cash|fees?|a fee)\b"
    # Selection verbs whose object is a BARE noun phrase ("favor one-time purchases", "prefer
    # free distribution"). They only count sentence-initially — with a subject in front,
    # "buyers favor free tools" is a report about the market, not advice to the builder.
    # "Sentence-initially" has to mean the same thing it means for the imperative above, which
    # already tolerates a fronted clause: "Subscriptions churn here; prefer a free community
    # edition" and "Given the cadence, favor a free sponsor-funded tool" are the identical advice
    # behind one leading clause, and a bare `^` anchor missed both. The clause has to END at a
    # comma or semicolon, which is what keeps the subject of "buyers favor free tools" out — a
    # subject is not a punctuated clause.
    r"|^[\s\-*•]*(?:[^,;.]{0,70}[,;]\s+)?"
    r"(?:so|then|instead|rather|therefore|ideally|realistically|for now)?[,\s]*"
    r"(?:just\s+|simply\s+|probably\s+)?"
    r"(?:favou?r|prefer|opt for|go with|lean toward(?:s)?|reach for)\b"
    # Deontic.
    r"|\b(?:should|shouldn't|ought to|must|need to|needs to|has to|have to|better off|"
    r"best to|better to|worth|recommend\w*|advis\w*|suggest\w*)\b"
    # "prescribe" is the only deontic verb in this list that is also an ordinary medical one,
    # and `prescrib\w*` read the corpus sentence "the inherent role of prescribing physicians
    # in managing dose adjustments" — a REPORT about free Reddit alternatives — as a
    # prescription. The recommendation sense takes a nominal object ("prescribe a free tier");
    # the medical sense here is an attributive participle with a bare agent noun. The object
    # requirement is the same one that separates the imperative from the report above.
    # The determiner list alone let "prescribes free access", "prescribing free tiers" and
    # "prescribe giving it away" through, since their objects are bare. The zero-price vocabulary
    # is added as a permitted object head (and one optional gerund, for "prescribe giving it
    # away") — never a bare agent noun, which is what keeps "prescribing physicians" out.
    r"|\bprescrib(?:e|es|ed|ing)\s+(?:\w+ing\s+)?"
    r"(?:a|an|the|it|them|this|that|these|those|any|no|free|zero|open[- ]?source|one[- ]time|"
    r"lifetime|perpetual|donation|donations|sponsor\w*|ad[- ]supported|advertising|affiliate|"
    r"lead[- ]gen\w*|giving|handing)\b"
    r"|^[\s\-*•]*consider\b"
    # Evaluative selection: the sentence picks one shape out of the possible ones.
    r"|\b(?:path|route|road|way|move|play|approach|option|answer|model|instrument|shape|"
    r"strategy|motion|angle|wedge|bet|plan|direction|course)\b[^.]{0,60}?"
    r"\b(?:is|are|would be|will be|remains?|forward)\b"
    r"|\b(?:fits|suits?|works?|belongs?|makes? (?:more )?sense)\b[^.]{0,40}?"
    r"\b(?:better|best|here|for (?:this|these|the))\b"
    # "are the only two ideas worth validating" selects among IDEAS, not among commercial
    # shapes, so "only" is deliberately absent from this list.
    r"|\b(?:is|are|remains?)\s+the\s+(?:right|best|correct|proper|natural|obvious|"
    r"realistic|sensible|logical)\b"
    # Directional pivot.
    r"|\bpivot\w*\s+(?:to|toward|towards|away)\b|\bshift\w*\s+(?:to|toward|towards)\b"
    r"|\blean\w*\s+into\b|\bmov(?:e|es|ing)\s+(?:to|toward|towards)\b",
    re.IGNORECASE | re.MULTILINE,
)


def has_zero_price_prescription(copy: str, *, rejection_only: bool = False) -> bool:
    """True when the prose RECOMMENDS a shape in which this audience does not pay.

    Polarity-blind: it looks for a recommended shape, never for a negative word. Applied on
    every path — verdict card, analyst summary, and the sanctioned statement's evidence slot —
    because a prescription is the one contradiction that carries nothing for the polarity-aware
    tests to see.

    ``rejection_only`` keeps the object path out: only prose that RULES OUT the audience paying
    counts. Its one caller is Stage 7's rationale gate, where a zero-price object is compatible
    with the model the field gate already permitted (a free tier under `Freemium`) and only a
    refusal to charge anyone contradicts it.
    """
    for sentence in _commercial_sentences(_normalized_commercial_copy(copy)):
        if not _RECOMMENDATION_MOOD_RE.search(sentence):
            continue
        if _rejects_the_paying_shape(sentence):
            return True
        if rejection_only:
            continue
        if (
            _ZERO_PRICE_SHAPE_RE.search(sentence)
            and not _zero_price_object_is_the_rival(sentence)
            and not _only_non_recurring_paid_shapes(sentence)
        ):
            return True
    return False


def _stance_windows(residue: str) -> list[str]:
    """Each sentence, plus each adjacent pair.

    A stance can straddle a sentence boundary: "…when a vendor comes asking for money. They
    walk away every time." carries the money word in one sentence and the refusal in the next.
    """
    sentences = _commercial_sentences(residue)
    return sentences + [
        " ".join(sentences[index:index + 2]) for index in range(len(sentences) - 1)
    ]


# The subset of scope cues that can only mean the niche AS A WHOLE. "segment", "buyer" and
# "customer" also occur INSIDE the per-idea score vocabulary ("weak buyer-segment payability",
# "for its target segment"), so they cannot be trusted to decide whether a grade word is a
# claim about the niche's wallet or a grade on one idea.
_WHOLE_NICHE_CUE_RE = re.compile(
    r"\b(?:niche|market|categor(?:y|ies)|space|vertical|trade|audience|community|here)\b"
    r"|\b(?:these|those)\s+(?!tools|ideas|concepts|products|solutions|features|platforms|"
    r"options|models|companies)\w+s\b",
    re.IGNORECASE,
)


def _wallet_claim_sentences(copy: str) -> list[str]:
    """Sentences of the unsanctioned residue, prepared for a niche-level wallet-claim read.

    The per-idea score vocabulary leaves the residue ONLY where it grades an idea. Stripping it
    unconditionally removed the grade word wherever it sat, and "…is likely to fail due to
    **weak buyer payability**" lost its only negation that way: there the grade IS the
    niche-level claim.

    A grade survives when its own CLAUSE predicates it of the niche as a whole. Clause scope is
    what makes this safe: "WeatherCancelAlert … are hampered by weak payability, as they target
    coaches rather than the corporate budgets that sustain this niche" mentions the niche in a
    different clause than the grade, and reading the two together turned a per-idea grade plus a
    POSITIVE remark about the niche into a wallet denial. Product names are removed first, since
    "the Turnover Market Rate Map struggles" is not a sentence about the market.
    """
    prepared = []
    for sentence in _commercial_sentences(_unsanctioned_commercial_residue(copy)):
        named = _PRODUCT_NAME_RE.sub(" ", sentence)
        prepared.append("".join(
            clause
            if _WHOLE_NICHE_CUE_RE.search(_PER_IDEA_SCORE_VOCAB_RE.sub(" ", clause))
            else _PER_IDEA_SCORE_VOCAB_RE.sub(" ", clause)
            for clause in _CLAUSE_BOUNDARY_RE.split(named)
        ))
    return prepared


def has_negative_commercial_stance(copy: str) -> bool:
    """True when prose argues, in any register, that the money here is not there.

    Polarity-aware: a money word plus an absence/weakness/refusal marker. Used to gate the one
    free-text slot the contract interpolates (the wallet probe evidence), where the text is a
    price list rather than a sentence, so a niche-scope cue cannot be relied on.
    """
    residue = _unsanctioned_commercial_residue(copy)
    return any(
        _MONEY_TOKEN_RE.search(window) and _COMMERCIAL_NEGATION_RE.search(window)
        for window in _stance_windows(residue)
    )


def has_negative_niche_wallet_claim(copy: str) -> bool:
    """True when unauthored prose says THIS NICHE's buyers will not pay.

    Deliberately narrower than ``has_unsanctioned_commercial_claim``. A portfolio summary's
    legitimate subject matter IS commercial vocabulary — per-idea payability, market fit, which
    pricing model suits which idea — so the polarity-blind boundary applied whole is a
    permanently-closed gate there rather than a contract (measured: it rejected 54 of 55
    persisted summaries even when they carried the sanctioned statement).

    Three restrictions, each answering a measured failure:
      * scope — only claims about the niche/market/audience as a whole, because per-idea
        payability commentary is the summary's job;
      * polarity — only claims that CONTRADICT the verified paying wallet, because rejecting a
        sentence that agrees with it ("buyers willing to pay for tools that address their
        pains") deletes the report's monetization guidance for no gain;
      * score vocabulary — the digest's own per-idea labels ("weak buyer payability", "moderate
        market fit") are this pipeline quoting itself, not a claim about the niche's wallet.

    Polarity is safe HERE and nowhere else: the prescription registers that reach a negative
    conclusion without a negative word are named rules in ``_PAYING_WALLET_FORBIDDEN_COPY``,
    which the caller applies alongside this. The verdict card keeps deny-by-default.
    """
    sentences = _wallet_claim_sentences(copy)
    if any(
        _NICHE_WALLET_VERDICT_RE.search(sentence) and _COMMERCIAL_NEGATION_RE.search(sentence)
        for sentence in sentences
    ):
        return True
    # A stance can straddle a sentence boundary ("…asking for money. They walk away every
    # time."), but only an unambiguous REFUSAL may reach across one. Generic absence words
    # ("lack", "without", "no") routinely belong to the neighbouring sentence's own subject —
    # "a lack of data for many ideas. Willingness-to-pay is moderate" is not a wallet denial.
    if any(
        _NICHE_WALLET_VERDICT_RE.search(pair) and _WALLET_REFUSAL_RE.search(pair)
        for pair in (
            " ".join(sentences[index:index + 2]) for index in range(len(sentences) - 1)
        )
    ):
        return True
    # A general money word needs a scope cue, and both have to sit in ONE sentence: naming the
    # niche in one sentence does not make the next sentence's pricing note a claim about it.
    return any(
        _COMMERCIAL_COPY_TOPIC_RE.search(sentence)
        and _NICHE_SCOPE_CUE_RE.search(sentence)
        and _COMMERCIAL_NEGATION_RE.search(sentence)
        for sentence in sentences
    )


# Two verdict fields carry a vocabulary token rather than prose. Scanning them for commercial
# vocabulary flags the token "budgeted-business" itself. Anything outside the closed vocabulary
# is still scanned, so this cannot be used to smuggle a sentence through.
_CLOSED_VOCABULARY_FIELDS = {
    "verdict.difficulty_level": frozenset(_BANDS),
    "verdict.buyer_class": frozenset(BUYER_CLASSES),
}


def _iter_verdict_strings(value, path: str = "verdict"):
    """Yield every persisted string so later card fields cannot bypass the invariant."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_verdict_strings(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _iter_verdict_strings(child, f"{path}[{index}]")


def _sanctioned_slot_contradiction(copy: str) -> bool:
    """True when the sanctioned statement's free-text slot argues against the statement.

    The slot rides INSIDE the one sentence the whole contract rests on, so it gets the strictest
    read available rather than the read its host path uses. Two gaps closed here:
      * a bare price list ("$29-$99/mo; nobody upgrades") carries a refusal but no money NOUN,
        so a topic-plus-negation test found no topic to pair the refusal with. A price is now a
        money token in its own right;
      * an unambiguous refusal in the slot is refused whether or not anything co-occurs with it.
        There is no reading of "nobody upgrades" that belongs inside "buyers demonstrably pay".
    """
    for match in _SANCTIONED_WALLET_NOTE_RE.finditer(_normalized_commercial_copy(copy)):
        slot = (match.groupdict().get("slot") or "").strip()
        if not slot:
            continue
        if _WALLET_REFUSAL_RE.search(slot) or has_negative_commercial_stance(slot):
            return True
    return False


def _paying_wallet_copy_rule_labels(copy: str) -> list[str]:
    copy_to_check = re.sub(
        r"\bnot proof of weak market willingness to pay\b",
        "",
        copy,
        flags=re.IGNORECASE,
    )
    labels = [
        label for label, pattern in _PAYING_WALLET_FORBIDDEN_COPY
        if pattern.search(copy_to_check)
    ]
    # The named rules above are eight enumerated prescriptions; this is the general case they
    # were instances of. It runs on every path because a prescription contradicts a verified
    # paying wallet in a verdict card, an analyst summary and an evidence slot alike.
    if has_zero_price_prescription(copy_to_check):
        labels.append("zero-price shape prescribed for a paying niche")
    if _sanctioned_slot_contradiction(copy):
        labels.append("contradiction inside the sanctioned statement's evidence slot")
    return labels


def _paying_wallet_copy_violations(
    copy: str,
    *,
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
    expected_copy: str,
    allow_surrounding_copy: bool,
    require_expected_copy: bool,
    surrounding_copy_test,
    surrounding_copy_label: str,
    negative_paraphrase_is_a_violation: bool = False,
) -> list[str]:
    if paying_wallet_commercial_contract_copy(wallet_class, wallet_evidence) is None:
        return []

    violations = []
    if require_expected_copy:
        matches_contract = (
            copy.count(expected_copy) == 1 if allow_surrounding_copy else copy == expected_copy
        )
        if not matches_contract:
            violations.append("outside positive paying-wallet contract")
    if allow_surrounding_copy:
        surrounding_copy = copy.replace(expected_copy, " ", 1)
        if surrounding_copy_test(surrounding_copy):
            violations.append(surrounding_copy_label)
    violations.extend(_paying_wallet_copy_rule_labels(copy))
    if negative_paraphrase_is_a_violation and _PAYING_WALLET_VERDICT_NEGATIVE_PARAPHRASE.search(copy):
        violations.append("recurring paid model declared non-viable")
    return violations


def paying_wallet_commercial_copy_violations(
    copy: str,
    *,
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
    expected_copy: str,
    allow_surrounding_copy: bool = False,
    require_expected_copy: bool = True,
) -> list[str]:
    """Validate one VERDICT-CARD string against the positive paying-wallet contract.

    Exact deterministic copy is authoritative. Any surrounding prose must still be built out of
    sanctioned statements, so a novel commercial paraphrase fails whether or not the sanctioned
    statement is present alongside it.

    ``require_expected_copy=False`` validates a FRAGMENT of a larger document, which is not
    itself obliged to carry the sanctioned statement — only obliged not to contradict it.

    Analyst prose (the portfolio summary, chat) must use
    ``paying_wallet_summary_copy_violations`` instead: deny-by-default is a closed gate there.
    """
    return _paying_wallet_copy_violations(
        copy,
        wallet_class=wallet_class,
        wallet_evidence=wallet_evidence,
        expected_copy=expected_copy,
        allow_surrounding_copy=allow_surrounding_copy,
        require_expected_copy=require_expected_copy,
        surrounding_copy_test=has_unsanctioned_commercial_claim,
        surrounding_copy_label="commercial copy outside sanctioned paying-wallet statement",
    )


def paying_wallet_summary_copy_violations(
    copy: str,
    *,
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
    expected_copy: str,
    allow_surrounding_copy: bool = True,
    require_expected_copy: bool = True,
) -> list[str]:
    """Validate free-form ANALYST PROSE against the positive paying-wallet contract.

    Same forbidden-copy rules and negative-paraphrase regex as the verdict card, but the
    surrounding-prose test is polarity-aware. A portfolio summary's job is to talk about
    per-idea payability, market fit and pricing model; measured over the persisted corpus the
    polarity-blind boundary rejected essentially all of it, which is a closed gate, not a
    contract. What stays forbidden is contradicting the verified paying wallet.
    """
    return _paying_wallet_copy_violations(
        copy,
        wallet_class=wallet_class,
        wallet_evidence=wallet_evidence,
        expected_copy=expected_copy,
        allow_surrounding_copy=allow_surrounding_copy,
        require_expected_copy=require_expected_copy,
        surrounding_copy_test=has_negative_niche_wallet_claim,
        surrounding_copy_label="commercial copy outside sanctioned paying-wallet statement",
        negative_paraphrase_is_a_violation=True,
    )


# The two `PricingStrategyResult.pricing_model` values in which THIS AUDIENCE NEVER PAYS. Every
# other member of that Literal keeps a price on some tier, so only these two can contradict a
# wallet that was verified to pay.
ZERO_PRICE_PRICING_MODELS = frozenset({"Ad-Supported-Free", "Affiliate-Only"})


def zero_price_model_contradicts_wallet(
    pricing_model: Optional[str],
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
) -> bool:
    """True when the STRUCTURED pricing choice contradicts the niche's verified wallet.

    Everything else in this module reads prose. `pricing_model` is the one place the report NAMES
    the money model as a field, and Stage 7 had no contract on it at all (D1 round 16, Priority 1):
    the prompt could be gated and the crew could still publish `Ad-Supported-Free` beside the
    incumbent price list the same prompt quoted.

    Symmetric with the prose rules: `paying` with any evidence, or `mixed` whose evidence carries
    literal prices. An absent or unpriced reading is not a finding either way and returns False.
    """
    if (pricing_model or "").strip() not in ZERO_PRICE_PRICING_MODELS:
        return False
    return wallet_reading_shows_verified_prices(wallet_class, wallet_evidence)


def wallet_reading_shows_verified_prices(
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
) -> bool:
    """True when this run VERIFIED that somebody in the niche pays: the wallet half of the gate.

    Named because Stage 7 has two report-visible money outputs to hold against the same reading —
    the `pricing_model` field and the `pricing_rationale` paragraph — and both must ask the wallet
    the identical question.
    """
    normalized = (wallet_class or "").strip().lower()
    if normalized == "paying" and (wallet_evidence or "").strip():
        return True
    return wallet_evidence_shows_real_prices(normalized, wallet_evidence)


PRICED_WALLET_PRESCRIPTION_LABEL = "zero-price shape prescribed for a priced niche"


def priced_wallet_prescription_violations(
    copy: str,
    *,
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
) -> list[str]:
    """The BACKSTOP alone, applied to a ``mixed`` wallet whose evidence carries real prices.

    Deliberately weaker than the paying contract. A mixed wallet has no sanctioned statement to
    require and no positive conclusion to defend, so deny-by-default and the polarity-aware
    wallet-claim test both stay off — a mixed niche is genuinely allowed to say that half its
    buyers will not pay. What it may not do is RECOMMEND a shape in which none of them does,
    while quoting their prices two paragraphs earlier.

    Returns [] for ``paying`` (which has its own, stronger contract) and for every wallet whose
    evidence shows no price.
    """
    if (wallet_class or "").strip().lower() != "mixed":
        return []
    if not wallet_evidence_shows_real_prices(wallet_class, wallet_evidence):
        return []
    return [PRICED_WALLET_PRESCRIPTION_LABEL] if has_zero_price_prescription(copy) else []


def _copy_violation_labels(copy: str) -> list[str]:
    """Every reason ONE verdict-card string fails the positive paying-wallet contract.

    Extracted so a candidate statement can be checked BEFORE it is put into a verdict, not only
    after: the deterministic reconciliation paths used to carry fact-pack points straight through
    and hand back a verdict that still failed its own invariant.
    """
    labels = _paying_wallet_copy_rule_labels(copy)
    if has_unsanctioned_commercial_claim(copy):
        labels.append("outside positive paying-wallet contract")
    if _PAYING_WALLET_VERDICT_NEGATIVE_PARAPHRASE.search(copy):
        labels.append("recurring paid model declared non-viable")
    return labels


def _contract_violating_copy(copy: str) -> bool:
    """True when this one string could not be published on a verified paying wallet."""
    return bool(_copy_violation_labels(copy))


def _commercial_copy_violations(
    verdict: NicheDifficultyVerdict,
    fp: NicheDifficultyFactPack,
) -> list[tuple[str, str]]:
    """Return commercial statements outside the positive paying-wallet contract.

    Compliant positive/neutral commercial evidence and non-commercial analysis remain run-authored.
    Only statements that take a contradictory commercial stance are rejected.
    """
    if paying_wallet_commercial_contract_copy(fp.wallet_class, fp.wallet_evidence) is None:
        return []

    violations: list[tuple[str, str]] = []
    for path, copy in _iter_verdict_strings(verdict.model_dump()):
        if copy in _CLOSED_VOCABULARY_FIELDS.get(path, ()):
            continue  # A closed-vocabulary token ("budgeted-business") is not prose.
        labels = _copy_violation_labels(copy)
        if path == "verdict.narrative_summary" and copy == _PAYING_WALLET_CORPUS_CHALLENGE:
            labels.append("corpus challenge duplicated into narrative")
        violations.extend((path, label) for label in dict.fromkeys(labels))
    return violations


def _paying_wallet_buyer_note(buyer_class: Optional[str]) -> Optional[str]:
    """Return a buyer note that reconciles low-payability labels with priced niche evidence."""
    if buyer_class == "consumer":
        return _PAYING_WALLET_CONSUMER_BUYER_NOTE
    if buyer_class == "indie-hobbyist":
        return _PAYING_WALLET_INDIE_BUYER_NOTE
    note = _BUYER_CLASS_NOTES.get(buyer_class) if buyer_class else None
    return _without_long_dashes(note) if note else None


def _without_long_dashes(copy: str) -> str:
    """Keep newly persisted fallback copy within the card's punctuation convention."""
    return (
        copy.replace(" — ", ": ")
        .replace("—", ": ")
        .replace(" – ", "-")
        .replace("–", "-")
    )


def _paying_wallet_contract_baseline(
    verdict: NicheDifficultyVerdict,
    fp: NicheDifficultyFactPack,
    niche: Optional[str],
) -> NicheDifficultyVerdict:
    """Build deterministic replacement statements for a verified paying wallet.

    The carried-over deterministic points are RE-VALIDATED here rather than trusted. They arrive
    from the fact pack, and the fact pack's own points were never checked against the contract —
    which is how a reconciled verdict came back with a `key_challenges[0]` that still failed
    `_commercial_copy_violations` (D1 round 15, Priority 5).
    """
    safe_challenges = [
        _without_long_dashes(point)
        for point in fp.key_points
        if point != _WEAK_WTP_CHALLENGE
        and _LEGACY_WEAK_WTP_MARKER not in point
        and not _contract_violating_copy(point)
    ]
    if (
        fp.commercial_intent_max is not None
        and fp.commercial_intent_max < 0.6
        and _PAYING_WALLET_CORPUS_CHALLENGE not in safe_challenges
    ):
        safe_challenges.append(_PAYING_WALLET_CORPUS_CHALLENGE)

    evidence_bearing_wallet_note = _wallet_positive_note(fp.wallet_evidence or "")
    safe_strengths = [
        _without_long_dashes(point)
        for point in fp.key_strengths
        if point != evidence_bearing_wallet_note
        and not _contract_violating_copy(point)
    ]
    # The probe evidence is model-produced web summary text. The positive contract publishes only
    # the sanctioned conclusion, never arbitrary evidence wording.
    wallet_note = paying_wallet_commercial_contract_copy(fp.wallet_class, fp.wallet_evidence)
    if wallet_note is None:
        raise ValueError("paying-wallet contract requested without verified paying evidence")
    if wallet_note not in safe_strengths:
        safe_strengths.append(wallet_note)
    buyer_note = _paying_wallet_buyer_note(verdict.buyer_class)
    if (
        verdict.buyer_class
        and _BUYER_CLASS_PAYABILITY.get(verdict.buyer_class) == "low"
        and buyer_note
        and buyer_note not in safe_challenges
    ):
        safe_challenges.append(buyer_note)

    # Challenges own the corpus-gap statement. Excluding it from the narrative input prevents the
    # same paragraph from appearing once in the summary and again in the visible challenge list.
    safe_fp = fp.model_copy(update={"key_points": []})
    headline, narrative = _fallback_narrative(safe_fp, niche)
    headline = _without_long_dashes(headline)
    narrative = _without_long_dashes(narrative)

    return NicheDifficultyVerdict(
        difficulty_level=fp.difficulty_level,
        software_addressability=fp.software_addressability,
        headline=headline,
        narrative_summary=narrative,
        key_challenges=safe_challenges,
        key_strengths=safe_strengths,
        low_confidence=fp.low_confidence,
        buyer_class=verdict.buyer_class,
        buyer_class_note=buyer_note,
        monetization_guidance=_fact_pack_monetization_guidance(fp),
    )


def _fact_pack_monetization_guidance(fp: NicheDifficultyFactPack) -> str:
    """The reader-facing monetization line for this run, from the fact pack's wallet reading."""
    return monetization_guidance(
        {"wallet_class": fp.wallet_class, "evidence": fp.wallet_evidence}
    )


def _compliant_narrative_sentences(narrative: str) -> str:
    """Keep every one of the run's own sentences that does not break the contract.

    This FILTERS rather than truncates. Truncating at the first violator reads better in
    principle, but measured over the persisted corpus it destroyed the whole narrative whenever
    the violation landed in sentence 1 or 2 — including narratives whose later sentences were
    compliant, niche-specific, and in one case the only monetization guidance in the report.
    Returns "" only when nothing survives, and the caller falls back to the baseline.
    """
    kept = [
        sentence
        for sentence in _SENTENCE_BOUNDARY_RE.split(narrative)
        if sentence.strip()
        and not _paying_wallet_copy_rule_labels(sentence)
        and not has_unsanctioned_commercial_claim(sentence)
        and not _PAYING_WALLET_VERDICT_NEGATIVE_PARAPHRASE.search(sentence)
    ]
    return " ".join(kept).strip()


def _build_paying_wallet_contract_verdict(
    verdict: NicheDifficultyVerdict,
    fp: NicheDifficultyFactPack,
    niche: Optional[str],
) -> NicheDifficultyVerdict:
    """Replace only the individual verdict statements that violate the wallet contract."""
    baseline = _paying_wallet_contract_baseline(verdict, fp, niche)
    violation_paths = {path for path, _ in _commercial_copy_violations(verdict, fp)}

    headline = (
        baseline.headline if "verdict.headline" in violation_paths else verdict.headline
    )
    narrative = verdict.narrative_summary
    if "verdict.narrative_summary" in violation_paths:
        narrative = (
            _compliant_narrative_sentences(verdict.narrative_summary)
            or baseline.narrative_summary
        )

    safe_strengths = [
        point
        for index, point in enumerate(verdict.key_strengths)
        if f"verdict.key_strengths[{index}]" not in violation_paths
    ]
    wallet_note = paying_wallet_commercial_contract_copy(fp.wallet_class, fp.wallet_evidence)
    if (
        wallet_note
        and not any(
            _SANCTIONED_WALLET_NOTE_RE.search(_normalized_commercial_copy(point))
            for point in safe_strengths
        )
    ):
        safe_strengths.append(wallet_note)

    safe_challenges = [
        point
        for index, point in enumerate(verdict.key_challenges)
        if f"verdict.key_challenges[{index}]" not in violation_paths
    ]
    if (
        fp.commercial_intent_max is not None
        and fp.commercial_intent_max < 0.6
        and _PAYING_WALLET_CORPUS_CHALLENGE not in safe_challenges
    ):
        safe_challenges.append(_PAYING_WALLET_CORPUS_CHALLENGE)

    buyer_note = verdict.buyer_class_note
    if "verdict.buyer_class_note" in violation_paths:
        buyer_note = baseline.buyer_class_note
    if (
        verdict.buyer_class
        and _BUYER_CLASS_PAYABILITY.get(verdict.buyer_class) == "low"
        and baseline.buyer_class_note
        and baseline.buyer_class_note not in safe_challenges
    ):
        safe_challenges.append(baseline.buyer_class_note)

    return verdict.model_copy(
        update={
            "headline": headline,
            "narrative_summary": narrative,
            "key_challenges": safe_challenges,
            "key_strengths": safe_strengths,
            "buyer_class_note": buyer_note,
        }
    )


def _merge_retry_for_rejected_fields(
    original: NicheDifficultyVerdict,
    retry: NicheDifficultyVerdict,
    original_violations: list[tuple[str, str]],
    retry_violations: list[tuple[str, str]],
) -> NicheDifficultyVerdict:
    """Accept retry prose only for a top-level field rejected in the original verdict."""
    rejected = {path.removeprefix("verdict.").split("[", 1)[0] for path, _ in original_violations}
    still_rejected = {
        path.removeprefix("verdict.").split("[", 1)[0] for path, _ in retry_violations
    }
    updates = {
        field: getattr(retry, field)
        for field in rejected - still_rejected
        if field in {"headline", "narrative_summary", "key_challenges", "key_strengths",
                     "buyer_class_note"}
    }
    return original.model_copy(update=updates)


def _deterministic_paying_wallet_fallback(
    verdict: NicheDifficultyVerdict,
    fp: NicheDifficultyFactPack,
    niche: Optional[str],
) -> NicheDifficultyVerdict:
    """Fail-soft wrapper for the deterministic positive contract."""
    try:
        reconciled = _build_paying_wallet_contract_verdict(verdict, fp, niche)
        remaining = _commercial_copy_violations(reconciled, fp)
        if not remaining:
            return reconciled
        logger.error(
            f"[Niche Difficulty] reconciled paying-wallet copy failed its recheck: {remaining}. "
            "Using minimal reconciled copy."
        )
    except Exception as e:  # noqa: BLE001 - commercial copy must never break the pipeline
        logger.error(
            f"[Niche Difficulty] paying-wallet copy reconciliation failed: {e}. "
            "Using minimal reconciled copy."
        )
    buyer_note = _paying_wallet_buyer_note(verdict.buyer_class)
    minimal_challenges = [_PAYING_WALLET_CORPUS_CHALLENGE]
    if (
        verdict.buyer_class
        and _BUYER_CLASS_PAYABILITY.get(verdict.buyer_class) == "low"
        and buyer_note
    ):
        minimal_challenges.append(buyer_note)
    minimal = NicheDifficultyVerdict(
        difficulty_level=fp.difficulty_level,
        software_addressability=fp.software_addressability,
        headline=_without_long_dashes(_fit_headline(fp.software_addressability)),
        narrative_summary=_MINIMAL_PAYING_WALLET_NARRATIVE,
        key_challenges=minimal_challenges,
        key_strengths=[_wallet_positive_note("")],
        low_confidence=fp.low_confidence,
        buyer_class=(verdict.buyer_class if verdict.buyer_class in BUYER_CLASSES else None),
        buyer_class_note=buyer_note,
        monetization_guidance=_fact_pack_monetization_guidance(fp),
    )
    # The last stop on every failure path is the one place a violation cannot be caught later, so
    # it validates itself instead of being trusted (D1 round 15, Priority 5). A statement that
    # fails here is dropped rather than published; the sanctioned corpus statement always survives,
    # so `key_challenges` cannot come back empty.
    residual = {path for path, _ in _commercial_copy_violations(minimal, fp)}
    if not residual:
        return minimal
    logger.error(
        f"[Niche Difficulty] minimal reconciled copy failed its own recheck: {sorted(residual)}. "
        "Publishing only the statements that passed."
    )
    return minimal.model_copy(update={
        "key_challenges": [
            point for index, point in enumerate(minimal.key_challenges)
            if f"verdict.key_challenges[{index}]" not in residual
        ] or [_PAYING_WALLET_CORPUS_CHALLENGE],
        "key_strengths": [
            point for index, point in enumerate(minimal.key_strengths)
            if f"verdict.key_strengths[{index}]" not in residual
        ],
        "buyer_class_note": (
            None if "verdict.buyer_class_note" in residual else minimal.buyer_class_note
        ),
    })


def _persisted_verdict_fact_pack(
    verdict: NicheDifficultyVerdict,
    *,
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
) -> NicheDifficultyFactPack:
    """Build a conservative fallback fact pack for a partial legacy checkpoint.

    Normal checkpoint hydration recomputes the full fact pack from restored Stage 3/5 data. This
    fallback exists for older or trimmed checkpoints that persisted the verdict but not all of its
    inputs. It preserves non-commercial deterministic findings while removing the legacy wallet
    statements that the positive contract replaces.
    """
    legacy_wtp_gap = any(
        point == _PAYING_WALLET_CORPUS_CHALLENGE
        or _LEGACY_WEAK_WTP_MARKER in point
        or point == _WEAK_WTP_CHALLENGE
        for point in verdict.key_challenges
    )
    safe_challenges = [
        point
        for point in verdict.key_challenges
        if not _paying_wallet_copy_rule_labels(point)
        and point != _PAYING_WALLET_CORPUS_CHALLENGE
    ]
    safe_strengths = [
        point
        for point in verdict.key_strengths
        if "demonstrably pay for tooling" not in point
    ]
    addressability = verdict.software_addressability
    return NicheDifficultyFactPack(
        n_pains=1,
        n_ideas=0,
        none_share=max(0.0, 1.0 - addressability),
        partial_share=0.0,
        full_share=addressability,
        software_addressability=addressability,
        commercial_intent_max=0.0 if legacy_wtp_gap else None,
        difficulty_level=verdict.difficulty_level,
        low_confidence=verdict.low_confidence,
        key_points=safe_challenges,
        key_strengths=safe_strengths,
        wallet_class=wallet_class,
        wallet_evidence=wallet_evidence,
    )


def reconcile_persisted_niche_difficulty_verdict(
    verdict: NicheDifficultyVerdict,
    *,
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
    fact_pack: Optional[NicheDifficultyFactPack] = None,
    niche: Optional[str] = None,
) -> NicheDifficultyVerdict:
    """Reconcile legacy persisted verdict prose before any resumed publication.

    The full restored fact pack is preferred and produces the same deterministic replacement as
    generation-time reconciliation. Partial legacy checkpoints use a conservative fact pack built
    from the persisted deterministic fields. This function is deliberately fail-soft: a contract
    violation never makes checkpoint restore fail.

    It also backfills the reader-facing `monetization_guidance` line, which older checkpoints
    predate — the field is the report's only niche-level statement about money, so a resumed run
    must not publish a card without it.
    """
    if not (verdict.monetization_guidance or "").strip():
        verdict = verdict.model_copy(update={
            "monetization_guidance": monetization_guidance(
                {"wallet_class": wallet_class, "evidence": wallet_evidence}
            )
        })
    if paying_wallet_commercial_contract_copy(wallet_class, wallet_evidence) is None:
        return verdict

    try:
        fp = fact_pack or _persisted_verdict_fact_pack(
            verdict,
            wallet_class=wallet_class,
            wallet_evidence=wallet_evidence,
        )
        fp = fp.model_copy(
            update={
                "difficulty_level": verdict.difficulty_level,
                "software_addressability": verdict.software_addressability,
                "low_confidence": verdict.low_confidence,
                "wallet_class": wallet_class,
                "wallet_evidence": wallet_evidence,
            }
        )
        violations = _commercial_copy_violations(verdict, fp)
        if not violations:
            return verdict
        logger.warning(
            "[Niche Difficulty] persisted paying-wallet commercial invariant rejected "
            f"fields {violations}. Hydrating deterministic reconciled copy."
        )
        return _deterministic_paying_wallet_fallback(verdict, fp, niche)
    except Exception as e:  # noqa: BLE001 - legacy prose must never crash resume/reporting
        logger.error(
            f"[Niche Difficulty] persisted prose reconciliation failed: {e}. "
            "Hydrating minimal reconciled copy."
        )
        fp = _persisted_verdict_fact_pack(
            verdict,
            wallet_class=wallet_class,
            wallet_evidence=wallet_evidence,
        )
        return _deterministic_paying_wallet_fallback(verdict, fp, niche)


def _compliant_summary_prose(summary: str, expected: str) -> str:
    """Drop the sentences that break the summary contract and keep the rest of the analysis.

    A legacy off-contract summary cannot be regenerated deterministically, but replacing the
    whole thing with the one sanctioned sentence threw away a 1,600-character analyst narrative
    to remove one contradicting clause. This keeps the run's own prose — paragraph structure
    included — and lets the sanctioned statement stand in for what was removed.

    The per-sentence pass cannot see a contradiction split across two sentences, so the filtered
    result is re-validated as a whole and abandoned if anything survived.
    """
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", summary):
        kept = [
            sentence
            for sentence in _SENTENCE_BOUNDARY_RE.split(paragraph)
            if sentence.strip()
            and sentence.strip() != expected.strip()
            and not _paying_wallet_copy_rule_labels(sentence)
            and not _PAYING_WALLET_VERDICT_NEGATIVE_PARAPHRASE.search(sentence)
            and not has_negative_niche_wallet_claim(sentence)
        ]
        if kept:
            paragraphs.append(" ".join(s.strip() for s in kept))
    prose = "\n\n".join(paragraphs).strip()
    if not prose:
        return ""
    residual = paying_wallet_summary_copy_violations(
        f"{prose}\n\n{expected}",
        wallet_class="paying",
        wallet_evidence=expected,
        expected_copy=expected,
    )
    if residual:
        logger.warning(
            f"[PortfolioSummary] filtered prose still violates {residual}; dropping it."
        )
        return ""
    return prose


def _priced_mixed_summary_without_prescriptions(summary: str) -> str:
    """Drop only the sentences that PRESCRIBE a non-paying shape; keep everything else.

    The mixed-wallet reconciliation has no sanctioned statement to fall back on, so it must not
    be able to empty the summary: if nothing survives, the caller keeps the original prose
    rather than publishing nothing.
    """
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", summary):
        kept = [
            sentence
            for sentence in _SENTENCE_BOUNDARY_RE.split(paragraph)
            if sentence.strip() and not has_zero_price_prescription(sentence)
        ]
        if kept:
            paragraphs.append(" ".join(s.strip() for s in kept))
    return "\n\n".join(paragraphs).strip()


def reconcile_persisted_paying_wallet_summary(
    summary: Optional[str],
    *,
    wallet_class: Optional[str],
    wallet_evidence: Optional[str],
) -> Optional[str]:
    """Return publishable persisted portfolio prose without making an LLM call.

    A legacy off-contract summary cannot be regenerated deterministically. Replacing it with the
    shared sanctioned commercial statement preserves the verified conclusion and removes every
    unconstrained wallet/pricing claim; a later candidate-set refresh may replace it with a fully
    grounded summary.

    A ``mixed`` wallet whose evidence carries literal prices gets the backstop only — see
    ``priced_wallet_prescription_violations``. It keeps its own analysis, including anything it
    says about the half of the niche that will not pay; it just cannot prescribe a shape in
    which nobody does.
    """
    expected = paying_wallet_commercial_contract_copy(wallet_class, wallet_evidence)
    if not summary:
        return summary
    if expected is None:
        priced_violations = priced_wallet_prescription_violations(
            summary, wallet_class=wallet_class, wallet_evidence=wallet_evidence
        )
        if not priced_violations:
            return summary
        kept = _priced_mixed_summary_without_prescriptions(summary)
        if not kept:
            logger.error(
                "[PortfolioSummary] persisted priced-mixed summary is prescription-only; "
                "keeping the original prose rather than publishing nothing."
            )
            return summary
        logger.warning(
            "[PortfolioSummary] persisted priced-mixed wallet rejected summary: "
            f"{priced_violations}. Keeping {len(kept)} of {len(summary)} characters of run prose."
        )
        return kept
    try:
        violations = paying_wallet_summary_copy_violations(
            summary,
            wallet_class=wallet_class,
            wallet_evidence=wallet_evidence,
            expected_copy=expected,
        )
    except Exception as e:  # noqa: BLE001 - use the safe deterministic copy on validator failure
        logger.error(
            f"[PortfolioSummary] persisted commercial validation failed: {e}. "
            "Hydrating deterministic reconciled copy."
        )
        return expected
    if not violations:
        return summary
    kept = _compliant_summary_prose(summary, expected)
    logger.warning(
        "[PortfolioSummary] persisted paying-wallet commercial invariant rejected summary: "
        f"{violations}. Keeping {len(kept)} of {len(summary)} characters of run prose."
    )
    return f"{kept}\n\n{expected}" if kept else expected


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
    usage = None
    prompt = None
    llm_service_cls = None
    token_usage_cls = None

    def _candidate(result=None) -> NicheDifficultyVerdict:
        headline, narrative = _fallback_narrative(fp, niche)
        buyer_class = None
        if result is not None:
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
            bc = (getattr(result, "buyer_class", "") or "").strip().lower()
            if bc in BUYER_CLASSES:
                buyer_class = bc
            elif bc:
                logger.warning(f"[Niche Difficulty] off-vocab buyer_class '{bc[:40]}' — dropped.")

        buyer_class_note = _BUYER_CLASS_NOTES.get(buyer_class) if buyer_class else None
        key_challenges = list(fp.key_points)
        wtp_judgment = _wtp_judgment(
            fp.commercial_intent_max,
            fp.high_commercial_share,
            fp.wallet_class,
            fp.wallet_evidence,
        )
        if (buyer_class and _BUYER_CLASS_PAYABILITY.get(buyer_class) == "low"
                and buyer_class_note and buyer_class_note not in key_challenges):
            key_challenges.append(buyer_class_note)

        return NicheDifficultyVerdict(
            difficulty_level=fp.difficulty_level,
            software_addressability=fp.software_addressability,
            headline=headline,
            narrative_summary=narrative,
            key_challenges=key_challenges,
            key_strengths=list(fp.key_strengths),
            low_confidence=fp.low_confidence,
            buyer_class=buyer_class,
            buyer_class_note=buyer_class_note,
            monetization_guidance=_fact_pack_monetization_guidance(fp),
        )

    try:
        from ..config.settings import settings
        from .llm_service import LLMService, TokenUsage
        from .prompts import load_prompt, safe_format
        from .score_helpers import score_band

        llm_service_cls = LLMService
        token_usage_cls = TokenUsage

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
            willingness_to_pay=_wtp_judgment(
                fp.commercial_intent_max,
                fp.high_commercial_share,
                fp.wallet_class,
                fp.wallet_evidence,
            ),
            buyer_segments=fp.segment_budget_brief or "n/a",
            substitute_share=_share_word(fp.substitute_share),
            verified_incumbent_share=_share_word(fp.verified_incumbent_share),
            adjacent_incumbent_share=_share_word(fp.adjacent_incumbent_share),
            episodic_usage_share=_share_word(fp.episodic_usage_share),
            key_points=" | ".join(fp.key_points) or "n/a",
            low_confidence=fp.low_confidence,
            monetization_guidance=_fact_pack_monetization_guidance(fp),
        )
        result, usage = llm_service_cls.invoke_structured(
            prompt=prompt,
            output_model=NicheDifficultyNarrative,
            temperature=0.7,
            model_name=settings.function_calling_llm,
        )
    except Exception as e:  # noqa: BLE001 — best-effort; deterministic fallback already set
        logger.warning(f"[Niche Difficulty] prose LLM failed: {e}. Using deterministic narrative.")
        result = None

    verdict = _candidate(result)
    violations = _commercial_copy_violations(verdict, fp)
    if not violations:
        return verdict, usage

    logger.warning(
        f"[Niche Difficulty] paying-wallet commercial invariant rejected final verdict "
        f"fields {violations}. Retrying prose once."
    )
    retry_usage = None
    if llm_service_cls is not None and prompt is not None:
        retry_prompt = prompt + (
            "\n\nCOMMERCIAL CONSISTENCY RETRY: your previous narrative recommended a commercial "
            "shape. That is out of your remit entirely — not just the shapes you happened to "
            "name. Verified priced evidence shows buyers in this niche already pay for tooling, "
            "and the `monetization_guidance` line quoted above is the report's own statement on "
            "how this makes money — it is carried on the verdict card you are writing. Rewrite "
            "with EVERY sentence "
            "about how the product should be priced or funded deleted, keeping the rest of your "
            "analysis intact. If the captured discussions lack purchase intent, you may report "
            "that as a corpus evidence gap — a fact about the evidence — and nothing more."
        )
        try:
            retry_result, retry_usage = llm_service_cls.invoke_structured(
                prompt=retry_prompt,
                output_model=NicheDifficultyNarrative,
                temperature=0.7,
                model_name=settings.function_calling_llm,
            )
            retry_verdict = _candidate(retry_result)
            retry_violations = _commercial_copy_violations(retry_verdict, fp)
            if retry_violations:
                logger.warning(
                    f"[Niche Difficulty] paying-wallet commercial invariant rejected retry "
                    f"fields {retry_violations}. Using deterministic reconciled copy."
                )
            merged = _merge_retry_for_rejected_fields(
                verdict, retry_verdict, violations, retry_violations
            )
            verdict = _deterministic_paying_wallet_fallback(merged, fp, niche)
        except Exception as e:  # noqa: BLE001 — deterministic semantic fallback is authoritative
            logger.warning(
                f"[Niche Difficulty] commercial-consistency retry failed: {e}. "
                "Using deterministic reconciled copy."
            )
            verdict = _deterministic_paying_wallet_fallback(verdict, fp, niche)
    else:
        verdict = _deterministic_paying_wallet_fallback(verdict, fp, niche)

    if usage is not None and retry_usage is not None and token_usage_cls is not None:
        costs = [getattr(item, "cost", None) for item in (usage, retry_usage)]
        usage = token_usage_cls(
            prompt_tokens=usage.prompt_tokens + retry_usage.prompt_tokens,
            completion_tokens=usage.completion_tokens + retry_usage.completion_tokens,
            model=usage.model,
            cost=sum(costs) if all(cost is not None for cost in costs) else None,
        )
    return verdict, usage
