import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ fetchBackend: vi.fn() }));

vi.mock('$lib/backend', () => ({ fetchBackend: mocks.fetchBackend }));

import { PUT as saveDecisionProfile } from '../api/jobs/[jobId]/decision-profile/+server';
import {
  GET as listExperiments,
  POST as createExperiment,
} from '../api/jobs/[jobId]/selection-experiments/+server';
import {
  DELETE as deleteExperiment,
  PUT as updateExperiment,
} from '../api/jobs/[jobId]/selection-experiments/[experimentId]/+server';
import { POST as lockExperiment } from '../api/jobs/[jobId]/selection-experiments/[experimentId]/lock/+server';
import { POST as launchExperiment } from '../api/jobs/[jobId]/selection-experiments/[experimentId]/run/+server';
import { POST as closeExperiment } from '../api/jobs/[jobId]/selection-experiments/[experimentId]/run/close/+server';
import { GET as experimentResults } from '../api/jobs/[jobId]/selection-experiments/[experimentId]/results/+server';
import {
  GET as getNarrowingProposal,
  POST as createNarrowingProposal,
} from '../api/jobs/[jobId]/selection-experiments/[experimentId]/narrowing-proposal/+server';
import { GET as publicExperiment } from '../api/public/experiments/[publicToken]/+server';
import { POST as publicExperimentEvent } from '../api/public/experiments/[publicToken]/events/+server';
import {
  GET as listConceptSets,
  POST as createConceptSet,
} from '../api/jobs/[jobId]/selection-concept-sets/+server';
import { POST as prepareConceptOption } from '../api/jobs/[jobId]/selection-concept-sets/[setId]/options/[optionId]/proposal/+server';
import { GET as getDecisionState } from '../api/jobs/[jobId]/selection-decision-state/+server';

const locals = {
  auth: vi.fn().mockResolvedValue({ user: { id: 'owner-1' } }),
};
const jobId = '550e8400-e29b-41d4-a716-446655440000';
const experimentId = '123e4567-e89b-42d3-a456-426614174000';

function backendResponse(body: unknown = { ok: true }, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fetchBackend.mockImplementation(async () => backendResponse());
});

describe('selection decision and experiment API proxies', () => {
  it('forwards the owner-only decision projection without allowing shared caching', async () => {
    const response = await getDecisionState({ params: { jobId }, locals } as never);

    expect(mocks.fetchBackend).toHaveBeenCalledWith(
      `/api/jobs/${jobId}/selection-decision-state`,
      { headers: { 'X-User-ID': 'owner-1' } },
    );
    expect(response.headers.get('cache-control')).toBe('private, no-store');
  });

  it('forwards Concept Forge list, create, and proposal operations', async () => {
    const conceptSetPayload = {
      sets: [{
        id: '660e8400-e29b-41d4-a716-446655440000',
        artifact: {
          parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }],
        },
      }],
    };
    const proposalPayload = {
      sourceMessageId: 'proposal-message-1',
      patch: {
        kind: 'idea_synthesis',
        parents: [{ ideaId: 'idea-signal', ideaRevision: 3 }],
      },
      cached: false,
    };
    mocks.fetchBackend
      .mockResolvedValueOnce(backendResponse(conceptSetPayload))
      .mockResolvedValueOnce(backendResponse({ set: conceptSetPayload.sets[0], cached: false }, 201))
      .mockResolvedValueOnce(backendResponse(proposalPayload, 201));

    const listed = await listConceptSets({ params: { jobId }, locals } as never);

    const body = JSON.stringify({ purpose: 'diverge', parents: [] });
    const created = await createConceptSet({
      params: { jobId },
      locals,
      request: new Request('http://local', { method: 'POST', body }),
    } as never);
    const prepared = await prepareConceptOption({
      params: { jobId, setId: 'set/1', optionId: 'option/1' },
      locals,
      request: new Request('http://local', { method: 'POST', body }),
    } as never);

    expect(await listed.json()).toEqual(conceptSetPayload);
    expect(await created.json()).toEqual({ set: conceptSetPayload.sets[0], cached: false });
    expect(await prepared.json()).toEqual(proposalPayload);

    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      1,
      `/api/jobs/${jobId}/selection-concept-sets`,
      expect.objectContaining({ method: 'GET', headers: { 'X-User-ID': 'owner-1' } }),
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      2,
      `/api/jobs/${jobId}/selection-concept-sets`,
      expect.objectContaining({ method: 'POST', body }),
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      3,
      `/api/jobs/${jobId}/selection-concept-sets/set%2F1/options/option%2F1/proposal`,
      expect.objectContaining({ method: 'POST', body }),
    );
  });

  it('keeps an upstream non-JSON Concept Forge failure JSON-readable', async () => {
    mocks.fetchBackend.mockResolvedValueOnce(new Response('<!doctype html><title>Not found</title>', {
      status: 404,
      headers: { 'Content-Type': 'text/html' },
    }));

    const response = await listConceptSets({ params: { jobId }, locals } as never);

    expect(response.status).toBe(404);
    expect(response.headers.get('content-type')).toContain('application/json');
    expect(await response.json()).toEqual({
      error: 'Concept Forge could not read the server response. Please try again.',
    });
  });

  it('keeps a rejected Concept Forge upstream request JSON-readable', async () => {
    mocks.fetchBackend.mockRejectedValueOnce(new TypeError('fetch failed'));

    const response = await listConceptSets({ params: { jobId }, locals } as never);

    expect(response.status).toBe(502);
    expect(response.headers.get('content-type')).toContain('application/json');
    expect(await response.json()).toEqual({
      error: 'Concept Forge is temporarily unavailable. Please try again.',
    });
  });

  it('forwards the founder decision profile with the authenticated owner ID', async () => {
    const body = JSON.stringify({ preset: 'balanced' });
    await saveDecisionProfile({
      params: { jobId },
      locals,
      request: new Request('http://local', { method: 'PUT', body }),
    } as never);

    expect(mocks.fetchBackend).toHaveBeenCalledWith(`/api/jobs/${jobId}/decision-profile`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': 'owner-1',
      },
      body,
    });
  });

  it('forwards list, create, update, delete, and lock experiment operations', async () => {
    await listExperiments({ params: { jobId }, locals } as never);

    const createBody = JSON.stringify({ ideaId: 'idea-1' });
    const updateBody = JSON.stringify({ ideaId: 'idea-1', expectedVersion: 7 });
    const mutationBody = JSON.stringify({ expectedVersion: 7 });
    await createExperiment({
      params: { jobId },
      locals,
      request: new Request('http://local', { method: 'POST', body: createBody }),
    } as never);
    await updateExperiment({
      params: { jobId, experimentId },
      locals,
      request: new Request('http://local', { method: 'PUT', body: updateBody }),
    } as never);
    await deleteExperiment({
      params: { jobId, experimentId },
      locals,
      request: new Request('http://local', { method: 'DELETE', body: mutationBody }),
    } as never);
    await lockExperiment({
      params: { jobId, experimentId },
      locals,
      request: new Request('http://local', { method: 'POST', body: mutationBody }),
    } as never);

    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(1, `/api/jobs/${jobId}/selection-experiments`, {
      headers: { 'X-User-ID': 'owner-1' },
    });
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(2, `/api/jobs/${jobId}/selection-experiments`, expect.objectContaining({
      method: 'POST',
      body: createBody,
    }));
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(3, `/api/jobs/${jobId}/selection-experiments/${experimentId}`, expect.objectContaining({
      method: 'PUT',
      body: updateBody,
    }));
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(4, `/api/jobs/${jobId}/selection-experiments/${experimentId}`, expect.objectContaining({
      method: 'DELETE',
      body: mutationBody,
    }));
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(5, `/api/jobs/${jobId}/selection-experiments/${experimentId}/lock`, expect.objectContaining({
      method: 'POST',
      body: mutationBody,
    }));
  });

  it('preserves an empty 204 response when deleting an experiment draft', async () => {
    mocks.fetchBackend.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const body = JSON.stringify({ expectedVersion: 3 });

    const response = await deleteExperiment({
      params: { jobId, experimentId },
      locals,
      request: new Request('http://local', { method: 'DELETE', body }),
    } as never);

    expect(response.status).toBe(204);
    expect(await response.text()).toBe('');
  });


  it('forwards run publication, close, and results with owner identity', async () => {
    const body = JSON.stringify({
      headline: 'Signal Desk',
      promise: 'Find recurring buyer signals',
      ctaLabel: 'IM_INTERESTED',
    });
    await launchExperiment({
      params: { jobId, experimentId },
      locals,
      request: new Request('http://local', { method: 'POST', body }),
    } as never);
    await closeExperiment({ params: { jobId, experimentId }, locals } as never);
    await experimentResults({ params: { jobId, experimentId }, locals } as never);

    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      1,
      `/api/jobs/${jobId}/selection-experiments/${experimentId}/run`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'X-User-ID': 'owner-1' }),
        body,
      }),
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      2,
      `/api/jobs/${jobId}/selection-experiments/${experimentId}/run/close`,
      expect.objectContaining({ method: 'POST', headers: { 'X-User-ID': 'owner-1' } }),
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      3,
      `/api/jobs/${jobId}/selection-experiments/${experimentId}/results`,
      { headers: { 'X-User-ID': 'owner-1' } },
    );
  });

  it('forwards narrowing proposal reads and generation with owner identity and no-store responses', async () => {
    const loaded = await getNarrowingProposal({ params: { jobId, experimentId }, locals } as never);
    const created = await createNarrowingProposal({ params: { jobId, experimentId }, locals } as never);

    const path = `/api/jobs/${jobId}/selection-experiments/${experimentId}/narrowing-proposal`;
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(1, path, {
      headers: { 'X-User-ID': 'owner-1' },
    });
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(2, path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': 'owner-1',
      },
      body: '{}',
    });
    expect(loaded.headers.get('cache-control')).toBe('private, no-store');
    expect(created.headers.get('cache-control')).toBe('private, no-store');
  });

  it('keeps public test traffic behind the service proxy and forwards only the trusted client address', async () => {
    const publicToken = 'opaque-public-token';
    const body = JSON.stringify({
      eventId: '323e4567-e89b-42d3-a456-426614174000',
      viewToken: 'signed.view',
      type: 'STIMULUS_EXPOSED',
      occurredAt: '2026-07-15T12:00:00.000Z',
    });

    await publicExperiment({ params: { publicToken } } as never);
    await publicExperimentEvent({
      params: { publicToken },
      request: new Request('http://local', { method: 'POST', body }),
      getClientAddress: () => '203.0.113.10',
    } as never);

    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      1,
      `/api/public/experiments/${publicToken}`,
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      2,
      `/api/public/experiments/${publicToken}/events`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Client-IP': '203.0.113.10',
        },
        body,
      },
    );
  });
});
