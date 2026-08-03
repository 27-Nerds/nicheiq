import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  changePassword,
  getSelectionConceptSets,
  getSelectionMetricExplanations,
  regenerateIdeas,
  updateSelectionExperiment,
  lockSelectionExperiment,
  deleteSelectionExperiment,
  ApiError,
} from '../api';
import type { SelectionExperimentDraft } from '../types/selectionExperiment';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('Notification Preferences API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('getNotificationPreferences', () => {
    it('fetches notification preferences successfully', async () => {
      const mockPrefs = {
        emailEnabled: true,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPrefs,
      });

      const result = await getNotificationPreferences('user-123');

      expect(mockFetch).toHaveBeenCalledWith('/api/users/user-123/notification-preferences');
      expect(result).toEqual(mockPrefs);
    });

    it('throws ApiError on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'User not found' }),
      });

      await expect(getNotificationPreferences('invalid-user')).rejects.toThrow(ApiError);
    });
  });

  describe('updateNotificationPreferences', () => {
    it('updates notification preferences successfully', async () => {
      const updatedPrefs = {
        emailEnabled: false,
        emailOnJobStart: true,
        emailOnJobComplete: true,
        emailOnJobError: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => updatedPrefs,
      });

      const result = await updateNotificationPreferences('user-123', {
        emailEnabled: false,
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/users/user-123/notification-preferences',
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ emailEnabled: false }),
        })
      );
      expect(result).toEqual(updatedPrefs);
    });

    it('handles partial updates', async () => {
      const updatedPrefs = {
        emailEnabled: true,
        emailOnJobStart: false,
        emailOnJobComplete: true,
        emailOnJobError: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => updatedPrefs,
      });

      await updateNotificationPreferences('user-123', {
        emailOnJobStart: false,
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/users/user-123/notification-preferences',
        expect.objectContaining({
          body: JSON.stringify({ emailOnJobStart: false }),
        })
      );
    });

    it('throws ApiError on validation failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'No valid preference fields provided' }),
      });

      await expect(
        updateNotificationPreferences('user-123', {})
      ).rejects.toThrow(ApiError);
    });
  });
});

describe('Selection metric explanations API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the authenticated proxy contract', async () => {
    const payload = {
      schemaVersion: 1 as const,
      metrics: [{
        key: 'research_score',
        label: 'Research score',
        kind: 'derived_score' as const,
        range: '0-100' as const,
        summary: 'Ranking score',
        method: 'Weighted from research dimensions',
        sourceFields: ['adjusted_composite_score'],
      }],
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => payload,
    });

    await expect(getSelectionMetricExplanations()).resolves.toEqual(payload);
    expect(mockFetch).toHaveBeenCalledWith('/api/selection/metric-explanations');
  });
});

describe('Password API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('changePassword', () => {
    it('changes password successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Password changed successfully' }),
      });

      const result = await changePassword('user-123', {
        currentPassword: 'oldpass123',
        newPassword: 'newpass123',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/users/user-123/change-password',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            currentPassword: 'oldpass123',
            newPassword: 'newpass123',
          }),
        })
      );
      expect(result).toEqual({ message: 'Password changed successfully' });
    });

    it('throws ApiError when current password is wrong', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ error: 'Current password is incorrect' }),
      });

      await expect(
        changePassword('user-123', {
          currentPassword: 'wrongpass',
          newPassword: 'newpass123',
        })
      ).rejects.toThrow(ApiError);

      try {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ error: 'Current password is incorrect' }),
        });
        await changePassword('user-123', {
          currentPassword: 'wrongpass',
          newPassword: 'newpass123',
        });
      } catch (error) {
        expect((error as ApiError).status).toBe(401);
        expect((error as ApiError).message).toBe('Current password is incorrect');
      }
    });

    it('throws ApiError for OAuth users without password', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Account uses OAuth login. Password cannot be changed.' }),
      });

      await expect(
        changePassword('user-123', {
          currentPassword: 'anything',
          newPassword: 'newpass123',
        })
      ).rejects.toThrow(ApiError);
    });

    it('throws ApiError when new password is too short', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          error: 'Validation error',
          details: [{ message: 'New password must be at least 8 characters' }],
        }),
      });

      await expect(
        changePassword('user-123', {
          currentPassword: 'oldpass123',
          newPassword: 'short',
        })
      ).rejects.toThrow(ApiError);
    });
  });
});

describe('ApiError', () => {
  it('creates error with correct properties', () => {
    const error = new ApiError('Test error', 404, { detail: 'Not found' });

    expect(error.message).toBe('Test error');
    expect(error.status).toBe(404);
    expect(error.details).toEqual({ detail: 'Not found' });
    expect(error.name).toBe('ApiError');
  });

  it('converts a non-JSON API response into a readable transport error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => { throw new SyntaxError('Unexpected token <'); },
    });

    await expect(getSelectionConceptSets('job-1')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'The request could not be completed. Please try again.',
    });
  });
});

describe('Idea batch API', () => {
  it('forwards the idempotency key, confirmed price, and requested focus', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: 'Additional batch queued',
        operationId: 'dispatch-1',
        batchOrdinal: 3,
        focus: 'novelty',
      }),
    });

    await regenerateIdeas('job-1', {
      clientRequestId: '15f6fe10-cbbe-4cea-94b8-ead2a0b718ee',
      expectedCost: 2,
      idea_focus: 'novelty',
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/jobs/job-1/regenerate-ideas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clientRequestId: '15f6fe10-cbbe-4cea-94b8-ead2a0b718ee',
        expectedCost: 2,
        idea_focus: 'novelty',
      }),
    });
  });
});

describe('Selection experiment mutation API', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('sends the compare-and-set version for update, lock, and delete', async () => {
    const draft = { ideaId: 'idea-1', ideaRevision: 2 } as SelectionExperimentDraft;
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ experiment: { id: 'experiment-1', version: 8 } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ experiment: { id: 'experiment-1', version: 9 } }),
      })
      .mockResolvedValueOnce({ ok: true, status: 204 });

    await updateSelectionExperiment('job-1', 'experiment-1', 7, draft);
    await lockSelectionExperiment('job-1', 'experiment-1', 8);
    await deleteSelectionExperiment('job-1', 'experiment-1', 9);

    expect(mockFetch).toHaveBeenNthCalledWith(1, '/api/jobs/job-1/selection-experiments/experiment-1', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...draft, expectedVersion: 7 }),
    });
    expect(mockFetch).toHaveBeenNthCalledWith(2, '/api/jobs/job-1/selection-experiments/experiment-1/lock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expectedVersion: 8 }),
    });
    expect(mockFetch).toHaveBeenNthCalledWith(3, '/api/jobs/job-1/selection-experiments/experiment-1', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expectedVersion: 9 }),
    });
  });
});
