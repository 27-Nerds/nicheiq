import { error } from "@sveltejs/kit";
import { fetchBackend } from "$lib/backend";
import type { Job, SolutionPreview } from "$lib/types/job";
import type { SelectionDecisionState } from "$lib/types/selectionDecisionState";
import type { SelectionMetricExplanationsResponse } from "$lib/types/selectionMetricExplanation";
import type { FounderFitLoadResponse } from "$lib/types/founderFit";
import type { LayoutServerLoad } from "./$types";
import { resolveSelectionWorkspace } from "./selectionWorkspace";

export const load: LayoutServerLoad = async ({ params, locals, url }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, "Unauthorized");

  const headers = { "X-User-ID": session.user.id };
  const jobResponse = await fetchBackend(`/api/jobs/${params.jobId}`, { headers });
  if (!jobResponse.ok) {
    if (jobResponse.status === 404) throw error(404, "Job not found");
    const payload = await jobResponse.json().catch(() => ({ error: "Failed to load research" }));
    throw error(jobResponse.status, payload.error || "Failed to load research");
  }

  const job = (await jobResponse.json()) as Job;
  let solutions: SolutionPreview[] = Array.isArray(job.solutionIdeas) ? job.solutionIdeas : [];

  const [solutionsResponse, decisionStateResponse, metricResponse, founderFitResponse] = await Promise.all([
    fetchBackend(`/api/jobs/${params.jobId}/solutions`, { headers }).catch(() => null),
    fetchBackend(`/api/jobs/${params.jobId}/selection-decision-state`, { headers }).catch(() => null),
    fetchBackend("/api/selection/metric-explanations", { headers }).catch(() => null),
    fetchBackend(`/api/jobs/${params.jobId}/founder-fit`, { headers }).catch(() => null),
  ]);
  if (solutionsResponse?.ok) {
    const payload = await solutionsResponse.json().catch(() => null);
    if (Array.isArray(payload?.solutionIdeas)) solutions = payload.solutionIdeas;
  }

  const decisionState = decisionStateResponse?.ok
    ? await decisionStateResponse.json().catch(() => null) as SelectionDecisionState | null
    : null;
  const metricExplanations = metricResponse?.ok
    ? await metricResponse.json().catch(() => null) as SelectionMetricExplanationsResponse | null
    : null;
  const founderFit = founderFitResponse?.ok
    ? await founderFitResponse.json().catch(() => null) as FounderFitLoadResponse | null
    : null;

  return {
    job,
    solutions,
    decisionState,
    metricExplanations,
    founderFit,
    workspace: resolveSelectionWorkspace(url, job, solutions),
  };
};
