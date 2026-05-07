import type { RequestHandler } from './$types';
import { proxyToSaves } from '$lib/server/savesProxy';

export const DELETE: RequestHandler = (event) =>
  proxyToSaves(event, 'DELETE', `/pain-points/${event.params.painPointId}`);

export const PATCH: RequestHandler = (event) =>
  proxyToSaves(event, 'PATCH', `/pain-points/${event.params.painPointId}`);
