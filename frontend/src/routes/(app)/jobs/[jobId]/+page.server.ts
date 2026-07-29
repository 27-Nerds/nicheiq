import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { error } from '@sveltejs/kit';
import type { ReportSummary, SolutionPreview } from '$lib/types/job';
import type { DiscoveryData } from '$lib/types/discovery';
import type { PreviewReport } from '$lib/types/previewReport';
import type { CatalogTopPainPoint } from '$lib/types/publicCatalog';
import type { SelectionMetricExplanationsResponse } from '$lib/types/selectionMetricExplanation';
import type { DiscoveryVoteRationale } from '$lib/api';
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
  const normalizedJobSolutions = normalizeSolutionPreviews(rawJob.solutionIdeas);
  const job = {
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
  let invalidSolutionCount = normalizedJobSolutions.invalidCount;
  let solutionsFetchFailed = false;
  let discoveryDataFetchFailed = false;
  let previewReportFetchFailed = false;
  let metricExplanations: SelectionMetricExplanationsResponse | null = null;
  // Free-preview pain points for the "explore while you wait" list, shown only
  // while Phase 1 (discovery) is generating. Public endpoint; empty array hides
  // the list. Mirrors the parsing in (public)/+page.server.ts.
  let catalogPainPoints: CatalogTopPainPoint[] = [];

  const conditionalFetches: Promise<void>[] = [];

  if (['QUEUED', 'PENDING', 'RUNNING', 'RUNNING_PHASE2'].includes(job.status)) {
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
  if (['AWAITING_SELECTION', 'REGENERATING', 'RUNNING_PHASE2'].includes(job.status)) {
    conditionalFetches.push(
      fetchBackend('/api/selection/metric-explanations', { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { metricExplanations = d; })
        .catch(() => {})
    );
  }

  if (['AWAITING_SELECTION', 'REGENERATING'].includes(job.status)) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/solutions`, { headers })
        .then(async (response) => {
          if (!response.ok) {
            if (job.solutionIdeas.length === 0) solutionsFetchFailed = true;
            return null;
          }
          return response.json();
        })
        .then(d => {
          if (!d || !('solutionIdeas' in d)) {
            if (job.solutionIdeas.length === 0) solutionsFetchFailed = true;
            return;
          }
          const normalized = normalizeSolutionPreviews(d.solutionIdeas);
          solutions = normalized.solutions;
          invalidSolutionCount = normalized.invalidCount;
        })
        .catch(() => {
          if (job.solutionIdeas.length === 0) solutionsFetchFailed = true;
        })
    );
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-share`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d?.isShared) return;
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
  if ([
    'AWAITING_SELECTION',
    'REGENERATING',
    'AWAITING_GATE',
    'FAILED',
    'RUNNING_PHASE2',
  ].includes(job.status)) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(async (response) => {
          if (response.ok) discoveryData = await response.json();
          else if (![204, 404].includes(response.status)) discoveryDataFetchFailed = true;
        })
        .catch(() => { discoveryDataFetchFailed = true; })
    );
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
    userEmail: session.user.email ?? null,
    catalogPainPoints,
    // Cast: TS control-flow ignores the closure assignment above and narrows to null.
    metricExplanations: metricExplanations as SelectionMetricExplanationsResponse | null,
  };
};
