import type { DiscoveryVoteRationale } from "$lib/api";
import type { SolutionPreview } from "$lib/types/job";
import { solutionDisplayTitle } from "$lib/utils/solution-utils";

export interface CollaboratorFeedbackGroup {
  key: string;
  linked: boolean;
  solutionName: string;
  comments: string[];
}

function ideaKey(solution: SolutionPreview): string {
  return solution.idea_id
    ? `${solution.idea_id}:${solution.idea_revision ?? 1}`
    : `legacy:${solution.solution_name}`;
}

/** Preserve identity-first matching so duplicate legacy names never attach a
 * collaborator comment to an arbitrary current candidate. */
export function buildCollaboratorFeedbackGroups(
  solutions: SolutionPreview[],
  rationales: DiscoveryVoteRationale[],
): CollaboratorFeedbackGroup[] {
  const nameCounts = new Map<string, number>();
  for (const solution of solutions) {
    nameCounts.set(solution.solution_name, (nameCounts.get(solution.solution_name) ?? 0) + 1);
  }

  const groups = new Map<string, CollaboratorFeedbackGroup>();
  for (const rationale of rationales) {
    const solution = rationale.solutionId
      ? solutions.find((candidate) => candidate.idea_id === rationale.solutionId) ?? null
      : nameCounts.get(rationale.solutionName) === 1
        ? solutions.find((candidate) => candidate.solution_name === rationale.solutionName) ?? null
        : null;
    const key = solution
      ? ideaKey(solution)
      : rationale.solutionId
        ? `previous:${rationale.solutionId}`
        : `legacy:${rationale.solutionName}`;
    const existing = groups.get(key);
    if (existing) {
      existing.comments.push(rationale.comment);
    } else {
      groups.set(key, {
        key,
        linked: solution !== null,
        solutionName: solution ? solutionDisplayTitle(solution) : rationale.solutionName,
        comments: [rationale.comment],
      });
    }
  }

  return [...groups.values()].sort((left, right) => {
    if (left.linked && !right.linked) return -1;
    if (!left.linked && right.linked) return 1;
    return left.solutionName.localeCompare(right.solutionName);
  });
}
