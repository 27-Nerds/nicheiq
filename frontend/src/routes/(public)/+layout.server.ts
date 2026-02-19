import type { LayoutServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: LayoutServerLoad = async () => {
  try {
    const res = await fetch(`${BACKEND_URL}/api/settings/cta-texts`, {
      headers: { 'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '' },
    });
    const data = res.ok ? await res.json() : { ctas: {} };
    return { ctaTexts: data.ctas };
  } catch (error) {
    console.error('Failed to fetch CTA texts:', error);
    return { ctaTexts: {} };
  }
};
