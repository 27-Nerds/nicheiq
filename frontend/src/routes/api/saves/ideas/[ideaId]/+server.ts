import type { RequestHandler } from './$types';
import { proxyToSaves } from '$lib/server/savesProxy';

export const DELETE: RequestHandler = (event) =>
  proxyToSaves(event, 'DELETE', `/ideas/${event.params.ideaId}`);

export const PATCH: RequestHandler = (event) =>
  proxyToSaves(event, 'PATCH', `/ideas/${event.params.ideaId}`);
