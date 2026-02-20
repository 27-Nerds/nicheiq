import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { DiscoveryShareData } from '$lib/api';

export const load: PageLoad = async ({ params, fetch }) => {
  const { shareToken } = params;

  try {
    const res = await fetch(`/api/shared/discovery/${shareToken}`);

    if (!res.ok) {
      if (res.status === 404) {
        return { discovery: null, shareToken };
      }
      throw error(res.status, 'Failed to load shared discovery');
    }

    const discovery: DiscoveryShareData = await res.json();
    const allowIndexing = discovery?.allowIndexing ?? false;

    return {
      discovery,
      shareToken,
      allowIndexing,
    };
  } catch (e) {
    if (e && typeof e === 'object' && 'status' in e) {
      throw e;
    }
    console.error('Failed to load shared discovery:', e);
    return { discovery: null, shareToken };
  }
};
