import type { PageServerLoad } from "./$types";
import { fetchBackend } from "$lib/backend";
import { normalizeJob } from "./normalize";

/**
 * Prototype loader — wires the redesigned job page to a REAL job so the design
 * is validated against real data instead of mock. Defaults to the "Peptides
 * Supplements" fixture (status AWAITING_SELECTION); override with
 * `?job=<id>&user=<ownerId>` for other jobs. Sandbox route only.
 */
const FIXTURE_JOB = "65b05ea7-1d02-491c-a9be-90a9c016d0e7";
const FIXTURE_USER = "26873251-b628-4d6e-a926-ab5c9776a0f4";

export const load: PageServerLoad = async ({ url }) => {
  const jobId = url.searchParams.get("job") || FIXTURE_JOB;
  const userId = url.searchParams.get("user") || FIXTURE_USER;
  const headers = { "X-User-ID": userId };

  try {
    const [solRes, pvRes] = await Promise.all([
      fetchBackend(`/api/jobs/${jobId}/solutions`, { headers }),
      fetchBackend(`/api/jobs/${jobId}/preview-report`, { headers }),
    ]);

    if (!solRes.ok) {
      return { ready: false, reason: `solutions ${solRes.status}`, jobId, data: null };
    }

    const solutions = await solRes.json();
    const preview = pvRes.ok ? await pvRes.json() : null;
    const vm = normalizeJob(solutions, preview);

    if (!vm.ideas.length) {
      return { ready: false, reason: "no ideas in this job yet", jobId, data: null };
    }

    return { ready: true, reason: null, jobId, data: vm };
  } catch (e) {
    return {
      ready: false,
      reason: e instanceof Error ? e.message : "backend unavailable",
      jobId,
      data: null,
    };
  }
};
