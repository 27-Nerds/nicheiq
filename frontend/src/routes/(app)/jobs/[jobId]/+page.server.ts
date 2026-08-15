import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { error } from '@sveltejs/kit';
import type { ReportSummary, SolutionPreview } from '$lib/types/job';
import type { DiscoveryData } from '$lib/types/discovery';
import type { PreviewReport } from '$lib/types/previewReport';
import type { CatalogTopPainPoint } from '$lib/types/publicCatalog';
import type { SelectionMetricExplanationsResponse } from '$lib/types/selectionMetricExplanation';
import type { DiscoveryVoteRationale } from '$lib/api';
import type { DiscoveryAnnotationResponse } from '$lib/types/discoveryAnnotations';
import { normalizeSolutionPreviews } from '$lib/utils/displayGuards';

export const load: PageServerLoad = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const headers = { 'X-User-ID': session.user.id };

  // Phase 1: Fetch job (required to know status for conditional fetches)
  const jobRes = await fetchBackend(`/api/jobs/${params.jobId}`, { headers });

  if (!jobRes.ok) {
    if (jobRes.status === 404) throw error(404, 'Job not found');
    const data = await jobRes.json().catch(() => ({ error: 'Unknown error' }));
    throw error(jobRes.status, data.error || 'Failed to load job');
  }

  const rawJob = await jobRes.json();
  // Paid pool mutations temporarily leave AWAITING_SELECTION even though the user
  // still owns the same selection workspace. Key off the exact dispatch kind and
  // its valid lifecycle states so initial Discovery and Deep Research queues keep
  // their lightweight progress-page data contracts.
  const selectionMutationActive =
    (
      rawJob.activeDispatchKind === 'SEED_IDEA'
      && ['QUEUED', 'RUNNING'].includes(rawJob.status)
    )
    || (
      rawJob.activeDispatchKind === 'REGENERATE'
      && ['QUEUED', 'REGENERATING'].includes(rawJob.status)
    );
  const selectionUiActive =
    ['AWAITING_SELECTION', 'REGENERATING'].includes(rawJob.status)
    || selectionMutationActive;
  // Phase 2 authorized and waiting for a worker — the progress screen's other half.
  const deepResearchQueued =
    rawJob.activeDispatchKind === 'DEEP_RESEARCH' && rawJob.status === 'QUEUED';

  // Do not normalize or use a generic job payload's pool in selection states. The backend
  // omits it there, and the only candidate/artifact snapshot this loader consumes is
  // the version/fingerprint-checked /solutions response below.
  const normalizedJobSolutions = selectionUiActive
    ? { solutions: [], invalidCount: 0 }
    : normalizeSolutionPreviews(rawJob.solutionIdeas);
  let job = {
    ...rawJob,
    solutionIdeas: normalizedJobSolutions.solutions,
  };

  // Phase 2: Conditional parallel fetches based on job status
  let reportSummary: ReportSummary | null = null;
  let solutions: SolutionPreview[] | null = null;
  let solutionVotes: Record<string, number> = {};
  let solutionVotesById: Record<string, number> = {};
  let voteRationales: DiscoveryVoteRationale[] = [];
  let discoveryData: DiscoveryData | null = null;
  let previewReport: PreviewReport | null = null;
  let invalidSolutionCount = selectionUiActive ? 0 : normalizedJobSolutions.invalidCount;
  let solutionsFetchFailed = false;
  let discoveryDataFetchFailed = false;
  let previewReportFetchFailed = false;
  let metricExplanations: SelectionMetricExplanationsResponse | null = null;
  let annotationDocument: DiscoveryAnnotationResponse | null = null;
  let selectionArtifactVerification: 'verified' | 'untrusted' | null = null;
  let selectionArtifactReason: string | null = null;
  // Free-preview pain points for the "explore while you wait" list, shown only
  // while Phase 1 (discovery) is generating. Public endpoint; empty array hides
  // the list. Mirrors the parsing in (public)/+page.server.ts.
  let catalogPainPoints: CatalogTopPainPoint[] = [];

  const conditionalFetches: Promise<void>[] = [];

  // Annotations are part of the durable research record, not just an editing
  // tool. Hydrate them on the server for every lifecycle state so running and
  // completed pages can render saved marks without a background client request.
  conditionalFetches.push(
    fetchBackend(`/api/jobs/${params.jobId}/discovery-annotations`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { annotationDocument = d; })
      .catch(() => {})
  );

  if (
    ['QUEUED', 'PENDING', 'RUNNING'].includes(job.status)
    && job.activeDispatchKind !== 'DEEP_RESEARCH'
    && !selectionMutationActive
  ) {
    conditionalFetches.push(
      fetchBackend('/api/public/catalog/top-pain-points?limit=8&freePreview=true', {
        signal: AbortSignal.timeout(3000),
      })
        .then(r => r.ok ? r.json() : null)
        .then(d => { catalogPainPoints = Array.isArray(d) ? d : (d?.painPoints ?? []); })
        .catch(() => {})
    );
  }

  if (job.status === 'COMPLETED') {
    const hasReport = (job.assets ?? []).some((a: { type: string }) => a.type === 'REPORT_JSON');
    if (hasReport) {
      conditionalFetches.push(
        fetchBackend(`/api/jobs/${params.jobId}/report-summary`, { headers })
          .then(r => r.ok ? r.json() : null)
          .then(d => { reportSummary = d; })
          .catch(() => {})
      );
    }
  }

  // Statuses where SelectionWorkbench (and its score-hint overlays) can render — the
  // served capThresholds keep the "capped at X" copy aligned with the deployed env.
  if (
    ['AWAITING_SELECTION', 'REGENERATING', 'RUNNING_PHASE2'].includes(job.status)
    || selectionMutationActive
  ) {
    conditionalFetches.push(
      fetchBackend('/api/selection/metric-explanations', { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { metricExplanations = d; })
        .catch(() => {})
    );
  }

  if (['AWAITING_SELECTION', 'REGENERATING'].includes(job.status) || selectionMutationActive) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/solutions`, { headers })
        .then(async (response) => {
          if (!response.ok) {
            solutionsFetchFailed = true;
            return null;
          }
          return response.json();
        })
        .then(d => {
          if (!d || !('solutionIdeas' in d)) {
            solutionsFetchFailed = true;
            return;
          }
          const normalized = normalizeSolutionPreviews(d.solutionIdeas);
          solutions = normalized.solutions;
          invalidSolutionCount = normalized.invalidCount;
          selectionArtifactVerification = d.artifactVerification === 'verified'
            ? 'verified'
            : 'untrusted';
          selectionArtifactReason = typeof d.artifactReason === 'string'
            ? d.artifactReason
            : null;
          previewReport = d.artifactVerification === 'verified' && d.previewReport
            ? d.previewReport as PreviewReport
            : null;
          job = {
            ...job,
            solutionIdeas: normalized.solutions,
            selectedSolution: d.selectedSolution,
            selectedSolutions: d.selectedSolutions,
            selectedSolutionIds: d.selectedSolutionIds,
            selectedSolutionRefs: d.selectedSolutionRefs,
            selectionRationale: d.selectionRationale,
            selectionDecisionProfile: d.selectionDecisionProfile,
            selectionDraft: d.selectionDraft,
            canRegenerate: d.canRegenerate,
            ideaBatchCompletedCount: d.ideaBatchCompletedCount,
            maxIdeaBatches: d.maxIdeaBatches,
            activeOperation: d.activeOperation,
          };
        })
        .catch(() => { solutionsFetchFailed = true; })
    );
  }

  // A closed share is still the owner's historical decision input. Load it for
  // every job that has reached a candidate pool so queued/running Deep Research
  // and completed runs do not silently lose collaborator feedback.
  if (
    selectionUiActive
    || normalizedJobSolutions.solutions.length > 0
    || (job.selectedSolutions?.length ?? 0) > 0
    || (job.selectedSolutionIds?.length ?? 0) > 0
  ) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-share`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d) return;
          solutionVotes = d.solutionVotes ?? {};
          solutionVotesById = d.solutionVotesById ?? {};
          voteRationales = d.voteRationales ?? [];
        })
        .catch(() => {})
    );
  }

  // Every status that displays Discovery context requests each artifact once.
  // Completed runs use the report as their canonical detail surface, so the
  // compact run overview does not re-fetch or duplicate the Discovery dossier.
  // A 404/204 is a legitimate legacy absence; transport/5xx failures are surfaced
  // separately so the page can offer Retry instead of pretending the dossier is empty.
  // AWAITING_GATE is intentionally absent: the backend's gate-status guard rejects
  // these artifact endpoints with a 400 mid-gate, so fetching would only trip the
  // failure flags and offer a Retry that can never succeed.
  if (
    [
      'AWAITING_SELECTION',
      'REGENERATING',
      'FAILED',
      'CANCELLED',
      'RUNNING_PHASE2',
    ].includes(job.status)
    || selectionMutationActive
  ) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(async (response) => {
          if (response.ok) discoveryData = await response.json();
          else if (![204, 404].includes(response.status)) discoveryDataFetchFailed = true;
        })
        .catch(() => { discoveryDataFetchFailed = true; })
    );
    if (!selectionUiActive) {
      conditionalFetches.push(
        fetchBackend(`/api/jobs/${params.jobId}/preview-report`, { headers })
          .then(async (response) => {
            if (response.ok) previewReport = await response.json();
            else if (![204, 404].includes(response.status)) previewReportFetchFailed = true;
          })
          .catch(() => { previewReportFetchFailed = true; })
      );
    }
  }

  // QUEUED with Deep Research authorized: the same focused progress screen as
  // RUNNING_PHASE2, for the whole queue wait. It renders the idea check's OUTCOME, and
  // without the artifact it falls back to the graded wording on runs the pipeline refused
  // to grade — which is exactly where /selection/review sends a refused run. The backend
  // half of this landed in the same change (`isQueuedDeepResearch`, routes/jobs.ts); either
  // one alone is inert.
  //
  // preview-report ONLY. `discovery-data` still 400s for QUEUED, so fetching it here would
  // set `discoveryDataFetchFailed` and offer a Retry that can never succeed — the same
  // reason AWAITING_GATE is absent above.
  if (deepResearchQueued) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/preview-report`, { headers })
        .then(async (response) => {
          if (response.ok) previewReport = await response.json();
          else if (![204, 404].includes(response.status)) previewReportFetchFailed = true;
        })
        .catch(() => { previewReportFetchFailed = true; })
    );
  }

  await Promise.all(conditionalFetches);

  return {
    job,
    reportSummary,
    solutions,
    solutionVotes,
    discoveryData,
    solutionVotesById,
    voteRationales,
    previewReport,
    discoveryDataFetchFailed,
    previewReportFetchFailed,
    solutionsFetchFailed,
    invalidSolutionCount,
    selectionArtifactVerification,
    selectionArtifactReason,
    userEmail: session.user.email ?? null,
    catalogPainPoints,
    // Cast: TS control-flow ignores the closure assignment above and narrows to null.
    metricExplanations: metricExplanations as SelectionMetricExplanationsResponse | null,
    annotationDocument: annotationDocument as DiscoveryAnnotationResponse | null,
  };
};
