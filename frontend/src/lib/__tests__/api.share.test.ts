import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getShareStatus,
  enableSharing,
  disableSharing,
  regenerateShareToken,
  ApiError,
} from '../api';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

const TEST_JOB_ID = '550e8400-e29b-41d4-a716-446655440000';

describe('Report Sharing API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  // ============================================
  // getShareStatus
  // ============================================
  describe('getShareStatus', () => {
    it('calls GET /api/jobs/:jobId/share and returns response', async () => {
      const mockResponse = {
        isShared: true,
        shareToken: 'abcdefghijklmnopqrstuv',
        viewCount: 5,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getShareStatus(TEST_JOB_ID);

      expect(mockFetch).toHaveBeenCalledWith(`/api/jobs/${TEST_JOB_ID}/share`);
      expect(result).toEqual(mockResponse);
    });

    it('throws ApiError on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'Job not found' }),
      });

      await expect(getShareStatus(TEST_JOB_ID)).rejects.toThrow(ApiError);
    });
  });

  // ============================================
  // enableSharing
  // ============================================
  describe('enableSharing', () => {
    it('calls POST /api/jobs/:jobId/share and returns response', async () => {
      const mockResponse = {
        isShared: true,
        shareToken: 'abcdefghijklmnopqrstuv',
        viewCount: 0,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await enableSharing(TEST_JOB_ID);

      expect(mockFetch).toHaveBeenCalledWith(`/api/jobs/${TEST_JOB_ID}/share`, {
        method: 'POST',
      });
      expect(result).toEqual(mockResponse);
    });

    it('throws ApiError on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Only completed jobs can be shared' }),
      });

      await expect(enableSharing(TEST_JOB_ID)).rejects.toThrow(ApiError);
    });
  });

  // ============================================
  // disableSharing
  // ============================================
  describe('disableSharing', () => {
    it('calls DELETE /api/jobs/:jobId/share and returns response', async () => {
      const mockResponse = { isShared: false };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await disableSharing(TEST_JOB_ID);

      expect(mockFetch).toHaveBeenCalledWith(`/api/jobs/${TEST_JOB_ID}/share`, {
        method: 'DELETE',
      });
      expect(result).toEqual(mockResponse);
    });

    it('throws ApiError on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ error: 'Not authorized' }),
      });

      await expect(disableSharing(TEST_JOB_ID)).rejects.toThrow(ApiError);
    });
  });

  // ============================================
  // regenerateShareToken
  // ============================================
  describe('regenerateShareToken', () => {
    it('calls POST /api/jobs/:jobId/share/regenerate and returns response', async () => {
      const mockResponse = {
        isShared: true,
        shareToken: 'ZZZZZZZZZZZZZZZZZZZZZZ',
        viewCount: 0,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await regenerateShareToken(TEST_JOB_ID);

      expect(mockFetch).toHaveBeenCalledWith(
        `/api/jobs/${TEST_JOB_ID}/share/regenerate`,
        { method: 'POST' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('throws ApiError on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'Sharing not enabled for this job' }),
      });

      await expect(regenerateShareToken(TEST_JOB_ID)).rejects.toThrow(ApiError);
    });
  });
});
