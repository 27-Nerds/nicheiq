import { describe, it, expect } from 'vitest';
import { opportunityShape } from './solution-utils';
import type { SolutionPreview } from '$lib/types/job';

const idea = (winning_angle: string | null): SolutionPreview =>
  ({ solution_name: 'x', winning_angle } as unknown as SolutionPreview);

describe('opportunityShape', () => {
  it('returns null when fewer than 3 ideas are classified', () => {
    expect(opportunityShape([idea('distribution_seo'), idea('novel_differentiation')])).toBeNull();
    expect(opportunityShape([idea(null), idea(null), idea('novel_differentiation')])).toBeNull();
  });

  it('names a clear distribution lean with the count', () => {
    const r = opportunityShape([
      idea('distribution_seo'), idea('distribution_seo'), idea('distribution_seo'),
      idea('novel_differentiation'), idea('novel_differentiation'),
    ])!;
    expect(r.dominant).toBe('distribution_seo');
    expect(r.counts).toEqual({ distribution_seo: 3, novel_differentiation: 2 });
    expect(r.line).toContain('Distribution-leaning');
    expect(r.line).toContain('3 of 5');
  });

  it('calls a tie a mixed niche', () => {
    const r = opportunityShape([
      idea('distribution_seo'), idea('distribution_seo'),
      idea('novel_differentiation'), idea('novel_differentiation'),
      idea('vertical_workflow'), idea('vertical_workflow'),
    ])!;
    expect(r.line).toContain('Mixed niche');
  });

  it('ignores unclassified ideas in the count', () => {
    const r = opportunityShape([
      idea('novel_differentiation'), idea('novel_differentiation'), idea('novel_differentiation'),
      idea(null), idea(null),
    ])!;
    expect(r.counts).toEqual({ novel_differentiation: 3 });
    expect(r.line).toContain('Novelty-leaning');
    expect(r.line).toContain('3 of 3');
  });
});
