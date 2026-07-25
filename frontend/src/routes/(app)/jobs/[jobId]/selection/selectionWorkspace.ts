import type { Job, SelectionDraftItem, SolutionPreview } from "$lib/types/job";

const MAX_SCOPE_IDEAS = 3;

const LENSES = ["demand", "distribution", "competition", "dependencies"] as const;
const COMPARE_VIEWS = ["market", "founder"] as const;
const ALTERNATIVE_MODES = ["diverge", "resolve_tradeoff", "reshape"] as const;

export type SelectionWorkspaceLens = (typeof LENSES)[number];
export type SelectionCompareView = (typeof COMPARE_VIEWS)[number];
export type SelectionAlternativeMode = (typeof ALTERNATIVE_MODES)[number];
export type SelectionWorkspaceScopeSource = "url" | "draft" | "preview";

export const SELECTION_LIFECYCLE_CONTEXT = Symbol("selection-workspace-lifecycle");

export interface SelectionWorkspaceLifecycle {
  status: Job["status"] | "";
  canMutate: boolean;
}

export interface SelectionWorkspaceRef {
  ideaId: string;
  ideaRevision: number;
}

export interface SelectionWorkspaceState {
  ideas: SolutionPreview[];
  refs: SelectionWorkspaceRef[];
  notices: string[];
  lens: SelectionWorkspaceLens;
  compareView: SelectionCompareView;
  alternativeMode: SelectionAlternativeMode;
  scopeSource: SelectionWorkspaceScopeSource;
  canonicalQuery: string;
}

function currentRef(idea: SolutionPreview): SelectionWorkspaceRef | null {
  if (!idea.idea_id) return null;
  return {
    ideaId: idea.idea_id,
    ideaRevision: idea.idea_revision ?? 1,
  };
}

function parseRef(value: string): SelectionWorkspaceRef | null {
  const token = value.trim();
  const separator = Math.max(token.lastIndexOf(":"), token.lastIndexOf("@"));
  if (separator <= 0 || separator === token.length - 1) return null;

  const ideaId = token.slice(0, separator).trim();
  const revision = Number(token.slice(separator + 1));
  if (!ideaId || ideaId.length > 200 || !Number.isSafeInteger(revision) || revision < 1) return null;

  return { ideaId, ideaRevision: revision };
}

function findExactIdea(
  solutions: SolutionPreview[],
  ref: SelectionWorkspaceRef,
): SolutionPreview | undefined {
  return solutions.find((idea) => {
    const candidateRef = currentRef(idea);
    return candidateRef?.ideaId === ref.ideaId && candidateRef.ideaRevision === ref.ideaRevision;
  });
}

function resolveFallback(
  job: Job,
  solutions: SolutionPreview[],
): { ideas: SolutionPreview[]; usedTopCandidates: boolean } {
  const draftItems: SelectionDraftItem[] = job.selectionDraft?.items ?? [];
  const drafted = draftItems
    .map((ref) => findExactIdea(solutions, ref))
    .filter((idea): idea is SolutionPreview => Boolean(idea))
    .slice(0, MAX_SCOPE_IDEAS);

  if (drafted.length > 0) return { ideas: drafted, usedTopCandidates: false };
  return { ideas: solutions.slice(0, 2), usedTopCandidates: solutions.length > 0 };
}

function pickEnum<const T extends readonly string[]>(
  value: string | null,
  allowed: T,
  fallback: T[number],
  label: string,
  notices: string[],
): T[number] {
  if (!value) return fallback;
  if ((allowed as readonly string[]).includes(value)) return value as T[number];
  notices.push(`The requested ${label} is not available. Showing the default instead.`);
  return fallback;
}

function resolveAlternativeMode(
  value: string | null,
  ideaCount: number,
  notices: string[],
): SelectionAlternativeMode {
  const fallback: SelectionAlternativeMode = ideaCount === 2 ? "resolve_tradeoff" : "diverge";
  if (!value) return fallback;
  if ((ALTERNATIVE_MODES as readonly string[]).includes(value)) {
    if (value === "resolve_tradeoff" && ideaCount < 2) {
      notices.push("Resolving a trade-off needs at least two current candidates. Showing distinct directions instead.");
      return "diverge";
    }
    return value as SelectionAlternativeMode;
  }

  // Compatibility for links created before the route matched the generator's
  // actual purpose model. These aliases deliberately resolve to a real input;
  // the old "recommended" and channel promises were not implemented filters.
  if (value === "recommended") {
    notices.push("This older variants link now opens the closest supported direction type.");
    return fallback;
  }
  if (value === "novelty" || value === "distribution") {
    notices.push("This older variants link now opens distinct directions; no candidate or score changed.");
    return "diverge";
  }

  notices.push("The requested alternative mode is not available. Showing the default instead.");
  return fallback;
}

export function resolveSelectionWorkspace(
  url: URL,
  job: Job,
  solutions: SolutionPreview[],
): SelectionWorkspaceState {
  const notices: string[] = [];
  const requestedTokens = [
    ...url.searchParams.getAll("idea"),
    ...(url.searchParams.get("ideas")?.split(",") ?? []),
  ].filter((value) => value.trim().length > 0);

  const parsedRefs: SelectionWorkspaceRef[] = [];
  let malformedCount = 0;
  for (const token of requestedTokens) {
    const parsed = parseRef(token);
    if (!parsed) {
      malformedCount += 1;
      continue;
    }
    if (!parsedRefs.some((ref) => ref.ideaId === parsed.ideaId && ref.ideaRevision === parsed.ideaRevision)) {
      parsedRefs.push(parsed);
    }
  }

  const scopedRefs = parsedRefs.slice(0, MAX_SCOPE_IDEAS);
  const matchedIdeas = scopedRefs
    .map((ref) => findExactIdea(solutions, ref))
    .filter((idea): idea is SolutionPreview => Boolean(idea));
  const staleCount = scopedRefs.length - matchedIdeas.length;
  const ignoredCount = Math.max(0, parsedRefs.length - MAX_SCOPE_IDEAS);

  let ideas = matchedIdeas;
  let scopeSource: SelectionWorkspaceScopeSource = "url";
  if (requestedTokens.length > 0 && (malformedCount > 0 || staleCount > 0 || ignoredCount > 0)) {
    notices.push("Some candidate references in this link are invalid, unavailable, or out of date.");
  }

  if (requestedTokens.length === 0) {
    const fallback = resolveFallback(job, solutions);
    ideas = fallback.ideas;
    scopeSource = fallback.usedTopCandidates ? "preview" : "draft";
    if (fallback.usedTopCandidates) {
      notices.push("No shortlist is saved yet. Showing the current leading candidates as a preview.");
    }
  }

  const refs = ideas.map(currentRef).filter((ref): ref is SelectionWorkspaceRef => Boolean(ref));
  const lens = pickEnum(url.searchParams.get("lens"), LENSES, "demand", "evidence area", notices);
  const compareView = pickEnum(url.searchParams.get("view"), COMPARE_VIEWS, "market", "comparison view", notices);
  const alternativeMode = resolveAlternativeMode(url.searchParams.get("mode"), ideas.length, notices);

  const canonicalParams = new URLSearchParams();
  // Canonicalize from MATCHED refs only. Emitting raw `scopedRefs` would keep a
  // stale/unresolvable ref in the URL and make the "out of date" notice sticky
  // for the whole session; `refs` drops the unresolvable ref cleanly.
  const canonicalRefs = refs;
  for (const ref of canonicalRefs) canonicalParams.append("idea", `${ref.ideaId}:${ref.ideaRevision}`);
  canonicalParams.set("lens", lens);
  canonicalParams.set("view", compareView);
  canonicalParams.set("mode", alternativeMode);

  return {
    ideas,
    refs,
    notices,
    lens,
    compareView,
    alternativeMode,
    scopeSource,
    canonicalQuery: `?${canonicalParams.toString()}`,
  };
}
