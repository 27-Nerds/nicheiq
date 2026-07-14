import { readFile } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import { AssetType } from '@prisma/client';
import { getJobAsset } from './jobService.js';
import { resolveAssetPath, getAllowedAssetRoot } from '../utils/assetPath.js';

const CACHE_TTL = 10 * 60 * 1000;
const CACHE_MAX = 200;

const discoveryCache = new Map<string, { data: unknown; ts: number }>();
const previewReportCache = new Map<string, { data: unknown; ts: number }>();

function readFromCache(cache: Map<string, { data: unknown; ts: number }>, key: string): unknown | null {
  const cached = cache.get(key);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return cached.data;
  return null;
}

function writeToCache(cache: Map<string, { data: unknown; ts: number }>, key: string, data: unknown): void {
  if (cache.size >= CACHE_MAX) {
    const oldest = [...cache.entries()].sort((a, b) => a[1].ts - b[1].ts)[0];
    if (oldest) cache.delete(oldest[0]);
  }
  cache.set(key, { data, ts: Date.now() });
}

async function readAssetJson(jobId: string, assetType: AssetType, logLabel: string): Promise<unknown | null> {
  const asset = await getJobAsset(jobId, assetType);
  if (!asset) return null;

  let resolvedPath: string;
  try {
    resolvedPath = resolveAssetPath(asset.filePath);
  } catch (err) {
    console.error(`[assetService] ${logLabel} path rejected: ${(err as Error).message} (filePath=${asset.filePath})`);
    return null;
  }

  const allowedRoot = getAllowedAssetRoot();
  if (resolvedPath !== allowedRoot && !resolvedPath.startsWith(allowedRoot + path.sep)) {
    console.error(`[assetService] ${logLabel} path traversal attempt: ${resolvedPath}`);
    return null;
  }
  if (!existsSync(resolvedPath)) return null;

  const raw = await readFile(resolvedPath, 'utf-8');
  return JSON.parse(raw);
}

export async function getDiscoveryDataForJob(jobId: string): Promise<unknown | null> {
  const cached = readFromCache(discoveryCache, jobId);
  if (cached) return cached;

  const data = await readAssetJson(jobId, AssetType.DISCOVERY_DATA, 'Discovery data');
  if (data === null) return null;
  writeToCache(discoveryCache, jobId, data);
  return data;
}

export async function getPreviewReportForJob(jobId: string): Promise<unknown | null> {
  const cached = readFromCache(previewReportCache, jobId);
  if (cached) return cached;

  const data = await readAssetJson(jobId, AssetType.PREVIEW_REPORT, 'Preview report');
  if (data === null) return null;
  writeToCache(previewReportCache, jobId, data);
  return data;
}

/**
 * Drop a job's cached preview report so the next read re-parses the on-disk file. The
 * worker's preview-report asset is keyed by job_id and gets overwritten in place (e.g. a
 * seed dispatch re-materializes it to add a ruled-out record) — the file path never
 * changes, but the CACHE_TTL window would otherwise keep serving the pre-seed snapshot.
 */
export function invalidatePreviewReportCache(jobId: string): void {
  previewReportCache.delete(jobId);
}
