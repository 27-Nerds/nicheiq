import { describe, it, expect } from 'vitest';
import { getPhaseContext } from '../phaseContext.js';

describe('getPhaseContext', () => {
  it('returns generic fallback when stage is null', () => {
    const ctx = getPhaseContext(null);
    expect(ctx.phaseLabel).toBe('During research');
    expect(ctx.guidance).toContain('try submitting');
  });

  it('returns generic fallback when stage is undefined', () => {
    const ctx = getPhaseContext(undefined);
    expect(ctx.phaseLabel).toBe('During research');
  });

  it('returns Discovery Phase for stage 1', () => {
    const ctx = getPhaseContext(1);
    expect(ctx.phaseLabel).toContain('Discovery Phase');
    expect(ctx.guidance).toContain('checkpointed');
  });

  it('returns Discovery Phase for stage 5', () => {
    const ctx = getPhaseContext(5);
    expect(ctx.phaseLabel).toContain('Discovery Phase');
  });

  it('returns Deep Research Phase for stage 5.5', () => {
    const ctx = getPhaseContext(5.5);
    expect(ctx.phaseLabel).toContain('Deep Research Phase');
    expect(ctx.guidance).toContain('checkpoint');
  });

  it('returns Deep Research Phase for stage 10', () => {
    const ctx = getPhaseContext(10);
    expect(ctx.phaseLabel).toContain('Deep Research Phase');
  });

  it('includes selected solution names in Deep Research label', () => {
    const ctx = getPhaseContext(8, ['SaaS Dashboard', 'Analytics Tool']);
    expect(ctx.phaseLabel).toContain('SaaS Dashboard');
    expect(ctx.phaseLabel).toContain('Analytics Tool');
  });

  it('omits solution names when selectedSolutions is empty', () => {
    const ctx = getPhaseContext(8, []);
    expect(ctx.phaseLabel).toBe('During Deep Research Phase');
  });

  it('omits solution names when selectedSolutions is null', () => {
    const ctx = getPhaseContext(8, null);
    expect(ctx.phaseLabel).toBe('During Deep Research Phase');
  });

  it('does not include solution names in Discovery Phase label', () => {
    const ctx = getPhaseContext(3, ['Some Solution']);
    expect(ctx.phaseLabel).not.toContain('Some Solution');
    expect(ctx.phaseLabel).toContain('Discovery Phase');
  });
});
