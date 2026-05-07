import type { RequestHandler } from './$types';
import { proxyToSaves } from '$lib/server/savesProxy';

export const GET: RequestHandler = (event) => proxyToSaves(event, 'GET', '/pain-points');
export const POST: RequestHandler = (event) => proxyToSaves(event, 'POST', '/pain-points');
