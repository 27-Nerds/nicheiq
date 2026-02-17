import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const load: LayoutServerLoad = async (event) => {
  const session = await event.locals.auth?.();

  if (!session?.user) {
    // Store intended destination for post-login redirect
    const returnTo = encodeURIComponent(event.url.pathname);
    throw redirect(302, `/login?returnTo=${returnTo}`);
  }

  // Fetch user's credit balance and stage costs for header display
  let creditBalance = 0;
  let stageCosts = { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2 };

  const headers = {
    'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
    'X-User-ID': session.user.id,
  };

  try {
    const [balanceRes, costsRes] = await Promise.all([
      fetch(`${BACKEND_URL}/api/billing/balance`, { headers }),
      fetch(`${BACKEND_URL}/api/billing/stage-costs`, { headers }),
    ]);

    if (balanceRes.ok) {
      const data = await balanceRes.json();
      creditBalance = data.balance ?? 0;
    }
    if (costsRes.ok) {
      const data = await costsRes.json();
      stageCosts = { ...stageCosts, ...data };
    }
  } catch (error) {
    console.error('Failed to fetch credit data:', error);
  }

  return { session, creditBalance, stageCosts };
};
