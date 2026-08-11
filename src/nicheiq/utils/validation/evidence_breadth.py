"""Evidence breadth for the "Check my idea" report block (plan P5.23).

Deterministic aggregation over linkage that already exists — ``PainPoint.source_post_ids``
resolved against the collected posts (reddit AND generic; the older lookups in
``utils/evidence_sources.py`` are reddit-only and would undercount HN). Direct linkage
only: when the cited posts can't be resolved, the caller renders "not enough linked
evidence" — there is deliberately NO niche-level fallback (a niche-wide number would not
be about the user's idea).

``distinct_authors`` counts posting accounts of the cited threads (quote-level authorship
isn't tracked) — label it that way in UI copy.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _post_lookup(social) -> dict[str, object]:
    lookup: dict[str, object] = {}
    for attr in ("reddit_posts", "generic_posts"):
        for post in getattr(social, attr, None) or []:
            post_id = getattr(post, "post_id", None)
            if post_id:
                lookup[post_id] = post
    return lookup


def _community(post) -> str | None:
    sub = getattr(post, "subreddit", None)
    if sub:
        return f"r/{sub}" if not str(sub).startswith("r/") else str(sub)
    platform = getattr(post, "platform", None)
    return str(platform) if platform else None


def _as_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def compute_evidence_breadth(pains: list, social, anchor_titles: list[str]) -> dict | None:
    """Breadth stats for the pains the user's idea anchors to.

    Returns None when no anchored pain resolves to at least one collected post —
    the honest "not enough linked evidence" case.
    """
    wanted = {t.strip().lower() for t in (anchor_titles or []) if t and t.strip()}
    if not wanted or social is None:
        return None
    lookup = _post_lookup(social)
    if not lookup:
        return None

    posts: list = []
    seen_ids: set[str] = set()
    for pain in pains or []:
        title = (getattr(pain, "title", None) or "").strip().lower()
        if title not in wanted:
            continue
        for post_id in getattr(pain, "source_post_ids", None) or []:
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)
            post = lookup.get(post_id)
            if post is not None:
                posts.append(post)
    if not posts:
        return None

    authors = {a for a in ((getattr(p, "author", None) or "").strip() for p in posts) if a}
    communities = {c for c in (_community(p) for p in posts) if c}
    stamps = [dt for dt in (_as_dt(getattr(p, "created_utc", None)) for p in posts) if dt]
    months_spanned = 0
    if stamps:
        lo, hi = min(stamps), max(stamps)
        months_spanned = max(1, (hi.year - lo.year) * 12 + (hi.month - lo.month) + 1)

    return {
        "posts": len(posts),
        "distinct_authors": len(authors),
        "distinct_communities": len(communities),
        "months_spanned": months_spanned,
        "label": (f"{len(posts)} posts · {len(authors)} accounts · "
                  f"{len(communities)} communities · {months_spanned} mo"),
    }


MILD_ANCHOR_NOTE = "Breadth is broad but the matched problem is mild."


def compute_evidence_confidence(
    breadth: dict | None,
    incumbent_parity: str | None,
    anchored_quality: bool = True,
) -> tuple[str, str]:
    """(Low|Moderate|High, reason). Deterministic; a parity HIT (a named shipping
    competitor — third-party behavioral evidence) may RAISE confidence one band; a
    parity miss never lowers anything ("no competitors found" is a known-weak signal).

    `anchored_quality` is False when no anchored pain reaches at least a moderate
    severity band. Ordering is pinned: base band → parity lift (upward only) →
    anchored-quality cap LAST (cap wins) — High on breadth alone over-read the live
    run, whose 9-post breadth anchored to a severity-0.43 pain.
    """
    parity = (incumbent_parity or "").strip().lower()
    parity_hit = parity.startswith(("shipped", "partial", "substitute", "bundled"))

    if not breadth:
        if parity_hit:
            return "Moderate", (
                "No collected discussion links directly to your idea's problem, but a "
                "named competitor already ships in this space — third-party proof the "
                "problem gets paid attention.")
        return "Low", "No collected discussion could be linked directly to your idea's problem."

    posts = breadth.get("posts", 0)
    authors = breadth.get("distinct_authors", 0)
    months = breadth.get("months_spanned", 0)
    # Qualitative only: the numbers already live in the record line the block renders
    # right above this reason — repeating them here made the same stats stutter.
    if posts >= 8 and authors >= 5 and months >= 3:
        band = "High"
        reason = "Broad, repeated discussion from distinct accounts."
    elif posts >= 3 and authors >= 2:
        band = "Moderate"
        reason = "Real but not broad."
    else:
        band = "Low"
        post_word = "post" if posts == 1 else "posts"
        reason = f"Only {posts} linked {post_word} — too thin to lean on."

    if parity_hit and band == "Low":
        band = "Moderate"
        reason += " A named competitor already ships in this space — third-party proof the problem gets paid attention."
    elif parity_hit and band == "Moderate":
        band = "High"
        reason += " Corroborated by a named shipping competitor."

    if band == "High" and not anchored_quality:
        band = "Moderate"
        reason += f" {MILD_ANCHOR_NOTE}"
    return band, reason
