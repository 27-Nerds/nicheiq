import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Preview functionality merged into /jobs/[jobId] — redirect for bookmarked URLs
export const load: PageLoad = async ({ params }) => {
  throw redirect(301, `/jobs/${params.jobId}`);
};
