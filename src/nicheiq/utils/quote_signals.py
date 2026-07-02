"""Incumbent-dissatisfaction quote signals (2026-07-02, A/B-validated, always on).

The raw corpus carries named-incumbent dissatisfaction ("Do you use anything for pricing?
I don't like CakeCost.") — the strongest demand marker a corpus can produce: a buyer with a
tool they pay for (or tried), unhappy, asking for alternatives. The pain-quote funnel
distills quotes that EVIDENCE pains and reliably drops these lines, so this detector scans
the RAW social content sentence-by-sentence. Deterministic — no LLM.
"""
import re

# Phrases that mark dissatisfaction when they co-occur with an incumbent name in a sentence.
# Deliberately RECALL-oriented (an LLM precision gate filters candidates downstream) but the
# weakest markers ("alternative to", "instead of", "missing", "wish it") were dropped after a
# 3-corpus validation showed they contributed only recommendation/rhetorical noise.
_NEGATIVE_MARKERS = (
    "don't like", "dont like", "do not like", "hate", "can't stand", "too expensive",
    "overpriced", "switched from", "gave up on", "stopped using", "clunky", "frustrat",
    "annoying", "terrible", "doesn't work", "doesnt work", "not worth", "cancel",
    "moving away from", "outgrew", "lacks", "disappointed", "looks terrible",
)

# Generic tools people name-drop without it meaning an incumbent gap in THIS niche.
_GENERIC_TOOL_NAMES = {
    "google", "excel", "instagram", "facebook", "youtube", "reddit", "tiktok", "twitter",
    "whatsapp", "paypal", "venmo", "amazon", "etsy", "gmail", "iphone", "android", "chrome",
    "chatgpt", "google calendar", "google sheets", "square", "usps", "nextdoor",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _name_pattern(name: str) -> "re.Pattern[str] | None":
    name = (name or "").strip()
    if len(name) < 3 or name.lower() in _GENERIC_TOOL_NAMES or name.endswith(":"):
        return None
    return re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)


def iter_corpus_texts(social_content) -> "list[tuple[str, str]]":
    """(text, source_label) pairs from a SocialContentCollection: Reddit post titles+bodies,
    comment bodies, and generic-source posts. Defensive against missing fields."""
    out: list[tuple[str, str]] = []
    if social_content is None:
        return out
    for p in (getattr(social_content, "reddit_posts", None) or []):
        src = f"r/{getattr(p, 'subreddit', '?')}"
        out.append((f"{getattr(p, 'title', '') or ''}. {getattr(p, 'selftext', '') or ''}", src))
        for c in (getattr(p, "comments", None) or []):
            out.append((getattr(c, "body", "") or "", src))
            for rc in (getattr(c, "replies", None) or []):
                out.append((getattr(rc, "body", "") or "", src))
    for g in (getattr(social_content, "generic_posts", None) or []):
        out.append((getattr(g, "content", "") or "", getattr(g, "platform", "?") or "?"))
    return out


def detect_incumbent_dissatisfaction(texts, incumbent_names,
                                     max_signals: int = 6, max_quote_len: int = 200) -> list[str]:
    """Scan (text, source) pairs sentence-by-sentence for incumbent names co-occurring with a
    negative marker. Returns formatted lines '<Name> — "<sentence>" (<source>)', deduped."""
    patterns = [(n.strip(), p) for n in (incumbent_names or [])
                if (p := _name_pattern(n)) is not None]
    if not patterns:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for text, source in texts or []:
        if not text:
            continue
        tl = text.lower()
        if not any(m in tl for m in _NEGATIVE_MARKERS):
            continue
        for sent in _SENTENCE_SPLIT.split(text):
            sl = sent.lower()
            if not any(m in sl for m in _NEGATIVE_MARKERS):
                continue
            for name, pat in patterns:
                if pat.search(sent):
                    key = " ".join(sl.split())[:80]
                    if key in seen:
                        continue
                    seen.add(key)
                    quote = sent.strip()
                    if len(quote) > max_quote_len:
                        quote = quote[:max_quote_len].rsplit(" ", 1)[0].rstrip(" ,;.") + "…"
                    out.append(f'{name} — "{quote}" ({source})')
                    break
            if len(out) >= max_signals:
                return out
    return out


def format_dissatisfaction_block(signals: list[str]) -> str:
    """Render detected signals as the prompt block shared by ideation briefs, the
    calibration critic, and synthesis. '' when no signals (blocks render nothing)."""
    if not signals:
        return ""
    return ("### INCUMBENT DISSATISFACTION (verbatim, from community)\n"
            "Real buyers naming a tool they are unhappy with — the strongest demand signal in "
            "this corpus. An idea that credibly fixes WHY these users are unhappy starts with "
            "demand already proven:\n" + "\n".join(f"- {s}" for s in signals))
