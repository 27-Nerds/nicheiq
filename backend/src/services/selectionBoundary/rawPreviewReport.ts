import { AssetType } from '@prisma/client';
import {
  previewReportCache,
  readAssetJson,
  writeToCache,
} from './privateAssetReader.js';

/**
 * Raw run artifact access. Production imports are restricted to the selection
 * context verifier and a closed legacy allowlist by the architecture gate.
 */
export async function getPreviewReportForJob(jobId: string): Promise<unknown | null> {
  const asset = await readAssetJson(
    jobId, AssetType.PREVIEW_REPORT, 'Preview report', previewReportCache,
  );
  if (asset.status !== 'ready') return null;
  if (asset.asset.mtimeMs === 0) return asset.asset.data;
  writeToCache(previewReportCache, jobId, asset.asset);
  return asset.asset.data;
}
