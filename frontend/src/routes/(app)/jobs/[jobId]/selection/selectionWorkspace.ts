import type { Job, SelectionDraftItem, SolutionPreview } from "$lib/types/job";
import { displayCompositeScore, solutionDisplayTitle } from "$lib/utils/solution-utils";

const MAX_SCOPE_IDEAS = 3;

const LENSES = ["demand", "distribution", "competition", "dependencies"] as const;
const COMPARE_VIEWS = ["market", "founder"] as const;
const ALTERNATIVE_MODES = ["diverge", "resolve_tradeoff", "reshape"] as const;

export type SelectionWorkspaceLens = (typeof LENSES)[number];
export type SelectionCompareView = (typeof COMPARE_VIEWS)[number];
export type SelectionAlternativeMode = (typeof ALTERNATIVE_MODES)[number];
export type SelectionWorkspaceScopeSource = "url" | "draft" | "preview" | "blocked";

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
  if (!idea.idea_id || idea.idea_id !== idea.idea_id.trim()) return null;
  return {
    ideaId: idea.idea_id,
    ideaRevision: idea.idea_revision ?? 1,
  };
}

function parseRef(value: string): SelectionWorkspaceRef | null {
  const token = value.trim();
  if (token !== value) return null;
  const separator = Math.max(token.lastIndexOf(":"), token.lastIndexOf("@"));
  if (separator <= 0 || separator === token.length - 1) return null;

  const ideaId = token.slice(0, separator).trim();
  if (ideaId !== token.slice(0, separator)) return null;
  const revision = Number(token.slice(separator + 1));
  if (!ideaId || ideaId.length > 200 || !Number.isSafeInteger(revision) || revision < 1) return null;

  return { ideaId, ideaRevision: revision };
}

function findExactIdea(
  solutions: SolutionPreview[],
  ref: SelectionWorkspaceRef,
): SolutionPreview | undefined {
  const matches = solutions.filter((idea) => {
    const candidateRef = currentRef(idea);
    return candidateRef?.ideaId === ref.ideaId && candidateRef.ideaRevision === ref.ideaRevision;
  });
  return matches.length === 1 ? matches[0] : undefined;
}

function hasDuplicateExactRefs(solutions: SolutionPreview[]): boolean {
  const seen = new Set<string>();
  for (const idea of solutions) {
    const ref = currentRef(idea);
    if (!ref) continue;
    const key = `${ref.ideaId}:${ref.ideaRevision}`;
    if (seen.has(key)) return true;
    seen.add(key);
  }
  return false;
}

function resolveFallback(
  job: Job,
  solutions: SolutionPreview[],
): { ideas: SolutionPreview[]; usedTopCandidates: boolean; blockedReason?: string } {
  const draftItems: SelectionDraftItem[] = job.selectionDraft?.items ?? [];
  const uniqueDraftRefs = new Set(
    draftItems.map((item) => `${item.ideaId}:${item.ideaRevision}`),
  );
  if (draftItems.length > 0 && uniqueDraftRefs.size !== draftItems.length) {
    return {
      ideas: [],
      usedTopCandidates: false,
      blockedReason: "The saved shortlist contains ambiguous candidate references. Choose the ideas again.",
    };
  }
  const drafted = draftItems
    .map((ref) => findExactIdea(solutions, ref))
    .filter((idea): idea is SolutionPreview => Boolean(idea));

  if (draftItems.length > 0) {
    return drafted.length === draftItems.length
      ? { ideas: drafted, usedTopCandidates: false }
      : {
          ideas: [],
          usedTopCandidates: false,
          blockedReason: "The saved shortlist is unavailable or out of date. Choose the ideas again.",
        };
  }
  // "Check my idea" runs: a draftless workspace visit must scope THE USER'S IDEA, never
  // pre-scope the top generated ideas (silently substituting the research subject).
  if (job.entryMode === 'validate_idea') {
    const seed = solutions.find(
      (idea) => idea.source_frame === 'user_seed' && idea.generation_operation_id === 'validate',
    );
    if (seed) return { ideas: [seed], usedTopCandidates: false };
  }
  const scored = solutions
    .map((idea) => ({ idea, score: displayCompositeScore(idea) }))
    .filter((entry): entry is { idea: SolutionPreview; score: number } => entry.score !== null)
    .sort((left, right) => (
      right.score - left.score
      || solutionDisplayTitle(left.idea).localeCompare(solutionDisplayTitle(right.idea))
    ));
  const preview = scored.length > 0
    ? scored.slice(0, 2).map((entry) => entry.idea)
    : solutions.slice(0, 2);
  return { ideas: preview, usedTopCandidates: preview.length > 0 };
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

  const strictValidationSeeds = job.entryMode === "validate_idea"
    ? solutions.filter(
        (idea) => idea.source_frame === "user_seed" && idea.generation_operation_id === "validate",
      )
    : [];
  const catalogBlockedReason = hasDuplicateExactRefs(solutions)
    ? "Candidate identities are ambiguous. Reload the current shortlist before continuing."
    : strictValidationSeeds.length > 1
      ? "More than one current candidate is marked as your submitted idea. Research cannot start until this is resolved."
      : null;

  if (catalogBlockedReason) {
    ideas = [];
    scopeSource = "blocked";
    notices.push(catalogBlockedReason);
  } else if (
    requestedTokens.length === 0
    && url.pathname.endsWith("/selection/review")
    && (job.selectionDraft?.items.length ?? 0) === 0
  ) {
    ideas = [];
    scopeSource = "blocked";
    notices.push("No saved shortlist is available. Choose at least one idea before review.");
  } else if (requestedTokens.length === 0) {
    const fallback = resolveFallback(job, solutions);
    ideas = fallback.ideas;
    scopeSource = fallback.blockedReason
      ? "blocked"
      : fallback.usedTopCandidates ? "preview" : "draft";
    if (fallback.blockedReason) {
      notices.push(fallback.blockedReason);
    } else if (fallback.usedTopCandidates) {
      notices.push("No shortlist is saved yet. Showing current candidates as a preview.");
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
