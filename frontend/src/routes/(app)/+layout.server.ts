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

  // Fetch user's credit balance for header display
  let creditBalance = 0;
  try {
    const response = await fetch(`${BACKEND_URL}/api/billing/balance`, {
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET,
        'X-User-ID': session.user.id,
      },
    });

    if (response.ok) {
      const data = await response.json();
      creditBalance = data.balance ?? 0;
    }
  } catch (error) {
    console.error('Failed to fetch credit balance:', error);
  }

  return { session, creditBalance };
};
