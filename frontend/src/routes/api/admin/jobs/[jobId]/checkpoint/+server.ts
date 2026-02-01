import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const GET: RequestHandler = async ({ params, locals }) => {
	const session = await locals.auth();
	if (!session?.user) throw error(401, 'Unauthorized');
	if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

	const response = await fetch(`${BACKEND_URL}/api/admin/jobs/${params.jobId}/checkpoint`, {
		headers: {
			'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
			'X-User-ID': session.user.id,
			'X-User-Role': session.user.role || ''
		}
	});

	if (!response.ok) {
		const data = await response.json();
		throw error(response.status, data.error || 'Failed to download checkpoint');
	}

	return new Response(response.body, {
		status: response.status,
		headers: {
			'Content-Type': response.headers.get('Content-Type') || 'application/zip',
			'Content-Disposition': response.headers.get('Content-Disposition') || '',
			'Content-Length': response.headers.get('Content-Length') || ''
		}
	});
};
