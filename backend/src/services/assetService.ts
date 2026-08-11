import { AssetType } from '@prisma/client';
import {
  discoveryCache,
  previewReportCache,
  readAssetJson,
  reportJsonCache,
  writeToCache,
} from './selectionBoundary/privateAssetReader.js';

export type ReportJsonPublicationResult =
  | { status: 'ready'; report: unknown }
  | { status: 'missing' }
  | { status: 'publication_blocked'; reason: string };

export async function getDiscoveryDataForJob(jobId: string): Promise<unknown | null> {
  const asset = await readAssetJson(
    jobId, AssetType.DISCOVERY_DATA, 'Discovery data', discoveryCache, false,
  );
  if (asset.status !== 'ready') return null;
  if (asset.asset.mtimeMs === 0) return asset.asset.data;
  writeToCache(discoveryCache, jobId, asset.asset);
  return asset.asset.data;
}

export async function getReportJsonForJob(jobId: string): Promise<unknown | null> {
  const result = await getReportJsonPublicationForJob(jobId);
  return result.status === 'ready' ? result.report : null;
}

export async function getReportJsonPublicationForJob(
  jobId: string,
): Promise<ReportJsonPublicationResult> {
  const asset = await readAssetJson(
    jobId, AssetType.REPORT_JSON, 'Report JSON', reportJsonCache,
  );
  if (asset.status !== 'ready') return asset;
  if (asset.asset.mtimeMs !== 0) writeToCache(reportJsonCache, jobId, asset.asset);
  return { status: 'ready', report: asset.asset.data };
}

export function invalidateReportJsonCache(jobId: string): void {
  reportJsonCache.delete(jobId);
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
