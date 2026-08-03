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

// The two answers the analyst gets WRONG by guessing: a tie in demand reads as "equally
// wanted", and a premise-unproven idea reads as "bad". Both are falsehoods now, so the
// glossary has to state the limit next to the formula.
describe('score glossary — the 2026-08 scoring changes', () => {
  it('scopes demand to the graded, on-idea keyword set and warns that ties carry no signal', () => {
    const demand = metricExplanation('keyword_demand_score')!;
    expect(demand).toContain('RELEVANCE-GRADED');
    expect(demand).toContain('len(validated_keywords)');
    expect(demand).toContain('never evidence that they are equally wanted');
    expect(metricExplanation('demand unmeasured')).toContain('NOT zero and not low');
    expect(metricExplanation('validated_count')).toContain('not the unfiltered expansion pool');
  });

  it('states the premise-unproven reading and never hands back the internal word', () => {
    const verdict = metricExplanation('red_team_verdict')!;
    expect(verdict).toContain('"Premise unproven"');
    expect(verdict).toContain('never say killed');
    expect(verdict).toContain('keeps its rank and stays selectable');
  });

  it('records the named-vendor competition bar and the ranking-only audience penalty', () => {
    expect(metricExplanation('incumbent_parity')).toContain('NAMED vendor');
    expect(metricExplanation('incumbent_parity')).toContain('no longer writes into this channel');
    expect(metricExplanation('audience_fit')).toContain('RANKING composite only');
    expect(metricExplanation('idea_theses')).toContain('ONE business');
  });
});
