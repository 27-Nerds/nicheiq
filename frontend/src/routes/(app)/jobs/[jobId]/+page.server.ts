import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import { error } from '@sveltejs/kit';
import type { ReportSummary, SolutionPreview } from '$lib/types/job';
import type { DiscoveryData } from '$lib/types/discovery';
import type { PreviewReport } from '$lib/types/previewReport';
import type { CatalogTopPainPoint } from '$lib/types/publicCatalog';

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

  const job = await jobRes.json();

  // Phase 2: Conditional parallel fetches based on job status
  let reportSummary: ReportSummary | null = null;
  let solutions: SolutionPreview[] | null = null;
  let solutionVotes: Record<string, number> = {};
  let discoveryData: DiscoveryData | null = null;
  let previewReport: PreviewReport | null = null;
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
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { discoveryData = d; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/preview-report`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { previewReport = d; })
        .catch(() => {})
    );
  }

  if (['AWAITING_SELECTION', 'REGENERATING'].includes(job.status)) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/solutions`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { solutions = d?.solutionIdeas ?? null; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-share`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (d?.isShared && d.solutionVotes) {
            solutionVotes = d.solutionVotes;
          }
        })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { discoveryData = d; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/preview-report`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { previewReport = d; })
        .catch(() => {})
    );
  }

  if (['FAILED', 'RUNNING_PHASE2'].includes(job.status)) {
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { discoveryData = d; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetchBackend(`/api/jobs/${params.jobId}/preview-report`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { previewReport = d; })
        .catch(() => {})
    );
  }

  await Promise.all(conditionalFetches);

  return {
    job,
    reportSummary,
    solutions,
    solutionVotes,
    discoveryData,
    previewReport,
    userEmail: session.user.email ?? null,
    catalogPainPoints,
  };
};
