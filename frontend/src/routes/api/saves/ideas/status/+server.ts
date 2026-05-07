import type { RequestHandler } from './$types';
import { proxyToSaves } from '$lib/server/savesProxy';

// Static `status` route wins over the sibling `[ideaId]` dynamic param,
// so requests to /api/saves/ideas/status are routed here.
export const GET: RequestHandler = (event) => proxyToSaves(event, 'GET', '/ideas/status');
