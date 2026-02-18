import type { LayoutServerLoad } from './$types';
import { getAvailableProviders } from '../auth';

export const load: LayoutServerLoad = async (event) => {
  const session = await event.locals.auth?.();
  return { session: session ?? null, availableProviders: getAvailableProviders() };
};
