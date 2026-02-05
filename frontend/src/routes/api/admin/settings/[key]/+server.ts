import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const GET: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }
  if (session.user.role !== 'ADMIN') {
    throw error(403, 'Admin access required');
  }

  const response = await fetch(`${BACKEND_URL}/api/admin/settings/${params.key}`, {
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
  });

  try {
    const data = await response.json();
    return json(data, { status: response.status });
  } catch {
    return json({ error: 'Unexpected backend response' }, { status: 502 });
  }
};

export const PUT: RequestHandler = async ({ params, request, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }
  if (session.user.role !== 'ADMIN') {
    throw error(403, 'Admin access required');
  }

  const body = await request.json();

  const response = await fetch(`${BACKEND_URL}/api/admin/settings/${params.key}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
    body: JSON.stringify(body),
  });

  try {
    const data = await response.json();
    return json(data, { status: response.status });
  } catch {
    return json({ error: 'Unexpected backend response' }, { status: 502 });
  }
};

export const DELETE: RequestHandler = async ({ params, locals }) => {
  const session = await locals.auth();
  if (!session?.user) {
    throw error(401, 'Unauthorized');
  }
  if (session.user.role !== 'ADMIN') {
    throw error(403, 'Admin access required');
  }

  const response = await fetch(`${BACKEND_URL}/api/admin/settings/${params.key}`, {
    method: 'DELETE',
    headers: {
      'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
      'X-User-ID': session.user.id,
      'X-User-Role': session.user.role,
    },
  });

  try {
    const data = await response.json();
    return json(data, { status: response.status });
  } catch {
    return json({ error: 'Unexpected backend response' }, { status: 502 });
  }
};
