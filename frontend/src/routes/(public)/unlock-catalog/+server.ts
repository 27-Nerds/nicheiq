import type { RequestHandler } from './$types';

/**
 * Uniform "unlock the full catalog" target. The blurred catalog teaser links
 * here with a single, session-independent href so the niche/sub-niche pages stay
 * byte-identical for everyone and remain publicly cacheable. The per-request
 * redirect below is `no-store`, so the auth-dependent destination is never
 * cached.
 *
 * Destinations are placeholders until the subscription/pricing page lands
 * (follow-up): logged-in → billing, logged-out → register.
 */
export const GET: RequestHandler = async ({ locals }) => {
  const session = await locals.auth?.();
  const location = session?.user ? '/billing' : '/register?ref=catalog';
  return new Response(null, {
    status: 302,
    headers: {
      Location: location,
      'Cache-Control': 'no-store',
    },
  });
};
