export interface NormalizedPainPoint {
  title: string;
  severity: number;
  wtp?: number;
  opportunity?: 'high' | 'medium' | 'low';
  mentions?: number;
  categories?: string[];
  platforms?: string[];
}

/**
 * Normalizes the string-or-object duality in discoveryFindings.painPoints.
 * Pain points may come as plain strings, { title, severity } objects,
 * or enriched PainPointSummary objects from the expanded stage 3 artifact.
 */
export function normalizePainPoint(point: unknown): NormalizedPainPoint {
  if (typeof point === 'string') {
    return { title: point, severity: 0.5 };
  }
  if (point && typeof point === 'object') {
    const p = point as Record<string, unknown>;
    return {
      title: String(p.title ?? p.name ?? ''),
      severity: typeof p.severity === 'number' ? p.severity : 0.5,
      wtp: typeof p.wtp === 'number' ? p.wtp : undefined,
      opportunity: (['high', 'medium', 'low'] as const).includes(p.opportunity as any)
        ? (p.opportunity as 'high' | 'medium' | 'low')
        : undefined,
      mentions: typeof p.mentions === 'number' ? p.mentions : undefined,
      categories: Array.isArray(p.categories) ? p.categories : undefined,
      platforms: Array.isArray(p.platforms) ? p.platforms : undefined,
    };
  }
  return { title: String(point), severity: 0.5 };
}
