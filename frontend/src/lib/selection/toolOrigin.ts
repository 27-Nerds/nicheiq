export interface SelectionToolOrigin {
  tool: "variants";
  jobId: string;
  returnHref: string;
  historyOwned: true;
}

/** Marks a routed tool as having been pushed from the current job page. */
export function createSelectionToolOrigin(
  url: URL,
  jobId: string,
): SelectionToolOrigin {
  return {
    tool: "variants",
    jobId,
    returnHref: `${url.pathname}${url.search}${url.hash}`,
    historyOwned: true,
  };
}

/**
 * Page state is browser-owned input. Only honor a return target that points to
 * the exact current job page on this origin.
 */
export function trustedSelectionToolOrigin(
  value: unknown,
  currentOrigin: string,
  jobId: string,
): SelectionToolOrigin | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<SelectionToolOrigin>;
  if (
    candidate.tool !== "variants"
    || candidate.jobId !== jobId
    || candidate.historyOwned !== true
    || typeof candidate.returnHref !== "string"
    || !candidate.returnHref.startsWith("/")
    || candidate.returnHref.startsWith("//")
  ) {
    return null;
  }

  try {
    const target = new URL(candidate.returnHref, currentOrigin);
    const expectedPath = `/jobs/${encodeURIComponent(jobId)}`;
    if (target.origin !== currentOrigin || target.pathname !== expectedPath) return null;
  } catch {
    return null;
  }

  return candidate as SelectionToolOrigin;
}
