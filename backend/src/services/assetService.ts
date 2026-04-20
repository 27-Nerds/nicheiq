import { readFile } from 'fs/promises';
import { existsSync } from 'fs';
import { resolve as pathResolve } from 'path';
import { AssetType } from '@prisma/client';
import { getJobAsset } from './jobService.js';
import { resolveAssetPath } from '../utils/assetPath.js';

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

  const resolvedPath = resolveAssetPath(asset.filePath);
  const normalizedPath = pathResolve(resolvedPath);
  if (!normalizedPath.startsWith(pathResolve('output')) && !normalizedPath.startsWith('/home')) {
    console.error(`[assetService] ${logLabel} path traversal attempt: ${normalizedPath}`);
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
