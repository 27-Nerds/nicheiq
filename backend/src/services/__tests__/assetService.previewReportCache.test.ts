/**
 * Preview-report cache invalidation (seed outcome-delivery fix). The worker
 * re-materializes the preview report IN PLACE (same file path, keyed by job_id)
 * whenever a seed settles, to fold in a new ruled-out/accepted record — the file
 * changes but the path doesn't, so the in-memory cache (CACHE_TTL) must be dropped
 * explicitly rather than relying on the path changing.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createHash } from 'node:crypto';

const mockGetJobAsset = vi.fn();
const mockExistsSync = vi.fn();
const mockReadFile = vi.fn();
const mockStat = vi.fn();

vi.mock('../jobService.js', () => ({
  getJobAsset: (...a: any[]) => mockGetJobAsset(...a),
}));

vi.mock('fs', () => ({
  existsSync: (...a: any[]) => mockExistsSync(...a),
}));

vi.mock('fs/promises', () => ({
  readFile: (...a: any[]) => mockReadFile(...a),
  stat: (...a: any[]) => mockStat(...a),
}));

vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: (p: string) => `/allowed/root/${p}`,
  getAllowedAssetRoot: () => '/allowed/root',
}));

const jobId = 'job-1';

function publishableAsset(raw: string, filePath = 'preview_report_job-1.json') {
  return {
    filePath,
    commercialCopyStatus: 'GENERATED_CONTRACT',
    commercialCopySha256: createHash('sha256').update(raw).digest('hex'),
  };
}

// The cache Maps are module-level singletons (by design — shared across every request in
// the running process). Reset the module registry per test so each test gets its OWN empty
// cache, instead of leaking cached entries from a prior test in this file.
beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
  mockGetJobAsset.mockReset();
  mockExistsSync.mockReturnValue(true);
  mockStat.mockResolvedValue({ mtimeMs: 1, size: 100, ino: 10 });
});

describe('getPreviewReportForJob caching', () => {
  it('serves the cached parse on a second read within CACHE_TTL without touching disk again', async () => {
    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    const raw = JSON.stringify({ examined_ruled_out: [] });
    mockGetJobAsset.mockResolvedValue(publishableAsset(raw));
    mockReadFile.mockResolvedValueOnce(raw);

    const first = await getPreviewReportForJob(jobId);
    const second = await getPreviewReportForJob(jobId);

    expect(first).toEqual({ examined_ruled_out: [] });
    expect(second).toEqual({ examined_ruled_out: [] });
    expect(mockReadFile).toHaveBeenCalledTimes(1);
  });

  it('re-reads disk after invalidatePreviewReportCache, picking up a re-materialized file at the same path', async () => {
    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    const { invalidatePreviewReportCache } = await import('../assetService.js');
    const beforeRaw = JSON.stringify({ examined_ruled_out: [] });
    const afterRaw = JSON.stringify({ examined_ruled_out: [{ pain_title: 'x', source_frame: 'user_seed' }] });
    mockGetJobAsset
      .mockResolvedValueOnce(publishableAsset(beforeRaw))
      .mockResolvedValueOnce(publishableAsset(afterRaw));
    mockReadFile
      .mockResolvedValueOnce(beforeRaw)
      .mockResolvedValueOnce(afterRaw);

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
    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    const { invalidatePreviewReportCache } = await import('../assetService.js');
    const raw = JSON.stringify({ examined_ruled_out: [] });
    mockGetJobAsset.mockResolvedValue(publishableAsset(raw));
    mockReadFile.mockResolvedValueOnce(raw);

    await getPreviewReportForJob(jobId);
    invalidatePreviewReportCache('some-other-job');
    await getPreviewReportForJob(jobId);

    expect(mockReadFile).toHaveBeenCalledTimes(1);
  });

  it('re-reads an atomically replaced preview asset without waiting for the TTL', async () => {
    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    const beforeRaw = JSON.stringify({ narrative_summary: 'legacy contradiction' });
    const afterRaw = JSON.stringify({ narrative_summary: 'reconciled copy' });
    mockGetJobAsset
      .mockResolvedValueOnce(publishableAsset(beforeRaw))
      .mockResolvedValueOnce(publishableAsset(afterRaw));
    mockReadFile
      .mockResolvedValueOnce(beforeRaw)
      .mockResolvedValueOnce(afterRaw);
    mockStat
      .mockResolvedValueOnce({ mtimeMs: 1, size: 100, ino: 10 })
      .mockResolvedValueOnce({ mtimeMs: 2, size: 80, ino: 11 })
      .mockResolvedValueOnce({ mtimeMs: 2, size: 80, ino: 11 });

    const beforeBackfill = await getPreviewReportForJob(jobId);
    const afterBackfill = await getPreviewReportForJob(jobId);

    expect(beforeBackfill).toEqual({ narrative_summary: 'legacy contradiction' });
    expect(afterBackfill).toEqual({ narrative_summary: 'reconciled copy' });
    expect(mockReadFile).toHaveBeenCalledTimes(2);
  });

  it('re-reads an atomically replaced final-report asset without waiting for the TTL', async () => {
    const { getReportJsonForJob } = await import('../assetService.js');
    const beforeRaw = JSON.stringify({ narrative_summary: 'legacy contradiction' });
    const afterRaw = JSON.stringify({ narrative_summary: 'reconciled copy' });
    mockGetJobAsset
      .mockResolvedValueOnce(publishableAsset(beforeRaw))
      .mockResolvedValueOnce(publishableAsset(afterRaw));
    mockReadFile
      .mockResolvedValueOnce(beforeRaw)
      .mockResolvedValueOnce(afterRaw);
    mockStat
      .mockResolvedValueOnce({ mtimeMs: 1, size: 100, ino: 10 })
      .mockResolvedValueOnce({ mtimeMs: 2, size: 80, ino: 11 })
      .mockResolvedValueOnce({ mtimeMs: 2, size: 80, ino: 11 });

    await expect(getReportJsonForJob(jobId)).resolves.toEqual({
      narrative_summary: 'legacy contradiction',
    });
    await expect(getReportJsonForJob(jobId)).resolves.toEqual({
      narrative_summary: 'reconciled copy',
    });
    expect(mockReadFile).toHaveBeenCalledTimes(2);
  });

  it('follows an authoritative JobAsset path CAS even while the old cached file is unchanged', async () => {
    const oldRaw = JSON.stringify({ narrative_summary: 'legacy contradiction' });
    const newRaw = JSON.stringify({ narrative_summary: 'reconciled copy' });
    mockGetJobAsset
      .mockResolvedValueOnce({
        filePath: 'old.json',
        commercialCopyStatus: 'RECONCILED',
        commercialCopySha256: createHash('sha256').update(oldRaw).digest('hex'),
      })
      .mockResolvedValueOnce({
        filePath: 'immutable-new.json',
        commercialCopyStatus: 'RECONCILED',
        commercialCopySha256: createHash('sha256').update(newRaw).digest('hex'),
      });
    mockReadFile.mockResolvedValueOnce(oldRaw).mockResolvedValueOnce(newRaw);
    mockStat
      .mockResolvedValueOnce({ mtimeMs: 1, size: oldRaw.length, ino: 10 })
      .mockResolvedValueOnce({ mtimeMs: 2, size: newRaw.length, ino: 11 });

    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');

    await expect(getPreviewReportForJob(jobId)).resolves.toEqual({
      narrative_summary: 'legacy contradiction',
    });
    await expect(getPreviewReportForJob(jobId)).resolves.toEqual({
      narrative_summary: 'reconciled copy',
    });
    expect(mockReadFile).toHaveBeenCalledTimes(2);
  });

  it('fails closed when the authoritative hash does not match disk', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    mockGetJobAsset.mockResolvedValueOnce({
      filePath: 'preview_report_job-1.json',
      commercialCopyStatus: 'RECONCILED',
      commercialCopySha256: '0'.repeat(64),
    });
    mockReadFile.mockResolvedValueOnce(JSON.stringify({ unsafe: true }));

    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    await expect(getPreviewReportForJob(jobId)).resolves.toBeNull();
    expect(error).toHaveBeenCalledWith(expect.stringContaining('registered content hash is stale'));
    error.mockRestore();
  });

  it('fails closed while an authoritative asset is pending or partially reconciled', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    mockGetJobAsset.mockResolvedValueOnce({
      filePath: 'preview_report_job-1.json',
      commercialCopyStatus: 'PARTIAL',
      commercialCopySha256: 'a'.repeat(64),
    });

    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    await expect(getPreviewReportForJob(jobId)).resolves.toBeNull();
    expect(mockReadFile).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith(expect.stringContaining('blocked by commercial-copy fence'));
    error.mockRestore();
  });

  it('fails closed when wallet publication metadata is missing', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    mockGetJobAsset.mockResolvedValueOnce({ filePath: 'preview_report_job-1.json' });

    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    await expect(getPreviewReportForJob(jobId)).resolves.toBeNull();
    expect(mockReadFile).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith(expect.stringContaining('status=undefined'));
    error.mockRestore();
  });

  it('publishes a proven non-paying asset with a matching registered hash', async () => {
    const raw = JSON.stringify({ market_reality: { wallet: { wallet_class: 'free-culture' } } });
    mockGetJobAsset.mockResolvedValueOnce({
      ...publishableAsset(raw),
      commercialCopyStatus: 'NOT_APPLICABLE',
    });
    mockReadFile.mockResolvedValueOnce(raw);

    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    await expect(getPreviewReportForJob(jobId)).resolves.toEqual({
      market_reality: { wallet: { wallet_class: 'free-culture' } },
    });
  });

  it('returns null instead of crashing when an asset contains invalid JSON', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { getPreviewReportForJob } = await import('../selectionBoundary/rawPreviewReport.js');
    const raw = '{broken';
    mockGetJobAsset.mockResolvedValueOnce(publishableAsset(raw));
    mockReadFile.mockResolvedValueOnce(raw);

    await expect(getPreviewReportForJob(jobId)).resolves.toBeNull();
    expect(error).toHaveBeenCalledWith(expect.stringContaining('Preview report could not be read'));
    error.mockRestore();
  });
});
