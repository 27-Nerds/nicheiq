"""Honest-brief assembly helpers (2026-07-02).

The report's idea cards previously rendered only the generator's voice (value prop,
differentiators). These helpers surface the other two voices already persisted in state:
verbatim community quotes for the addressed pains (evidence) and the calibration critic's
market_fit reason (bear case). Shared by report_generator (Phase-2 alternatives) and the
Phase-1 preview materializer.
"""


def build_quotes_by_pain(pain_points) -> dict[str, list[str]]:
    """{lowercased pain title: [verbatim quotes]} from PainPoint-like objects."""
    out: dict[str, list[str]] = {}
    for p in pain_points or []:
        title = (getattr(p, "title", "") or "").strip().lower()
        if title:
            out[title] = list(getattr(p, "representative_quotes", None) or [])
    return out


def demand_quotes_for(pain_titles, quotes_by_pain: dict[str, list[str]],
                      max_quotes: int = 3, max_len: int = 220) -> list[str]:
    """Up to max_quotes verbatim quotes, round-robin across the addressed pains so one
    quote-rich pain doesn't crowd out the others. Long quotes truncate at a word boundary."""
    pools = [
        [q for q in quotes_by_pain.get((t or "").strip().lower(), []) if q]
        for t in (pain_titles or [])
    ]

    def _overlaps(q: str, kept: list[str]) -> bool:
        # source pains often share overlapping quote fragments — containment on a
        # normalized prefix catches near-duplicates exact matching misses
        probe = " ".join(q.lower().split())[:60]
        for k in kept:
            kn = " ".join(k.lower().split())
            if probe and (probe in kn or kn[:60] in " ".join(q.lower().split())):
                return True
        return False

    quotes: list[str] = []
    rank = 0
    while len(quotes) < max_quotes and any(len(p) > rank for p in pools):
        for pool in pools:
            if rank < len(pool) and len(quotes) < max_quotes:
                q = pool[rank].strip()
                if len(q) > max_len:
                    q = q[:max_len].rsplit(" ", 1)[0].rstrip(" ,;.") + "…"
                if not _overlaps(q, quotes):
                    quotes.append(q)
        rank += 1
    return quotes
