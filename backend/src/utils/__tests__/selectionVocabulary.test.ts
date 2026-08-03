/**
 * `incumbent_parity` / `adjacent_market_parity` lead with a token from the closed vocabulary
 * `shipped | partial | substitute | bundled_free`, or are the literal `none found`. The analyst
 * repeats whatever the dossier hands it, and `stripSchemaVocabulary` only de-underscores — so
 * "bundled_free by Notion" became "bundled free by Notion" and got said out loud either way.
 */
import { describe, it, expect } from 'vitest';
import {
  adversarialReviewLabel,
  incumbentParityPhrase,
  presentableFieldValue,
  presentableRecord,
} from '../selectionVocabulary.js';

/** A bare class token still sitting at the head of the phrase is the leak. */
const BARE_CLASS = /^(?:shipped|partial|substitute|bundled[_ ]free)\b/i;

describe('incumbentParityPhrase', () => {
  it('labels the `<class> by <vendor>` shape', () => {
    expect(incumbentParityPhrase('shipped by Aftershoot: culls RAW batches'))
      .toBe('Already shipped by Aftershoot: culls RAW batches');
    expect(incumbentParityPhrase('partial by Karbon: workflow automation'))
      .toBe('Partly covered by Karbon: workflow automation');
  });

  it('labels the `<class> (<vendor>)` shape', () => {
    expect(incumbentParityPhrase('substitute (Forrager): free templates cover it'))
      .toBe('Buyers already get this outcome from Forrager: free templates cover it');
    expect(incumbentParityPhrase('bundled_free (Notion): included in the free tier'))
      .toBe('Already included free with Notion: included in the free tier');
  });

  it('handles a finding with no evidence clause', () => {
    expect(incumbentParityPhrase('substitute (free spreadsheet templates)'))
      .toBe('Buyers already get this outcome from free spreadsheet templates');
    expect(incumbentParityPhrase('partial by free petition and spreadsheet workflows'))
      .toBe('Partly covered by free petition and spreadsheet workflows');
  });

  it('names no product for a red-team / evidence finding, which is a CLASS not a vendor', () => {
    // Mirrors the frontend, which suppresses these from its "Incumbent: <name>" chip
    // (SelectionWorkbench.svelte incumbentName + the `(red-team)` guard).
    const evidence = incumbentParityPhrase('shipped by evidence: the data source misses the buyer');
    expect(evidence).toBe(
      'This is already shipped elsewhere (an alternative class, no product named): '
      + 'the data source misses the buyer',
    );

    const redTeam = incumbentParityPhrase('bundled_free (red-team): a free route already covers it');
    expect(redTeam).toContain('no product named');
    expect(redTeam).toContain('a free route already covers it');
    expect(redTeam).not.toContain('red-team');
  });

  it('states the empty finding in words', () => {
    expect(incumbentParityPhrase('none found')).toBe('No competing product found');
    expect(incumbentParityPhrase('')).toBe('');
    expect(incumbentParityPhrase(null)).toBe('');
  });

  it('leaves free prose that carries no class token untouched', () => {
    const prose = 'SpreadsheetCo covers the basics for free';
    expect(incumbentParityPhrase(prose)).toBe(prose);
  });

  it('never returns a phrase that still opens with a bare class token', () => {
    const stored = [
      'shipped by Aftershoot: culls RAW batches',
      'partial by Karbon: workflow automation',
      'substitute (Forrager): free templates cover it',
      'bundled_free (Notion): included in the free tier',
      'bundled_free (red-team): a free route already covers it',
      'shipped by evidence: the data source misses the buyer',
      'none found',
    ];
    for (const value of stored) {
      expect(incumbentParityPhrase(value)).not.toMatch(BARE_CLASS);
    }
  });
});

/**
 * The shared record sanitizer. Every analyst retrieval tool used to hand the model the raw
 * stored record; the model then quoted `red_team_verdict: "killed"` and
 * `incumbent_parity: "partial by Opendate: …"` straight onto a user's screen. Keys survive
 * (report paths stay quotable and nothing is dropped) — only the closed-vocabulary VALUES
 * are replaced with the words the product ships.
 */
describe('presentableRecord', () => {
  it.each(['killed', 'weakened', 'survives'])(
    'replaces the raw "%s" verdict while keeping the field',
    (verdict) => {
      const presented = presentableRecord({ solution_name: 'Sol', red_team_verdict: verdict });
      expect(presented).toHaveProperty('red_team_verdict');
      expect(JSON.stringify(presented)).not.toMatch(/\b(killed|weakened|survives)\b/i);
      expect(presented.solution_name).toBe('Sol');
    },
  );

  it('maps both parity fields and reaches nested records and arrays', () => {
    const presented = presentableRecord({
      candidates: [
        {
          incumbent_parity: 'partial by Opendate: covers the settlement step',
          adjacent_market_parity: 'bundled_free (Notion): included in the free tier',
          nested: { red_team_verdict: 'killed' },
        },
      ],
    });

    expect(presented).toEqual({
      candidates: [
        {
          incumbent_parity: 'Partly covered by Opendate: covers the settlement step',
          adjacent_market_parity: 'Already included free with Notion: included in the free tier',
          nested: { red_team_verdict: 'Premise unproven' },
        },
      ],
    });
  });

  it('leaves everything else — including free prose and non-strings — exactly as stored', () => {
    const stored = {
      description: 'A partial refund is shipped by default',
      incumbent_parity: 'SpreadsheetCo covers the basics for free',
      adjacent_market_parity: null,
      red_team_caveats: ['No reachable buyer was found.'],
      market_fit_score: 0.62,
    };
    expect(presentableRecord(stored)).toEqual(stored);
  });

  it('drops an unrecognised verdict rather than echoing it', () => {
    expect(presentableRecord({ red_team_verdict: 'obliterated' }))
      .toEqual({ red_team_verdict: null });
    expect(adversarialReviewLabel('obliterated')).toBeNull();
  });

  it('maps a detached leaf by its field name, for evidence-search results', () => {
    expect(presentableFieldValue('incumbent_parity', 'partial by Opendate: covers it'))
      .toBe('Partly covered by Opendate: covers it');
    expect(presentableFieldValue('alternative_solutions[0]', 'partial by Opendate'))
      .toBe('partial by Opendate');
    expect(presentableFieldValue('description', 'shipped by default')).toBe('shipped by default');
  });
});
