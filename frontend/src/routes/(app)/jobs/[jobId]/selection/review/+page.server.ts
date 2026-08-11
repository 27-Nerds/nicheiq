import { error } from "@sveltejs/kit";
import { fetchBackend } from "$lib/backend";
import type { DiscoveryVoteRationale } from "$lib/api";
import type { PageServerLoad } from "./$types";

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function voteCounts(value: unknown): Record<string, number> {
  const record = objectRecord(value);
  if (!record) return {};

  const counts: Record<string, number> = {};
  for (const [key, count] of Object.entries(record)) {
    if (typeof count === "number" && Number.isInteger(count) && count >= 0) {
      counts[key] = count;
    }
  }
  return counts;
}

function voteRationales(value: unknown): DiscoveryVoteRationale[] {
  if (!Array.isArray(value)) return [];

  return value.flatMap((candidate) => {
    const record = objectRecord(candidate);
    const solutionName = typeof record?.solutionName === "string"
      ? record.solutionName.trim()
      : "";
    const comment = typeof record?.comment === "string" ? record.comment.trim() : "";
    const solutionId = typeof record?.solutionId === "string" ? record.solutionId.trim() : "";
    if (!solutionName || !comment) return [];

    return [{
      ...(solutionId ? { solutionId } : {}),
      solutionName,
      comment,
    }];
  });
}

export const load: PageServerLoad = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, "Unauthorized");

  let collaboratorSignalsStatus: "loaded" | "absent" | "unavailable" = "unavailable";
  let solutionVotes: Record<string, number> = {};
  let solutionVotesById: Record<string, number> = {};
  let rationales: DiscoveryVoteRationale[] = [];
  try {
    const response = await fetchBackend(`/api/jobs/${params.jobId}/discovery-share`, {
      headers: { "X-User-ID": session.user.id },
    });
    if (response.status === 204 || response.status === 404) {
      collaboratorSignalsStatus = "absent";
    } else if (response.ok) {
      const payload = await response.json();
      const record = objectRecord(payload);
      if (record) {
        solutionVotes = voteCounts(record.solutionVotes);
        solutionVotesById = voteCounts(record.solutionVotesById);
        rationales = voteRationales(record.voteRationales);
        collaboratorSignalsStatus = "loaded";
      }
    }
  } catch {
    // Keep unavailable distinct from an owner who never collected collaborator input.
  }

  return {
    collaboratorSignalsStatus,
    solutionVotes,
    solutionVotesById,
    voteRationales: rationales,
  };
};
