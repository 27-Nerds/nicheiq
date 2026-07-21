import { describe, expect, it } from 'vitest';
import {
  buildReportExport,
  getReportPath,
  metricExplanation,
  searchReportEvidence,
} from '../chatReportTools.js';

const report = {
  Executive_Dashboard: {
    market_verdict: 'Conditional go',
  },
  alternative_solutions: [
    { solution_name: 'Signal Desk', score: 72 },
  ],
};

describe('chat report tools', () => {
  it('resolves dotted report paths case-insensitively without fuzzy key matching', () => {
    expect(getReportPath(report, 'executive_dashboard.MARKET_VERDICT')).toBe('Conditional go');
    expect(getReportPath(report, 'executive.market_verdict')).toBeUndefined();
  });

  it('keeps report search bounded and preserves exact evidence paths', () => {
    expect(searchReportEvidence(report, 'conditional')).toEqual([
      { path: 'report.Executive_Dashboard.market_verdict', value: 'Conditional go' },
    ]);
  });

  it('renders the established export and metric-definition formats', () => {
    expect(buildReportExport(report, ['Executive_Dashboard'], 'csv')).toBe(
      '"section","market_verdict"\n"Executive_Dashboard","Conditional go"',
    );
    expect(metricExplanation('adjusted composite score')).toContain(
      '70% composite score plus 30% keyword demand score',
    );
    expect(metricExplanation('invented score')).toBeNull();
  });
});
