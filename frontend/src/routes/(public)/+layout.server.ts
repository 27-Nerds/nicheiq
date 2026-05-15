import type { LayoutServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

export const load: LayoutServerLoad = async () => {
  try {
    const res = await fetchBackend('/api/settings/cta-texts');
    const data = res.ok ? await res.json() : { ctas: {} };
    return { ctaTexts: data.ctas };
  } catch (error) {
    console.error('Failed to fetch CTA texts:', error);
    return { ctaTexts: {} };
  }
};
