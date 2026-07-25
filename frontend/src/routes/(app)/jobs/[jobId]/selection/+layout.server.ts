import { error, redirect } from "@sveltejs/kit";
import { fetchBackend } from "$lib/backend";
import type { Job, SolutionPreview } from "$lib/types/job";
import type { SelectionDecisionState } from "$lib/types/selectionDecisionState";
import type { SelectionMetricExplanationsResponse } from "$lib/types/selectionMetricExplanation";
import type { FounderFitLoadResponse } from "$lib/types/founderFit";
import type { DiscoveryData } from "$lib/types/discovery";
import type { PreviewReport } from "$lib/types/previewReport";
import type { SelectionConceptSet } from "$lib/types/selectionConceptSet";
import { createDiscoveryDisplayModel } from "$lib/discovery/discoveryDisplay";
import { normalizeSolutionPreviews } from "$lib/utils/displayGuards";
import type { LayoutServerLoad } from "./$types";
import { resolveSelectionWorkspace } from "./selectionWorkspace";

type OptionalArtifact<T> = {
  known: boolean;
  value: T | null;
};

async function loadOptionalArtifact<T>(request: Promise<Response>): Promise<OptionalArtifact<T>> {
  try {
    const response = await request;
    if (response.status === 204 || response.status === 404) {
      return { known: true, value: null };
    }
    if (!response.ok) {
      return { known: false, value: null };
    }
    try {
      return { known: true, value: await response.json() as T };
    } catch {
      return { known: false, value: null };
    }
  } catch {
    return { known: false, value: null };
  }
}

export const load: LayoutServerLoad = async ({ params, locals, url, parent }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, "Unauthorized");

  // Grant comes from the (app) layout load, which fetches it fresh per navigation.
  const { featureAccess } = await parent();
  const decisionTools = featureAccess?.decisionTools === true;
  // /selection/risks IS the evidence-check tool. Without the grant it has nothing to
  // render and every fetch on it 403s, so send the owner to the compare view instead
  // of a half-empty page. Deep links and stale bookmarks both land here.
  if (!decisionTools && url.pathname.endsWith("/selection/risks")) {
    redirect(307, `/jobs/${params.jobId}/selection/compare${url.search}`);
  }

  const headers = { "X-User-ID": session.user.id };
  const jobResponse = await fetchBackend(`/api/jobs/${params.jobId}`, { headers });
  if (!jobResponse.ok) {
    if (jobResponse.status === 404) throw error(404, "Job not found");
    const payload = await jobResponse.json().catch(() => ({ error: "Failed to load research" }));
    throw error(jobResponse.status, payload.error || "Failed to load research");
  }

  const job = (await jobResponse.json()) as Job;
  let normalizedSolutions = normalizeSolutionPreviews(job.solutionIdeas);
  let solutions: SolutionPreview[] = normalizedSolutions.solutions;
  // Both are decision-tool endpoints and 403 without the grant — don't spend the
  // round trip, and don't log a failure that isn't one.
  const shouldPrefetchConceptSets = decisionTools && url.pathname.endsWith("/selection/compare");
  const shouldFetchFounderFit = decisionTools;

  // stageCosts + creditBalance are inherited from the (app) layout load — no need
  // to re-fetch them on every selection navigation.
  const [
    solutionsResponse,
    decisionStateResponse,
    metricResponse,
    founderFitResponse,
    discoveryDataArtifact,
    previewReportArtifact,
    conceptSetsArtifact,
  ] = await Promise.all([
    fetchBackend(`/api/jobs/${params.jobId}/solutions`, { headers }).catch(() => null),
    fetchBackend(`/api/jobs/${params.jobId}/selection-decision-state`, { headers }).catch(() => null),
    fetchBackend("/api/selection/metric-explanations", { headers }).catch(() => null),
    shouldFetchFounderFit
      ? fetchBackend(`/api/jobs/${params.jobId}/founder-fit`, { headers }).catch(() => null)
      : Promise.resolve(null),
    loadOptionalArtifact<DiscoveryData>(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-data`, { headers }),
    ),
    loadOptionalArtifact<PreviewReport>(
      fetchBackend(`/api/jobs/${params.jobId}/preview-report`, { headers }),
    ),
    shouldPrefetchConceptSets
      ? loadOptionalArtifact<{ sets: SelectionConceptSet[] }>(
          fetchBackend(`/api/jobs/${params.jobId}/selection-concept-sets`, { headers }),
        )
      : Promise.resolve({ known: false, value: null }),
  ]);
  if (solutionsResponse?.ok) {
    const payload = await solutionsResponse.json().catch(() => null);
    if (payload && typeof payload === "object" && "solutionIdeas" in payload) {
      normalizedSolutions = normalizeSolutionPreviews(payload.solutionIdeas);
      solutions = normalizedSolutions.solutions;
    }
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
  const conceptSets = Array.isArray(conceptSetsArtifact.value?.sets)
    ? conceptSetsArtifact.value.sets
    : null;
  const discoverySectionsKnown = discoveryDataArtifact.known && previewReportArtifact.known;
  const availableSectionIds = discoverySectionsKnown
    ? createDiscoveryDisplayModel(
        previewReportArtifact.value,
        discoveryDataArtifact.value,
      ).availableSectionIds
    : undefined;

  return {
    job,
    solutions,
    decisionState,
    metricExplanations,
    founderFit,
    conceptSets,
    availableSectionIds,
    decisionTools,
    selectionLoadState: {
      decisionStateUnavailable: !decisionStateResponse?.ok || decisionState === null,
      metricExplanationsUnavailable: !metricResponse?.ok || metricExplanations === null,
      // Not fetched without the grant — "unavailable" would render a failure banner
      // for a feature the owner simply doesn't have.
      founderFitUnavailable: decisionTools && (!founderFitResponse?.ok || founderFit === null),
      invalidSolutionCount: normalizedSolutions.invalidCount,
    },
    workspace: resolveSelectionWorkspace(url, job, solutions),
  };
};
