"""Durable, fail-honest speaker attribution for discovery evidence.

The classifier runs after pain extraction and audience mapping converge, so it can
judge an authored contribution relative to the final primary target. It mutates only
metadata on already-collected content and parallel quote metadata; collection scope
and ranking are untouched.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ..config.settings import settings
from ..models.social_content import SpeakerAttribution, SocialContentCollection
from .llm_service import LLMService
from .prompts import get_prompt
from .validation.thread_validator import _sanitize_text


ATTRIBUTION_VERSION = 5
CONFIRMED_BUYER_CONFIDENCE = 0.70
ATTRIBUTION_BATCH_SIZE = 40


class _AttributionVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=1)
    role: Literal["buyer", "adjacent_worker", "customer", "unknown"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str
    identity_evidence: str | None = None
    authority_evidence: str | None = None


class _BatchAttributionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attributions: list[_AttributionVerdict]


class _BuyerReviewVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=1)
    confirmed: bool
    segment_fit: Literal["fits", "unknown", "contradicts"]
    corrected_role: Literal["adjacent_worker", "customer", "unknown"] | None = None
    rationale: str


class _BuyerReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviews: list[_BuyerReviewVerdict]


@dataclass
class ContributionRef:
    key: str
    text: str
    contribution_id: str | None
    author: str | None
    community: str
    content_kind: str
    is_submitter: bool | None
    speaker_context: str = ""
    node: Any | None = None
    pain_refs: list[tuple[Any, int]] = field(default_factory=list)
    pain_titles: set[str] = field(default_factory=set)
    evidence_segments: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class SpeakerAttributionRun:
    changed: bool
    candidate_count: int
    llm_calls: int
    unknown_count: int
    failed_batches: int


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


ScaleFit = Literal["fits", "unknown", "contradicts"]


@dataclass(frozen=True)
class ParsedScale:
    """A grounded numeric interval whose unit came from the source text."""

    unit: str
    minimum: Decimal | None
    maximum: Decimal | None
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True


_NUMBER = r"(?:[$€£]\s*)?(?:\d[\d,]*(?:\.\d+)?|zero|no)\s*[kmb]?"
_UNIT = r"[A-Za-z][A-Za-z-]*"
_UNIT_SEPARATOR = r"(?:\s+|-)"
_SCALE_PATTERN = re.compile(
    rf"""
    (?<![\w])
    (?:
        (?P<range_low>{_NUMBER})\s*(?:[-–—]|\bto\b)\s*
            (?P<range_high>{_NUMBER}){_UNIT_SEPARATOR}(?P<range_unit>{_UNIT})
      | (?P<lower_prefix>at\s+least)\s+(?P<lower_value>{_NUMBER}){_UNIT_SEPARATOR}
            (?P<lower_unit>{_UNIT})
      | (?P<upper_prefix>under|fewer\s+than)\s+(?P<upper_value>{_NUMBER}){_UNIT_SEPARATOR}
            (?P<upper_unit>{_UNIT})
      | (?P<plus_value>{_NUMBER})\s*\+{_UNIT_SEPARATOR}(?P<plus_unit>{_UNIT})
      | (?P<exact_value>{_NUMBER}){_UNIT_SEPARATOR}(?P<exact_unit>{_UNIT})
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _decimal_quantity(raw: str) -> Decimal:
    normalized = re.sub(r"[$€£,\s]", "", raw.lower())
    if normalized in {"zero", "no"}:
        return Decimal(0)
    multiplier = Decimal(1)
    if normalized[-1:] in {"k", "m", "b"}:
        multiplier = {
            "k": Decimal(1_000),
            "m": Decimal(1_000_000),
            "b": Decimal(1_000_000_000),
        }[normalized[-1]]
        normalized = normalized[:-1]
    return Decimal(normalized) * multiplier


def _normalized_unit(raw: str) -> str:
    unit = raw.lower().strip("-")
    if unit.endswith("ies") and len(unit) > 3:
        return f"{unit[:-3]}y"
    if unit.endswith("s") and not unit.endswith("ss") and len(unit) > 1:
        return unit[:-1]
    return unit


def _parse_scales(text: str) -> tuple[ParsedScale, ...]:
    """Parse explicit number-plus-unit scale statements without unit vocabulary."""
    scales: list[ParsedScale] = []
    for match in _SCALE_PATTERN.finditer(text):
        if match.group("range_low") is not None:
            low = _decimal_quantity(match.group("range_low"))
            high = _decimal_quantity(match.group("range_high"))
            if low > high:
                continue
            scales.append(ParsedScale(
                unit=_normalized_unit(match.group("range_unit")),
                minimum=low,
                maximum=high,
            ))
        elif match.group("lower_value") is not None:
            scales.append(ParsedScale(
                unit=_normalized_unit(match.group("lower_unit")),
                minimum=_decimal_quantity(match.group("lower_value")),
                maximum=None,
            ))
        elif match.group("upper_value") is not None:
            scales.append(ParsedScale(
                unit=_normalized_unit(match.group("upper_unit")),
                minimum=Decimal(0),
                maximum=_decimal_quantity(match.group("upper_value")),
                maximum_inclusive=False,
            ))
        elif match.group("plus_value") is not None:
            scales.append(ParsedScale(
                unit=_normalized_unit(match.group("plus_unit")),
                minimum=_decimal_quantity(match.group("plus_value")),
                maximum=None,
            ))
        else:
            value = _decimal_quantity(match.group("exact_value"))
            scales.append(ParsedScale(
                unit=_normalized_unit(match.group("exact_unit")),
                minimum=value,
                maximum=value,
            ))
    return tuple(scales)


def _parse_scale(text: str) -> ParsedScale | None:
    """Return one unambiguous typed scale, otherwise fail closed."""
    scales = _parse_scales(text)
    return scales[0] if len(scales) == 1 else None


def _strictly_before(left: ParsedScale, right: ParsedScale) -> bool:
    if left.maximum is None or right.minimum is None:
        return False
    return left.maximum < right.minimum or (
        left.maximum == right.minimum
        and (not left.maximum_inclusive or not right.minimum_inclusive)
    )


def _contains(container: ParsedScale, value: ParsedScale) -> bool:
    lower_contains = container.minimum is None or (
        value.minimum is not None
        and (
            value.minimum > container.minimum
            or (
                value.minimum == container.minimum
                and (container.minimum_inclusive or not value.minimum_inclusive)
            )
        )
    )
    upper_contains = container.maximum is None or (
        value.maximum is not None
        and (
            value.maximum < container.maximum
            or (
                value.maximum == container.maximum
                and (container.maximum_inclusive or not value.maximum_inclusive)
            )
        )
    )
    return lower_contains and upper_contains


def _compare_segment_scale(target: str, text: str) -> ScaleFit:
    """Compare only grounded, unambiguous, like-unit scale intervals."""
    target_scale = _parse_scale(target)
    if target_scale is None:
        return "unknown"
    speaker_scales = [
        scale for scale in _parse_scales(text) if scale.unit == target_scale.unit
    ]
    if not speaker_scales:
        return "unknown"

    comparisons: list[ScaleFit] = []
    for speaker_scale in speaker_scales:
        if (
            _strictly_before(speaker_scale, target_scale)
            or _strictly_before(target_scale, speaker_scale)
        ):
            comparisons.append("contradicts")
        elif _contains(target_scale, speaker_scale):
            comparisons.append("fits")
        else:
            comparisons.append("unknown")

    if all(result == "contradicts" for result in comparisons):
        return "contradicts"
    if all(result == "fits" for result in comparisons):
        return "fits"
    return "unknown"


def _explicitly_below_target_scale(target: str, text: str) -> bool:
    """Compatibility predicate for a grounded same-unit scale contradiction."""
    return _compare_segment_scale(target, text) == "contradicts"


def _has_direct_operational_control(text: str) -> bool:
    """Recognize buyer-candidacy evidence, never a final buyer verdict.

    Selecting a tool and delegating its underlying work can indicate operational
    authority. It only proposes a tentative buyer for adversarial review; it must
    never override that review's rejection.
    """
    normalized = _normalized(text)
    selects_tool = bool(re.search(
        r"\b(?:need|find|finding|choose|choosing|evaluate|evaluating|tried|using"
        r"|select(?:s|ed|ing)?)\b"
        r".{0,100}\b(?:tool|software|program|app|system)\b",
        normalized,
    ))
    delegates_work = bool(re.search(
        r"\b(?:give|assign|delegat(?:e|es|ed|ing)|have|ask)\b.{0,80}"
        r"\b(?:staff|employee|team member|worker)\b",
        normalized,
    ))
    return selects_tool and delegates_work


def _identity_matches_target_context(
    identity_evidence: str | None,
    target: str,
    target_context: str,
    community_hubs: Iterable[Any],
) -> bool:
    """Require a lexical target/domain anchor before proposing a tentative buyer."""
    ignored = {
        "and", "for", "from", "have", "into", "our", "the", "their", "this",
        "with", "work", "working", "business", "company", "operation", "manager",
        "owner", "independent", "staff", "team",
    }
    identity_tokens = {
        token for token in _normalized(identity_evidence).split()
        if len(token) >= 3 and token not in ignored
    }
    reference_tokens = {
        token for token in _normalized(
            " ".join((target, target_context, *(str(hub) for hub in community_hubs)))
        ).split()
        if len(token) >= 3 and token not in ignored
    }
    return any(
        left == right or left.startswith(right) or right.startswith(left)
        for left in identity_tokens
        for right in reference_tokens
    )


def _iter_reddit_comments(comments: Iterable[Any]) -> Iterable[Any]:
    for comment in comments or []:
        yield comment
        yield from _iter_reddit_comments(getattr(comment, "replies", None) or [])


def _iter_social_responses(responses: Iterable[Any]) -> Iterable[Any]:
    for response in responses or []:
        yield response
        yield from _iter_social_responses(getattr(response, "replies", None) or [])


def _matches_quote(quote: str, contribution_text: str) -> bool:
    q = _normalized(quote)
    body = _normalized(contribution_text)
    if not q or not body:
        return False
    # Quotes are cleaned sentence fragments. Require containment rather than a
    # topical/similarity guess: unresolved provenance must stay unresolved.
    return q in body or (len(body) >= 40 and body in q)


def find_quote_contribution(
    social_content: SocialContentCollection,
    post_id: str,
    quote: str,
) -> ContributionRef | None:
    """Resolve a quote to its authored post/comment/reply using exact provenance.

    ``source_post_ids`` identify the enclosing thread, so the text join is needed
    to distinguish its submitter from a commenter. No role is inferred here.
    """
    if not post_id or not quote:
        return None

    for post in social_content.reddit_posts or []:
        if post.post_id != post_id:
            continue
        post_text = " ".join(part for part in (post.title, post.selftext) if part)
        if _matches_quote(quote, post_text):
            return ContributionRef(
                key=f"reddit_post:{post.post_id}",
                text=post_text,
                contribution_id=post.post_id,
                author=post.author,
                community=post.subreddit,
                content_kind="reddit_post",
                is_submitter=True,
                node=post,
            )
        for comment in _iter_reddit_comments(post.comments):
            if _matches_quote(quote, comment.body):
                return ContributionRef(
                    key=f"reddit_comment:{comment.comment_id}",
                    text=comment.body,
                    contribution_id=comment.comment_id,
                    author=comment.author,
                    community=post.subreddit,
                    content_kind="reddit_comment",
                    is_submitter=comment.is_submitter,
                    speaker_context=post_text if comment.is_submitter else "",
                    node=comment,
                )
        return None

    for thread in social_content.twitter_threads or []:
        if thread.thread_id != post_id:
            continue
        tweets = [thread.original_tweet, *(thread.replies or [])]
        for tweet in tweets:
            if _matches_quote(quote, tweet.text):
                return ContributionRef(
                    key=f"twitter_tweet:{tweet.tweet_id}",
                    text=tweet.text,
                    contribution_id=tweet.tweet_id,
                    author=tweet.author_username,
                    community="twitter",
                    content_kind="twitter_tweet",
                    is_submitter=tweet.tweet_id == thread.thread_id,
                    node=tweet,
                )
        return None

    for post in social_content.generic_posts or []:
        if post.post_id != post_id:
            continue
        post_text = " ".join(part for part in (post.title, post.body) if part)
        if _matches_quote(quote, post_text):
            return ContributionRef(
                key=f"{post.platform}_post:{post.post_id}",
                text=post_text,
                contribution_id=post.post_id,
                author=post.author,
                community=post.platform,
                content_kind=f"{post.platform}_post",
                is_submitter=True,
                node=post,
            )
        for response in _iter_social_responses(post.responses):
            if _matches_quote(quote, response.body):
                return ContributionRef(
                    key=f"{post.platform}_response:{response.response_id}",
                    text=response.body,
                    contribution_id=response.response_id,
                    author=response.author,
                    community=post.platform,
                    content_kind=f"{post.platform}_response",
                    is_submitter=response.author == post.author,
                    node=response,
                )
        return None

    return None


def _top_level_candidates(social_content: SocialContentCollection) -> list[ContributionRef]:
    rows: list[tuple[int, ContributionRef]] = []
    for post in social_content.reddit_posts or []:
        rows.append((post.score, ContributionRef(
            key=f"reddit_post:{post.post_id}",
            text=" ".join(part for part in (post.title, post.selftext) if part),
            contribution_id=post.post_id,
            author=post.author,
            community=post.subreddit,
            content_kind="reddit_post",
            is_submitter=True,
            node=post,
        )))
    for post in social_content.generic_posts or []:
        rows.append((post.score, ContributionRef(
            key=f"{post.platform}_post:{post.post_id}",
            text=" ".join(part for part in (post.title, post.body) if part),
            contribution_id=post.post_id,
            author=post.author,
            community=post.platform,
            content_kind=f"{post.platform}_post",
            is_submitter=True,
            node=post,
        )))
    rows.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in rows[:10]]


def _source_counts(social_content: SocialContentCollection) -> Counter[str]:
    labels = [post.subreddit for post in social_content.reddit_posts or []]
    labels.extend(post.platform for post in social_content.generic_posts or [])
    labels.extend("twitter" for _ in social_content.twitter_threads or [])
    return Counter(label.lower().removeprefix("r/") for label in labels if label)


def _target_context(audience_mapping: Any, target: str) -> str:
    segments = getattr(audience_mapping, "audience_segments", None) or []
    segment = next((s for s in segments if getattr(s, "segment_name", None) == target), None)
    if segment is None:
        return "No additional segment description available."
    parts = [
        f"segment={getattr(segment, 'segment_name', '')}",
        f"pain alignment={'; '.join(getattr(segment, 'pain_point_alignment', None) or [])}",
        f"motivations={'; '.join(getattr(segment, 'motivation_drivers', None) or [])}",
        f"channels={'; '.join(getattr(segment, 'discovery_channels', None) or [])}",
    ]
    return " | ".join(parts)


def _collect_candidates(
    social_content: SocialContentCollection,
    pain_points: list[Any],
    target: str,
) -> list[ContributionRef]:
    by_key: dict[str, ContributionRef] = {}

    for pain_index, pain in enumerate(pain_points):
        quotes = getattr(pain, "representative_quotes", None) or []
        post_ids = getattr(pain, "source_post_ids", None) or []
        existing = list(getattr(pain, "speaker_attributions", None) or [])
        if len(existing) < len(quotes):
            existing.extend([None] * (len(quotes) - len(existing)))
        elif len(existing) > len(quotes):
            existing = existing[:len(quotes)]
        pain.speaker_attributions = existing

        for quote_index, quote in enumerate(quotes):
            prior = existing[quote_index]
            if prior is not None and prior.target_segment == target:
                continue
            post_id = post_ids[quote_index] if quote_index < len(post_ids) else ""
            ref = find_quote_contribution(social_content, post_id, quote)
            if ref is None:
                ref = ContributionRef(
                    key=f"unresolved_quote:{pain_index}:{quote_index}:{post_id}",
                    text=quote,
                    contribution_id=None,
                    author=None,
                    community="",
                    content_kind="unresolved_quote",
                    is_submitter=None,
                )
            merged = by_key.setdefault(ref.key, ref)
            merged.pain_refs.append((pain, quote_index))
            merged.pain_titles.add(getattr(pain, "title", ""))
            merged.evidence_segments.update(getattr(pain, "evidence_segments", None) or [])

    for ref in _top_level_candidates(social_content):
        prior = getattr(ref.node, "speaker_attribution", None)
        if prior is not None and prior.target_segment == target:
            continue
        if ref.key in by_key:
            continue
        by_key[ref.key] = ref

    return list(by_key.values())


def _unknown(ref: ContributionRef, target: str, reason: str) -> SpeakerAttribution:
    return SpeakerAttribution(
        role="unknown",
        confidence=0.0,
        rationale=reason,
        target_segment=target,
        contribution_id=ref.contribution_id,
        author=ref.author,
        is_submitter=ref.is_submitter,
        content_kind=ref.content_kind,
    )


def _assign(ref: ContributionRef, attribution: SpeakerAttribution) -> None:
    if ref.node is not None:
        ref.node.speaker_attribution = attribution
    for pain, quote_index in ref.pain_refs:
        pain.speaker_attributions[quote_index] = attribution


def _resolve_authoritative_buyer_review(
    tentative: SpeakerAttribution,
    review: _BuyerReviewVerdict | None,
    *,
    deterministic_scale_fit: ScaleFit,
    target_has_numeric_scale: bool,
) -> SpeakerAttribution:
    """Finalize a tentative buyer with adversarial review as sole authority.

    Deterministic positive signals may put an attribution into the tentative-buyer
    queue, but cannot confirm it or veto a correction. Grounded negative evidence
    can block confirmation. Consequently this function returns ``buyer`` only if
    the adversarial review explicitly confirms it and neither the review nor the
    source contradicts the target segment.
    """
    if tentative.role != "buyer":
        raise ValueError("Only tentative buyer attributions may enter buyer review")
    if review is not None and review.corrected_role is not None:
        rationale = review.rationale.strip() or (
            "Buyer-side role was corrected by the attribution review."
        )
        if target_has_numeric_scale and deterministic_scale_fit == "unknown":
            rationale = (
                "The attribution review corrected the buyer-side role from the full "
                "contribution; numeric scale remains unknown because there is no "
                "unambiguous same-unit comparison."
            )
        return tentative.model_copy(update={
            "role": review.corrected_role,
            "confidence": 0.0 if review.corrected_role == "unknown" else min(
                tentative.confidence, CONFIRMED_BUYER_CONFIDENCE - 0.01
            ),
            "rationale": rationale,
        })
    deterministic_contradiction = deterministic_scale_fit == "contradicts"
    review_contradiction = (
        not target_has_numeric_scale
        and review is not None
        and review.segment_fit == "contradicts"
    )
    if deterministic_contradiction or review_contradiction:
        return tentative.model_copy(update={
            "role": "adjacent_worker",
            "confidence": min(
                tentative.confidence, CONFIRMED_BUYER_CONFIDENCE - 0.01
            ),
            "rationale": (
                "The speaker's explicit same-unit scale is outside the target interval."
                if deterministic_contradiction
                else review.rationale.strip()
            ),
        })
    if (
        review is not None
        and review.confirmed
        and review.corrected_role is None
    ):
        return tentative

    return tentative.model_copy(update={
        "role": "unknown",
        "confidence": 0.0,
        "rationale": (
            review.rationale.strip()
            if review is not None and review.rationale.strip()
            else "Buyer-side role could not be confirmed by the attribution review."
        ),
    })


def attribute_evidence_speakers(
    social_content: SocialContentCollection,
    pain_points: list[Any],
    audience_mapping: Any,
    *,
    cost_tracker: Any | None = None,
    batch_size: int = ATTRIBUTION_BATCH_SIZE,
) -> SpeakerAttributionRun:
    """Classify evidence speakers in batches and persist every outcome.

    A failed or incomplete batch is explicitly stamped ``unknown``. The function
    never substitutes role vocabulary, community membership, or engagement for a
    missing model judgment.
    """
    target = (getattr(audience_mapping, "primary_target_segment", None) or "").strip()
    if not target:
        return SpeakerAttributionRun(False, 0, 0, 0, 0)
    if (
        social_content.speaker_attribution_version == ATTRIBUTION_VERSION
        and social_content.speaker_attribution_target == target
    ):
        return SpeakerAttributionRun(False, 0, 0, 0, 0)

    candidates = _collect_candidates(social_content, pain_points, target)
    counts = _source_counts(social_content)
    hubs = getattr(audience_mapping, "community_hubs", None) or []
    normalized_hubs = {str(h).lower().removeprefix("r/") for h in hubs}
    context = _target_context(audience_mapping, target)
    llm_calls = 0
    failed_batches = 0
    unknown_count = 0
    tentative_buyers: list[tuple[ContributionRef, SpeakerAttribution]] = []

    for start in range(0, len(candidates), max(1, batch_size)):
        batch = candidates[start:start + max(1, batch_size)]
        payload = []
        for index, ref in enumerate(batch, start=1):
            community = ref.community.lower().removeprefix("r/")
            payload.append(json.dumps({
                "index": index,
                "text": _sanitize_text(ref.text)[:800],
                "speaker_context": _sanitize_text(ref.speaker_context)[:800] or None,
                "author": _sanitize_text(ref.author) if ref.author else None,
                "contribution_id": ref.contribution_id,
                "content_kind": ref.content_kind,
                "is_submitter": ref.is_submitter,
                "community": ref.community or None,
                "community_post_count": counts.get(community, 0),
                "community_is_llm_hub_prior": community in normalized_hubs,
                "pain_titles": sorted(ref.pain_titles),
                "pain_evidence_segments": sorted(ref.evidence_segments),
                "pain_provenance_includes_target": target in ref.evidence_segments,
            }, ensure_ascii=False))

        prompt = get_prompt(
            "speaker_attribution",
            target_segment=target,
            target_context=context,
            community_hubs=", ".join(str(h) for h in hubs) or "none",
            candidates_text="\n".join(payload),
            candidate_count=len(batch),
        )
        verdicts: dict[int, _AttributionVerdict] = {}
        try:
            llm_calls += 1
            response, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=_BatchAttributionResponse,
                temperature=0,
                timeout=180,
                model_name=settings.content_analysis_llm,
                reasoning_effort="none",
            )
            if cost_tracker is not None and usage is not None:
                cost_tracker.record_llm_usage(
                    "Stage 4 - Speaker Attribution", usage.to_dict()
                )
            for verdict in response.attributions:
                if 1 <= verdict.index <= len(batch) and verdict.index not in verdicts:
                    verdicts[verdict.index] = verdict
        except Exception as exc:  # fail-honest per batch
            failed_batches += 1
            logger.warning(
                f"[Speaker Attribution] batch {start // max(1, batch_size) + 1} failed; "
                f"stamping {len(batch)} contributions unknown: {exc}"
            )

        for index, ref in enumerate(batch, start=1):
            verdict = verdicts.get(index)
            if verdict is None:
                attribution = _unknown(
                    ref,
                    target,
                    "Speaker role could not be confirmed from the available evidence.",
                )
            else:
                identity_evidence = (verdict.identity_evidence or "").strip() or None
                authority_evidence = (verdict.authority_evidence or "").strip() or None
                evidence_haystack = _normalized(
                    " ".join(filter(None, (ref.text, ref.speaker_context, ref.author)))
                )
                identity_grounded = bool(
                    identity_evidence
                    and _normalized(identity_evidence) in evidence_haystack
                )
                authority_grounded = bool(
                    authority_evidence
                    and _normalized(authority_evidence) in evidence_haystack
                )
                role = verdict.role
                confidence = verdict.confidence
                rationale = verdict.rationale.strip() or "No role evidence supplied."
                if role == "buyer" and (
                    not identity_grounded or confidence < CONFIRMED_BUYER_CONFIDENCE
                ):
                    role = "adjacent_worker" if identity_grounded else "unknown"
                    confidence = min(confidence, CONFIRMED_BUYER_CONFIDENCE - 0.01)
                    rationale = (
                        "Primary-target membership was not grounded strongly enough in "
                        "verbatim source evidence to confirm a buyer-side voice."
                    )
                elif (
                    role == "adjacent_worker"
                    and identity_grounded
                    and confidence >= CONFIRMED_BUYER_CONFIDENCE
                    and _has_direct_operational_control(ref.text)
                    and _identity_matches_target_context(
                        identity_evidence, target, context, hubs
                    )
                ):
                    # This heuristic proposes a tentative buyer only. The role is
                    # not persisted unless the adversarial pass confirms it.
                    role = "buyer"
                    rationale = (
                        "The contribution grounds target-side identity and direct operational "
                        "control through tool selection and staff delegation."
                    )
                attribution = SpeakerAttribution(
                    role=role,
                    confidence=confidence,
                    rationale=rationale,
                    identity_evidence=identity_evidence if identity_grounded else None,
                    authority_evidence=authority_evidence if authority_grounded else None,
                    target_segment=target,
                    contribution_id=ref.contribution_id,
                    author=ref.author,
                    is_submitter=ref.is_submitter,
                    content_kind=ref.content_kind,
                )
            if attribution.role == "buyer":
                tentative_buyers.append((ref, attribution))
            else:
                if attribution.role == "unknown":
                    unknown_count += 1
                _assign(ref, attribution)

    for start in range(0, len(tentative_buyers), max(1, batch_size)):
        review_batch = tentative_buyers[start:start + max(1, batch_size)]
        review_payload = [
            json.dumps({
                "index": index,
                "text": _sanitize_text(ref.text)[:1200],
                "speaker_context": _sanitize_text(ref.speaker_context)[:800] or None,
                "identity_evidence": attribution.identity_evidence,
                "authority_evidence": attribution.authority_evidence,
                "initial_rationale": attribution.rationale,
                "explicit_target_segment_contradiction": (
                    _explicitly_below_target_scale(
                        target, " ".join((ref.text, ref.speaker_context))
                    )
                ),
                "deterministic_segment_fit": _compare_segment_scale(
                    target, " ".join((ref.text, ref.speaker_context))
                ),
                "tool_selection_and_staff_delegation_signal": (
                    _has_direct_operational_control(ref.text)
                ),
            }, ensure_ascii=False)
            for index, (ref, attribution) in enumerate(review_batch, start=1)
        ]
        prompt = get_prompt(
            "speaker_attribution_review",
            target_segment=target,
            target_context=context,
            candidates_text="\n".join(review_payload),
            candidate_count=len(review_batch),
        )
        reviews: dict[int, _BuyerReviewVerdict] = {}
        try:
            llm_calls += 1
            response, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=_BuyerReviewResponse,
                temperature=0,
                timeout=180,
                model_name=settings.content_analysis_llm,
                reasoning_effort="none",
            )
            if cost_tracker is not None and usage is not None:
                cost_tracker.record_llm_usage(
                    "Stage 4 - Speaker Attribution Review", usage.to_dict()
                )
            for review in response.reviews:
                if 1 <= review.index <= len(review_batch) and review.index not in reviews:
                    reviews[review.index] = review
        except Exception as exc:  # fail-honest: an unreviewed buyer is not confirmed
            failed_batches += 1
            logger.warning(
                f"[Speaker Attribution] buyer review batch "
                f"{start // max(1, batch_size) + 1} failed; demoting "
                f"{len(review_batch)} tentative buyers to unknown: {exc}"
            )

        for index, (ref, attribution) in enumerate(review_batch, start=1):
            review = reviews.get(index)
            deterministic_scale_fit = _compare_segment_scale(
                target, " ".join((ref.text, ref.speaker_context))
            )
            resolved = _resolve_authoritative_buyer_review(
                attribution,
                review,
                deterministic_scale_fit=deterministic_scale_fit,
                target_has_numeric_scale=_parse_scale(target) is not None,
            )
            if resolved.role == "unknown":
                unknown_count += 1
            _assign(ref, resolved)

    social_content.speaker_attribution_version = ATTRIBUTION_VERSION
    social_content.speaker_attribution_target = target
    return SpeakerAttributionRun(True, len(candidates), llm_calls, unknown_count, failed_batches)
