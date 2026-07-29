import type { OverlapGroup } from "$lib/types/report";

/** An overlap group with two or more of its members currently on the shortlist. */
export interface ShortlistOverlap {
  /** Only the shortlisted members — not the whole group. Display titles, not internal names. */
  ideaNames: string[];
  sharedProduct: string;
}

/**
 * A shortlisted idea, carrying both names.
 *
 * `overlap_groups` is keyed on the pipeline's internal `solution_name` ("ConsolidatorAI"),
 * but every surface the reader can see shows the headline ("Auto-consolidate 50+ QuickBooks/
 * Xero trial balances"). Match on one, print the other — naming the ideas in a vocabulary
 * that appears nowhere else on the page makes the warning unactionable.
 */
export interface ShortlistedIdea {
  /** Internal solution_name — matched against OverlapGroup.idea_names. */
  name: string;
  /** What the reader sees elsewhere on the page. */
  label: string;
}

/**
 * Overlap groups the pipeline flagged as the same underlying product, restricted to
 * groups with two or more members on the shortlist.
 *
 * Deep Research funds at most three ideas. Two shortlisted variants of one product
 * spend two of those slots answering the same question, and nothing in the commit
 * path said so — the groups were computed upstream but only ever surfaced in the
 * dossier appendix, which nobody reads before paying.
 *
 * This is a warning, never a block: convergence can be the honest answer when a niche
 * really does point at one product, and comparing two framings of it is a legitimate
 * thing to buy. The user just has to know they're buying it.
 */
export function shortlistOverlaps(
  overlapGroups: OverlapGroup[] | null | undefined,
  shortlisted: Iterable<ShortlistedIdea>,
): ShortlistOverlap[] {
  const labelByName = new Map<string, string>();
  for (const idea of shortlisted) labelByName.set(idea.name, idea.label || idea.name);

  const overlaps: ShortlistOverlap[] = [];
  for (const group of overlapGroups ?? []) {
    const hits = (group.idea_names ?? [])
      .filter((name) => labelByName.has(name))
      .map((name) => labelByName.get(name)!);
    if (hits.length < 2) continue;
    overlaps.push({ ideaNames: hits, sharedProduct: group.shared_product });
  }
  return overlaps;
}

/**
 * One sentence naming the colliding ideas and what they share. Kept in one place so
 * the shortlist dock and the commit gate cannot drift into describing the same
 * finding two different ways.
 */
export function overlapWarningText(overlap: ShortlistOverlap): string {
  const names = overlap.ideaNames.join(" and ");
  const product = overlap.sharedProduct?.trim();
  return product
    ? `${names} are variants of the same product (${product}). Researching both spends two slots on one question.`
    : `${names} are variants of the same product. Researching both spends two slots on one question.`;
}
