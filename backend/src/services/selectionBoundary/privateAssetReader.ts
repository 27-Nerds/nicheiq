import { readFile, stat } from 'fs/promises';
import { existsSync } from 'fs';
import { createHash } from 'node:crypto';
import path from 'path';
import { AssetType } from '@prisma/client';
import { getJobAsset } from '../jobService.js';
import { resolveAssetPath, getAllowedAssetRoot } from '../../utils/assetPath.js';
import {
  needsCommercialCopyFence,
  PUBLISHABLE_COMMERCIAL_COPY_STATUSES,
} from '../assetPublicationFence.js';

const CACHE_TTL = 10 * 60 * 1000;
const CACHE_MAX = 200;

interface CacheEntry {
  data: unknown;
  ts: number;
  filePath: string;
  mtimeMs: number;
  size: number;
  ino: number;
  sha256: string;
}

interface AssetJson {
  data: unknown;
  filePath: string;
  mtimeMs: number;
  size: number;
  ino: number;
  sha256: string;
}

export type AssetReadResult =
  | { status: 'ready'; asset: AssetJson }
  | { status: 'missing' }
  | { status: 'publication_blocked'; reason: string };

export type AssetCache = Map<string, CacheEntry>;

export const discoveryCache: AssetCache = new Map();
export const previewReportCache: AssetCache = new Map();
export const reportJsonCache: AssetCache = new Map();

async function readFromCache(
  cache: AssetCache,
  key: string,
  filePath: string,
  expectedSha256: string | null,
  checkFileFreshness = true,
): Promise<unknown | null> {
  const cached = cache.get(key);
  if (!cached || Date.now() - cached.ts >= CACHE_TTL) {
    cache.delete(key);
    return null;
  }
  if (cached.filePath !== filePath) {
    cache.delete(key);
    return null;
  }
  if (expectedSha256 && cached.sha256 !== expectedSha256) {
    cache.delete(key);
    return null;
  }
  if (!checkFileFreshness) return cached.data;

  try {
    const current = await stat(cached.filePath);
    if (
      current.mtimeMs === cached.mtimeMs
      && current.size === cached.size
      && current.ino === cached.ino
    ) {
      return cached.data;
    }
  } catch {
    // The normal read path below logs and degrades to null if the asset disappeared or is odd.
  }
  cache.delete(key);
  return null;
}

export function writeToCache(cache: AssetCache, key: string, asset: AssetJson): void {
  if (cache.size >= CACHE_MAX) {
    const oldest = [...cache.entries()].sort((a, b) => a[1].ts - b[1].ts)[0];
    if (oldest) cache.delete(oldest[0]);
  }
  cache.set(key, { ...asset, ts: Date.now() });
}

export async function readAssetJson(
  jobId: string,
  assetType: AssetType,
  logLabel: string,
  cache: AssetCache,
  checkFileFreshness = true,
): Promise<AssetReadResult> {
  const asset = await getJobAsset(jobId, assetType);
  if (!asset) return { status: 'missing' };

  let resolvedPath: string;
  try {
    resolvedPath = resolveAssetPath(asset.filePath);
  } catch (err) {
    console.error(`[assetService] ${logLabel} path rejected: ${(err as Error).message} (filePath=${asset.filePath})`);
    return { status: 'missing' };
  }

  const allowedRoot = getAllowedAssetRoot();
  if (resolvedPath !== allowedRoot && !resolvedPath.startsWith(allowedRoot + path.sep)) {
    console.error(`[assetService] ${logLabel} path traversal attempt: ${resolvedPath}`);
    return { status: 'missing' };
  }
  if (!existsSync(resolvedPath)) return { status: 'missing' };

  const expectedSha256 = asset.commercialCopySha256 ?? null;
  if (
    needsCommercialCopyFence(assetType)
    && (
      !PUBLISHABLE_COMMERCIAL_COPY_STATUSES.has(asset.commercialCopyStatus)
      || !expectedSha256
      || !/^[a-f0-9]{64}$/.test(expectedSha256)
    )
  ) {
    const reason = !PUBLISHABLE_COMMERCIAL_COPY_STATUSES.has(asset.commercialCopyStatus)
      ? `status ${String(asset.commercialCopyStatus ?? 'UNKNOWN')} is not publishable`
      : 'registered content hash is missing or invalid';
    console.error(
      `[assetService] ${logLabel} blocked by commercial-copy fence `
      + `(status=${asset.commercialCopyStatus}, jobId=${jobId})`,
    );
    cache.delete(jobId);
    return { status: 'publication_blocked', reason };
  }

  const cached = await readFromCache(
    cache, jobId, resolvedPath, expectedSha256, checkFileFreshness,
  );
  if (cached !== null) {
    return { status: 'ready', asset: {
      data: cached,
      filePath: resolvedPath,
      mtimeMs: 0,
      size: 0,
      ino: 0,
      sha256: expectedSha256 ?? '',
    } };
  }

  try {
    const raw = await readFile(resolvedPath);
    const fileStat = await stat(resolvedPath);
    const sha256 = createHash('sha256').update(raw).digest('hex');
    if (expectedSha256 && sha256 !== expectedSha256) {
      console.error(`[assetService] ${logLabel} blocked: registered content hash is stale (jobId=${jobId})`);
      cache.delete(jobId);
      return { status: 'publication_blocked', reason: 'registered content hash is stale' };
    }
    return { status: 'ready', asset: {
      data: JSON.parse(raw.toString('utf8')),
      filePath: resolvedPath,
      mtimeMs: fileStat.mtimeMs,
      size: fileStat.size,
      ino: fileStat.ino,
      sha256,
    } };
  } catch (err) {
    console.error(`[assetService] ${logLabel} could not be read: ${(err as Error).message} (filePath=${asset.filePath})`);
    return { status: 'missing' };
  }
}
