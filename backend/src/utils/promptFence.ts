/**
 * TS mirror of `src/nicheiq/utils/content_security.py` (`fence_content` /
 * `sanitize_social_content`). Keep behavior identical — same delimiter shape, same
 * injection-pattern scrub, same fence-forgery collapse — so a quote that's safe in
 * the Python pipeline is safe here too. Every dossier string handed to the guided-chat
 * LLM (backend/src/routes/chat.ts) MUST pass through `fenceContent()` before it
 * reaches the prompt.
 */

// Known prompt-injection patterns to strip from untrusted content.
const INJECTION_PATTERNS =
  /(ignore\s+(all\s+)?previous\s+instructions|you\s+are\s+now\s+|^SYSTEM:|^ASSISTANT:|^USER:|<\|(?:im_start|im_end|endoftext)\|>|\bdo\s+not\s+follow\s+any\s+(?:other|previous)\b)/gim;

// Fence-forgery signature. fenceContent wraps content with "======== ... ========"
// delimiter lines; untrusted text containing a byte-identical '=' run (on its own
// line OR mid-line) could forge a fence closer so everything after it reads as
// out-of-band/trusted. Collapse any run of >=6 '=' anywhere BEFORE wrapping.
const FENCE_DELIM = /={6,}/g;

/** Strip control characters, fence-forgery delimiters, and known injection patterns. */
export function sanitizeUntrustedContent(text: string): string {
  if (!text) return '';
  // Remove control characters except standard whitespace (\n \r \t)
  let sanitized = Array.from(text)
    .filter((c) => c.charCodeAt(0) >= 32 || c === '\n' || c === '\r' || c === '\t')
    .join('');
  // Neutralize forged fence delimiters so untrusted text can't break out of fencing
  sanitized = sanitized.replace(FENCE_DELIM, '[REDACTED FENCE]');
  // Strip known injection patterns
  sanitized = sanitized.replace(INJECTION_PATTERNS, '[REDACTED]');
  return sanitized;
}

/**
 * Wrap untrusted content in delimiter-based fencing for prompt-injection defense.
 * Delimiter lines (not XML tags) so the fence survives any downstream chunking.
 */
export function fenceContent(
  text: string,
  source: string,
  itemId = '',
  label = 'UNTRUSTED CONTENT'
): string {
  const sanitized = sanitizeUntrustedContent(text);
  const header = itemId
    ? `======== ${label} (source=${source}, id=${itemId}) ========`
    : `======== ${label} (source=${source}) ========`;
  return `${header}\n${sanitized}\n======== END UNTRUSTED CONTENT ========`;
}
