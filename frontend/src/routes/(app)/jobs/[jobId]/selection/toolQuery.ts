// One-shot `?tool=` deep-link bookkeeping for the selection layout.
//
// The layout's tool effect dedupes on a URL signature so a re-run of the same
// reactive tick can't open a tool twice. The guard must MOVE with the
// lifecycle, though: it originally stored the with-tool signature forever, so
// a repeat navigation to the identical deep link neither reopened the tool nor
// stripped the query — the URL was stuck (P0-E). Once the params are stripped
// (or the tool is closed), the guard re-arms by storing the post-strip
// signature instead, which can never match a future with-tool URL.

/** Params that are one-shot open instructions, never workspace state. */
export const TOOL_QUERY_KEYS = ["tool", "assumptionId"] as const;

/** Signature of a URL — what the dedupe guard stores and compares. */
export function toolQuerySignature(url: URL): string {
  return `${url.pathname}${url.search}`;
}

/** The signature the URL will have AFTER the one-shot params are stripped.
 *  Storing this re-arms the guard: a repeat navigation to the same `?tool=`
 *  link reads as new and reopens the tool. */
export function strippedToolSignature(url: URL): string {
  const stripped = new URL(url);
  for (const key of TOOL_QUERY_KEYS) stripped.searchParams.delete(key);
  return toolQuerySignature(stripped);
}

/** Clears only the payload consumed by a tool. Caller provenance must survive
 * until that tool actually closes, even though its `?tool=` instruction does
 * not remain in the URL. */
export function stateAfterToolQueryStrip(state: App.PageState): App.PageState {
  return {
    ...state,
    selectionTestDraft: undefined,
  };
}
