import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async (event) => {
  const session = await event.locals.auth?.();

  if (!session?.user) {
    // Store intended destination for post-login redirect
    const returnTo = encodeURIComponent(event.url.pathname);
    throw redirect(302, `/login?returnTo=${returnTo}`);
  }

  return { session };
};
