import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

export const GET: RequestHandler = async ({ params, locals }) => {
	const session = await locals.auth();
	if (!session?.user) throw error(401, 'Unauthorized');
	if (session.user.role !== 'ADMIN') throw error(403, 'Admin access required');

	let response: globalThis.Response;
	try {
		response = await fetch(`${BACKEND_URL}/api/admin/jobs/${params.jobId}/checkpoint`, {
			headers: {
				'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || '',
				'X-User-ID': session.user.id,
				'X-User-Role': session.user.role || ''
			}
		});
	} catch (err) {
		console.error('Backend fetch failed:', err);
		throw error(502, 'Backend service unavailable');
	}

	if (!response.ok) {
		let message = 'Failed to download checkpoint';
		try {
			const data = await response.json();
			message = data.error || message;
		} catch { /* non-JSON error body */ }
		throw error(response.status, message);
	}

	const headers: Record<string, string> = {
		'Content-Type': response.headers.get('Content-Type') || 'application/zip'
	};
	const disposition = response.headers.get('Content-Disposition');
	if (disposition) headers['Content-Disposition'] = disposition;
	const length = response.headers.get('Content-Length');
	if (length) headers['Content-Length'] = length;

	return new Response(response.body, { status: response.status, headers });
};
