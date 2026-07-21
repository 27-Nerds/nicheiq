import type { PageServerLoad } from './$types';
import type { PublicExperimentTest } from '$lib/types/selectionExperiment';

export const load: PageServerLoad = async ({ params, fetch, setHeaders }) => {
  setHeaders({
    'Cache-Control': 'private, no-store',
    'Referrer-Policy': 'no-referrer',
    'X-Robots-Tag': 'noindex, nofollow',
  });

  const response = await fetch(`/api/public/experiments/${params.publicToken}`);
  if (!response.ok) {
    return { test: null, publicToken: params.publicToken };
  }

  const body = await response.json() as { test: PublicExperimentTest };
  return { test: body.test, publicToken: params.publicToken };
};
