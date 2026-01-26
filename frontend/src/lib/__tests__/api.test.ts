import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  changePassword,
  ApiError,
} from '../api';

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
});
