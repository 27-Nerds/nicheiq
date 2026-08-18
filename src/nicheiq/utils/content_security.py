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


# Runaway backstop for model-authored fields rendered into a prompt.
#
# MEASURED 2026-08-18 over 3,626 checkpoint JSONs: this bound binds on 0.00% of
# technical_approach / value_proposition / why_it_works / description and 0.07% of
# content_generation_model (one pathological 5,283-char generation). It exists ONLY to stop a
# runaway generation from flooding a prompt.
#
# It is NOT a context-window budget. Every prompt these fields feed is a few KB against
# models with >=256K context, so a limit that trims a normal value is a semantic edit wearing
# a length limit's clothes. Before lowering this, re-run the bind-rate measurement: cutting
# technical_approach (median 522 chars) at 200 silently removed the mechanism from 94.9% of
# stamped ideas -- 95.9% of DISTINCT ones -- at the exact moment the calibration critic
# scored them. Quote the denominator with any such rate: the checkpoint corpus is ~47%
# regenerate/fork duplicates, so all-values and distinct-values figures differ by ~1pp and
# a bare percentage here is ambiguous.
PROMPT_FIELD_MAX = 2000


def prompt_field(value: object, limit: int = PROMPT_FIELD_MAX) -> str:
    """Render a model-authored field for a prompt, bounded only by a runaway backstop.

    When the backstop fires the result carries a visible marker. A silent mid-word cut hands
    the receiving model a garbled token and no signal that anything is missing -- it cannot
    distinguish "the mechanism does not cover this" from "the sentence saying so was cut".

    Does NOT sanitize: callers that need the injection scrub wrap the value in
    ``sanitize_social_content`` themselves, and adding it here would silently change the text
    at call sites that deliberately render trusted, model-authored content.
    """
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …[truncated]"


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
