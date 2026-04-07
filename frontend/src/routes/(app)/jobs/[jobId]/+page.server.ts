import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { ReportSummary, SolutionPreview } from '$lib/types/job';
import type { DiscoveryData } from '$lib/types/discovery';
import type { PreviewReport } from '$lib/types/previewReport';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: PageServerLoad = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  // Phase 1: Fetch job (required to know status for conditional fetches)
  const jobRes = await fetch(`${BACKEND_URL}/api/jobs/${params.jobId}`, { headers });

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

  const conditionalFetches: Promise<void>[] = [];

  if (job.status === 'COMPLETED') {
    const hasReport = (job.assets ?? []).some((a: { type: string }) => a.type === 'REPORT_JSON');
    if (hasReport) {
      conditionalFetches.push(
        fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/report-summary`, { headers })
          .then(r => r.ok ? r.json() : null)
          .then(d => { reportSummary = d; })
          .catch(() => {})
      );
    }
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { discoveryData = d; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/preview-report`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { previewReport = d; })
        .catch(() => {})
    );
  }

  if (['AWAITING_SELECTION', 'REGENERATING'].includes(job.status)) {
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/solutions`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { solutions = d?.solutionIdeas ?? null; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/discovery-share`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (d?.isShared && d.solutionVotes) {
            solutionVotes = d.solutionVotes;
          }
        })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { discoveryData = d; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/preview-report`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { previewReport = d; })
        .catch(() => {})
    );
  }

  if (['FAILED', 'RUNNING_PHASE2'].includes(job.status)) {
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/discovery-data`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { discoveryData = d; })
        .catch(() => {})
    );
    conditionalFetches.push(
      fetch(`${BACKEND_URL}/api/jobs/${params.jobId}/preview-report`, { headers })
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
  };
};
