/**
 * Context bridge for the selection workspace routes.
 *
 * The four workspace pages (`/selection/compare|risks|tests|alternatives`) used
 * to reach their tools by NAVIGATING BACK to the job page with a
 * `?selectionTool=` query, which re-opened the tool as an overlay over a
 * different page than the one the user launched it from. Closing it stranded
 * them on the job page instead of returning them to their workspace.
 *
 * The layout now owns the tools and hands the pages this API, so a tool opens
 * in place, over the page that asked for it, and closing returns there.
 */
import { getContext, setContext } from "svelte";
import type { SolutionPreview } from "$lib/types/job";
import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";

export interface WorkspaceChallengeFocus {
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
}

export interface WorkspaceTestSeed {
  ideaId: string;
  ideaRevision: number;
  assumptionId?: string;
}

export interface WorkspaceToolsApi {
  /** Evidence review, optionally focused on one candidate revision and lens. */
  openChallenge(focus?: WorkspaceChallengeFocus): void;
  /** Evidence review, opened on its tracked-assumptions tab. */
  openAssumptions(focus?: WorkspaceChallengeFocus): void;
  /** Test planner, optionally seeded from a tracked assumption. */
  openTestPlanner(seed?: WorkspaceTestSeed): void;
  /** Variant generator (ConceptForge) over the current scope. */
  openVariants(): void;
  /** Build-constraints form. */
  openConstraints(): void;
  /** Compare cockpit on its founder-fit tab. */
  openFit(): void;
  /** Shortlist mutation, shared with the scope strip in the workspace header. */
  toggleShortlist(idea: SolutionPreview): void;
  isShortlisted(idea: SolutionPreview): boolean;
  shortlistFull(): boolean;
  shortlistBusy(): boolean;
}

const WORKSPACE_TOOLS_KEY = Symbol("selection:workspace-tools");

export function setWorkspaceTools(api: WorkspaceToolsApi): void {
  setContext(WORKSPACE_TOOLS_KEY, api);
}

export function getWorkspaceTools(): WorkspaceToolsApi {
  const api = getContext<WorkspaceToolsApi | undefined>(WORKSPACE_TOOLS_KEY);
  if (!api) throw new Error("Selection workspace tools are only available inside the selection layout.");
  return api;
}

/** Stable identity for a candidate revision, matching the shortlist draft. */
export function workspaceIdeaKey(idea: SolutionPreview): string {
  return idea.idea_id ?? idea.solution_name;
}
