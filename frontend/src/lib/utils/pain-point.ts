export interface NormalizedPainPoint {
  title: string;
  severity: number;
}

/**
 * Normalizes the string-or-object duality in discoveryFindings.painPoints.
 * Pain points may come as plain strings or as { title, severity } objects.
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
    };
  }
  return { title: String(point), severity: 0.5 };
}
