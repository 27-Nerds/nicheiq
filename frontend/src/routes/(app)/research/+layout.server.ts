import { redirect } from '@sveltejs/kit';
import { dev } from '$app/environment';
import type { LayoutServerLoad } from './$types';

// EXPERIMENTAL surface (continuous-analyst-ledger plan): the chat-first guided
// research flow. Admin-only while it bakes — same guard as the (admin) group.
//
// DEV-ONLY BYPASS: `?preview=1` lets a signed-in non-admin (or an automated browser)
// open the page for design review. Double-gated — it needs BOTH the dev build AND the
// explicit flag — so a stray query string can never open it in production, where
// `dev` is false and the admin check is the only path.
export const load: LayoutServerLoad = async (event) => {
  const session = await event.locals.auth?.();

  if (!session?.user) {
    throw redirect(302, '/login');
  }

  const devPreview = dev && event.url.searchParams.get('preview') === '1';

  if (session.user.role !== 'ADMIN' && !devPreview) {
    throw redirect(302, '/dashboard');
  }

  return { session };
};
