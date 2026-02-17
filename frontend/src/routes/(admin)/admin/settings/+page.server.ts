import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

const TOKEN_COST_KEYS = [
  'token_cost_discovery',
  'token_cost_deep_research',
  'token_cost_landing_page',
  'token_cost_regenerate_ideas',
] as const;

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
    'X-User-Role': session.user.role || '',
  };

  try {
    const [sampleReportRes, ...tokenCostResponses] = await Promise.all([
      fetch(`${BACKEND_URL}/api/admin/settings/sample_report_url`, { headers }),
      ...TOKEN_COST_KEYS.map((key) =>
        fetch(`${BACKEND_URL}/api/admin/settings/${key}`, { headers }),
      ),
    ]);

    const sampleReportUrl = sampleReportRes.ok
      ? (await sampleReportRes.json()).value
      : null;

    const tokenCosts: Record<string, string | null> = {};
    for (let i = 0; i < TOKEN_COST_KEYS.length; i++) {
      const res = tokenCostResponses[i];
      tokenCosts[TOKEN_COST_KEYS[i]] = res.ok
        ? (await res.json()).value
        : null;
    }

    return { sampleReportUrl, tokenCosts };
  } catch (error) {
    console.error('Failed to fetch settings:', error);
  }

  return { sampleReportUrl: null, tokenCosts: {} };
};
