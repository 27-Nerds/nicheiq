import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


const TOKEN_COST_KEYS = [
  'token_cost_discovery',
  'token_cost_deep_research',
  'token_cost_landing_page',
  'token_cost_regenerate_ideas',
  'token_cost_seed_idea',
  'token_cost_guided_s1',
  'token_cost_guided_s2_4',
  'token_cost_guided_s5',
] as const;

const CTA_KEYS = [
  'cta_header',
  'cta_hero_primary',
  'cta_hero_secondary',
  'cta_pricing_button',
  'cta_final_primary',
  'cta_final_secondary',
  'cta_sample_button',
  'cta_view_sample_link',
] as const;

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const headers = {
    'X-User-ID': session.user.id,
    'X-User-Role': session.user.role || '',
  };

  try {
    const [sampleReportRes, registrationCreditsRes, ...responses] = await Promise.all([
      fetchBackend(`/api/admin/settings/sample_report_url`, { headers }),
      fetchBackend(`/api/admin/settings/registration_credits`, { headers }),
      ...TOKEN_COST_KEYS.map((key) =>
        fetchBackend(`/api/admin/settings/${key}`, { headers }),
      ),
      ...CTA_KEYS.map((key) =>
        fetchBackend(`/api/admin/settings/${key}`, { headers }),
      ),
    ]);

    const sampleReportUrl = sampleReportRes.ok
      ? (await sampleReportRes.json()).value
      : null;

    const registrationCredits = registrationCreditsRes.ok
      ? (await registrationCreditsRes.json()).value
      : null;

    const tokenCostResponses = responses.slice(0, TOKEN_COST_KEYS.length);
    const ctaResponses = responses.slice(TOKEN_COST_KEYS.length);

    const tokenCosts: Record<string, string | null> = {};
    for (let i = 0; i < TOKEN_COST_KEYS.length; i++) {
      const res = tokenCostResponses[i];
      tokenCosts[TOKEN_COST_KEYS[i]] = res.ok
        ? (await res.json()).value
        : null;
    }

    const ctaTexts: Record<string, string | null> = {};
    for (let i = 0; i < CTA_KEYS.length; i++) {
      const res = ctaResponses[i];
      ctaTexts[CTA_KEYS[i]] = res.ok
        ? (await res.json()).value
        : null;
    }

    return { sampleReportUrl, registrationCredits, tokenCosts, ctaTexts };
  } catch (error) {
    console.error('Failed to fetch settings:', error);
  }

  return { sampleReportUrl: null, registrationCredits: null, tokenCosts: {}, ctaTexts: {} };
};
