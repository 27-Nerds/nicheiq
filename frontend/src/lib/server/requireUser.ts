import { error } from '@sveltejs/kit';

export async function requireUser(locals: App.Locals) {
  const session = await locals.auth();
  if (!session?.user) throw error(401, 'Unauthorized');
  return session.user;
}

export async function requireUserId(locals: App.Locals): Promise<string> {
  return (await requireUser(locals)).id;
}
