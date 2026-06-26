"""Shared prompt-injection defenses for untrusted (scraped) content.

Canonical home for the sanitize + delimiter-fence helpers. These were originally
private to ``pain_point_crew``; they live here so every prompt builder that injects
scraped social content (pain extraction, the feasibility/novelty critic, solution
reinjection, competitor mentions) can reuse the SAME defense instead of each
re-implementing or skipping it.

Defense is delimiter fencing + a shallow injection-pattern scrub. The fencing is the
real control (models are told to treat fenced blocks as data); the regex is a
best-effort scrub, not a guarantee.
"""

import re

# Known prompt-injection patterns to strip from scraped content.
_INJECTION_PATTERNS = re.compile(
    r"(?i)(ignore\s+(all\s+)?previous\s+instructions|"
    r"you\s+are\s+now\s+|"
    r"^SYSTEM:|^ASSISTANT:|^USER:|"
    r"<\|(?:im_start|im_end|endoftext)\|>|"
    r"\bdo\s+not\s+follow\s+any\s+(?:other|previous)\b)",
)

# Fence-forgery signature. fence_content wraps content with "======== ... ========"
# delimiter lines; scraped text containing a byte-identical '=' run (on its own line OR
# mid-line, e.g. inside a post title) could forge a fence closer so everything after it
# reads as out-of-band/trusted. The '=' run IS the signature, so collapse any run of >=6
# '=' anywhere BEFORE wrapping. The real fence added by fence_content (after sanitize)
# is unaffected.
_FENCE_DELIM = re.compile(r"={6,}")


def sanitize_social_content(text: str) -> str:
    """Strip control characters, fence-forgery delimiters, and known injection patterns."""
    if not text:
        return ""
    # Remove control characters except standard whitespace
    sanitized = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")
    # Neutralize forged fence delimiters so scraped text can't break out of fencing
    sanitized = _FENCE_DELIM.sub("[REDACTED FENCE]", sanitized)
    # Strip known injection patterns
    sanitized = _INJECTION_PATTERNS.sub("[REDACTED]", sanitized)
    return sanitized


def fence_content(text: str, source: str, item_id: str = "", label: str = "UNTRUSTED CONTENT") -> str:
    """Wrap untrusted content in delimiter-based fencing for prompt-injection defense.

    Uses delimiters instead of XML tags because CrewAI's StringKnowledgeSource chunks
    text for embedding — XML tags get severed across chunk boundaries, but delimiter
    lines survive chunking on their own lines. ``label`` lets callers keep an existing
    header wording (e.g. pain extraction uses "UNTRUSTED SOCIAL CONTENT").
    """
    sanitized = sanitize_social_content(text)
    header = (
        f"======== {label} (source={source}, id={item_id}) ========"
        if item_id
        else f"======== {label} (source={source}) ========"
    )
    return f"{header}\n{sanitized}\n======== END UNTRUSTED CONTENT ========"
