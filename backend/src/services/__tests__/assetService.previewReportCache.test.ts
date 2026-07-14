/**
 * Preview-report cache invalidation (seed outcome-delivery fix). The worker
 * re-materializes the preview report IN PLACE (same file path, keyed by job_id)
 * whenever a seed settles, to fold in a new ruled-out/accepted record — the file
 * changes but the path doesn't, so the in-memory cache (CACHE_TTL) must be dropped
 * explicitly rather than relying on the path changing.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetJobAsset = vi.fn();
const mockExistsSync = vi.fn();
const mockReadFile = vi.fn();

vi.mock('../jobService.js', () => ({
  getJobAsset: (...a: any[]) => mockGetJobAsset(...a),
}));

vi.mock('fs', () => ({
  existsSync: (...a: any[]) => mockExistsSync(...a),
}));

vi.mock('fs/promises', () => ({
  readFile: (...a: any[]) => mockReadFile(...a),
}));

vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: (p: string) => `/allowed/root/${p}`,
  getAllowedAssetRoot: () => '/allowed/root',
}));

const jobId = 'job-1';

// The cache Maps are module-level singletons (by design — shared across every request in
// the running process). Reset the module registry per test so each test gets its OWN empty
// cache, instead of leaking cached entries from a prior test in this file.
beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
  mockGetJobAsset.mockResolvedValue({ filePath: 'preview_report_job-1.json' });
  mockExistsSync.mockReturnValue(true);
});

describe('getPreviewReportForJob caching', () => {
  it('serves the cached parse on a second read within CACHE_TTL without touching disk again', async () => {
    const { getPreviewReportForJob } = await import('../assetService.js');
    mockReadFile.mockResolvedValueOnce(JSON.stringify({ examined_ruled_out: [] }));

    const first = await getPreviewReportForJob(jobId);
    const second = await getPreviewReportForJob(jobId);

    expect(first).toEqual({ examined_ruled_out: [] });
    expect(second).toEqual({ examined_ruled_out: [] });
    expect(mockReadFile).toHaveBeenCalledTimes(1);
  });

  it('re-reads disk after invalidatePreviewReportCache, picking up a re-materialized file at the same path', async () => {
    const { getPreviewReportForJob, invalidatePreviewReportCache } = await import('../assetService.js');
    mockReadFile
      .mockResolvedValueOnce(JSON.stringify({ examined_ruled_out: [] }))
      .mockResolvedValueOnce(
        JSON.stringify({ examined_ruled_out: [{ pain_title: 'x', source_frame: 'user_seed' }] }),
      );

    const beforeSeed = await getPreviewReportForJob(jobId);
    invalidatePreviewReportCache(jobId);
    const afterSeed = await getPreviewReportForJob(jobId);

    expect(beforeSeed).toEqual({ examined_ruled_out: [] });
    expect(afterSeed).toEqual({
      examined_ruled_out: [{ pain_title: 'x', source_frame: 'user_seed' }],
    });
    expect(mockReadFile).toHaveBeenCalledTimes(2);
  });

  it('invalidating a different job id does not evict this job from cache', async () => {
    const { getPreviewReportForJob, invalidatePreviewReportCache } = await import('../assetService.js');
    mockReadFile.mockResolvedValueOnce(JSON.stringify({ examined_ruled_out: [] }));

    await getPreviewReportForJob(jobId);
    invalidatePreviewReportCache('some-other-job');
    await getPreviewReportForJob(jobId);

    expect(mockReadFile).toHaveBeenCalledTimes(1);
  });
});
