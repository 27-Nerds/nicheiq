import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { AssetType } from '@prisma/client';
import { resolveAssetPath } from '../utils/assetPath.js';

export const COMMERCIAL_COPY_CONTRACT_VERSION = 'paying-wallet-positive-copy-v1';
export const PUBLISHABLE_COMMERCIAL_COPY_STATUSES = new Set([
  'RECONCILED',
  'NOT_APPLICABLE',
  'GENERATED_CONTRACT',
]);

export function needsCommercialCopyFence(assetType: AssetType): boolean {
  return assetType === AssetType.PREVIEW_REPORT || assetType === AssetType.REPORT_JSON;
}

export async function hashRegisteredAsset(filePath: string): Promise<{ sha256: string; size: number }> {
  const raw = await readFile(resolveAssetPath(filePath));
  JSON.parse(raw.toString('utf8'));
  return { sha256: createHash('sha256').update(raw).digest('hex'), size: raw.length };
}
