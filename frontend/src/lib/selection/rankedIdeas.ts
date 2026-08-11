/** The return target shared by every selection surface and the visible first idea row. */
export const RANKED_IDEAS_ANCHOR = "idea-select-0";

export function rankedIdeasHref(jobId: string): string {
  return `/jobs/${jobId}#${RANKED_IDEAS_ANCHOR}`;
}
