/**
 * Context bridge for the selection workspace routes.
 *
 * Selection tools used to navigate back to the job page with a
 * `?selectionTool=` query, which re-opened the tool as an overlay over a
 * different page than the one the user launched it from. Closing it stranded
 * them on the job page instead of returning them to their workspace.
 *
 * The layout hands routed pages a small action API. Comparison and evidence
 * stay as durable pages; bounded review/edit forms open over the page that
 * asked for them. Legacy secondary-tool routes remain compatibility links.
 */
import { getContext, setContext } from "svelte";
import type { SolutionPreview } from "$lib/types/job";
import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";
import type { SelectionConceptPurpose } from "$lib/types/selectionConceptSet";
import type { SelectionExperimentDraftSeed } from "$lib/types/selectionExperiment";

export interface WorkspaceChallengeFocus {
  ideaId: string;
  ideaRevision: number;
  lens: SelectionChallengeLens;
}

export interface WorkspaceTestSeed {
  ideaId: string;
  ideaRevision: number;
  assumptionId?: string;
  /** Preserves an unsaved generated brief across the route transition. */
  draft?: SelectionExperimentDraftSeed;
}

export interface WorkspaceToolsApi {
  /** Evidence review, optionally focused on one candidate revision and lens. */
  openChallenge(focus?: WorkspaceChallengeFocus): void;
  /** Evidence review with the decision-changing questions disclosure open. */
  openAssumptions(focus?: WorkspaceChallengeFocus): void;
  /** Test planner, optionally seeded from a tracked assumption. */
  openTestPlanner(seed?: WorkspaceTestSeed): void;
  /** Variant generator (ConceptForge) over the current exact scope. */
  openVariants(purpose?: SelectionConceptPurpose): void;
  /** Build-constraints form. */
  openConstraints(): void;
  /** Durable founder-fit comparison route. */
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
  return `${idea.idea_id ?? idea.solution_name}@${idea.idea_revision ?? 1}`;
}
