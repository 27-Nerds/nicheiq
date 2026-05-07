import type { RequestHandler } from './$types';
import { proxyToSaves } from '$lib/server/savesProxy';

export const GET: RequestHandler = (event) => proxyToSaves(event, 'GET', '/ideas');
export const POST: RequestHandler = (event) => proxyToSaves(event, 'POST', '/ideas');
