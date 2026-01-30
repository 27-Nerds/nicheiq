import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async (event) => {
  const session = await event.locals.auth?.();

  if (!session?.user) {
    throw redirect(302, '/login');
  }

  if (session.user.role !== 'ADMIN') {
    throw redirect(302, '/dashboard');
  }

  return { session };
};
