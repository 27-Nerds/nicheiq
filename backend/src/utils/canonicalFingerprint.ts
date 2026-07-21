import { createHash } from 'node:crypto';

/** Preserve the canonical JSON algorithm used by persisted selection fingerprints. */
export function canonicalizeJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalizeJson);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, canonicalizeJson(child)]),
    );
  }
  return value;
}

export function canonicalJsonSha256(value: unknown): string {
  return createHash('sha256')
    .update(JSON.stringify(canonicalizeJson(value)) as string)
    .digest('hex');
}
