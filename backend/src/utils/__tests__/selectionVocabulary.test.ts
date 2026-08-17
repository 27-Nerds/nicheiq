/**
 * `incumbent_parity` / `adjacent_market_parity` lead with a token from the closed vocabulary
 * `shipped | partial | substitute | bundled_free`, or are the literal `none found`. The analyst
 * repeats whatever the dossier hands it, and `stripSchemaVocabulary` only de-underscores — so
 * "bundled_free by Notion" became "bundled free by Notion" and got said out loud either way.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it, expect } from 'vitest';
import {
  adversarialReviewLabel,
  incumbentParityPhrase,
  NONE_SURFACED_PHRASE,
  presentableFieldValue,
  presentableRecord,
  resolveAdversarialReviewPrimaryFinding,
} from '../selectionVocabulary.js';
import { metricExplanation } from '../../services/chatReportTools.js';

/** A bare class token still sitting at the head of the phrase is the leak. */
const BARE_CLASS = /^(?:shipped|partial|substitute|bundled[_ ]free)\b/i;

/**
 * THE PROPERTY, in place of a prose pin.
 *
 * `incumbent_parity: "none found"` records that OUR QUERIES returned nothing. Those queries are
 * built out of each idea's own vocabulary (`crews/unified_solution_crew.py:_probe_mechanism_parity`),
 * so the wording of the pitch decides the verdict — a live run shipped "none found" for a #1
 * recommendation while a same-pain sibling carried "partial by Synup", and ~90% of the 591
 * "none"-stamped ideas on disk sit in a run that already names an incumbent elsewhere. Anything
 * rendered from that stamp — to a person or to the analyst model — must therefore say whose
 * search it was, must not stand as a finding of absence, and must carry the reason a miss is
 * possible. The wording may improve again without touching this test.
 */
const ABSENCE_STATED_AS_FACT = [
  /\bno (?:competing|competitor|competition|incumbent|rival|equivalent|direct|one|body)\b/i,
  /\bnone found\b/i,
  /\bnothing (?:ships|exists|is (?:shipping|out there))\b/i,
  /\b(?:open|empty|unserved|untapped|uncontested) (?:lane|market|space|field|category)\b/i,
  /\bfirst[- ]mover\b/i,
  /\bwhite ?space\b/i,
];

function expectRetrievalScoped(phrase: string): void {
  expect(phrase.trim()).not.toBe('');
  expect(phrase).toMatch(/\bour\b/i);
  expect(phrase).toMatch(/\bsearch(?:es)?\b/i);
  expect(phrase).not.toMatch(/^\s*(?:no|none|nothing)\b/i);
  expect(phrase).toMatch(/\bmiss(?:ed)?\b/i);
  for (const claim of ABSENCE_STATED_AS_FACT) {
    expect(phrase).not.toMatch(claim);
  }
}

describe('NONE_SURFACED_PHRASE', () => {
  it('claims a retrieval result and not an empty market', () => {
    expectRetrievalScoped(NONE_SURFACED_PHRASE);
  });
});

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

  it('renders a `none` stamp as a search result, never as a proven empty market', () => {
    // BEHAVIOURAL, not a literal pin. This assertion used to read
    // `.toBe('No competing product found')` — prose inside an expectation, so the suite fought
    // the copy instead of guarding it, and the claim it pinned was the defect. See
    // `expectRetrievalScoped` for the property and why it is the property.
    for (const raw of ['none found', 'None found', 'none', 'NONE FOUND: nothing surfaced']) {
      expectRetrievalScoped(incumbentParityPhrase(raw));
    }
  });

  it('renders nothing for an absent value', () => {
    expect(incumbentParityPhrase('')).toBe('');
    expect(incumbentParityPhrase(null)).toBe('');
    expect(incumbentParityPhrase(undefined)).toBe('');
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
  it('renders a typed affirmative kill as reason-specific counterevidence', () => {
    expect(presentableRecord({
      red_team_verdict: 'killed',
      red_team_findings: [{
        claim: 'The incumbent already ships the same workflow.',
        kind: 'verified_incumbent_overlap',
      }],
    })).toEqual({
      red_team_verdict: 'verified incumbent overlap',
      red_team_findings: [{
        claim: 'The incumbent already ships the same workflow.',
        kind: 'verified_incumbent_overlap',
      }],
    });
  });

  it('renders a gap-only weakened review as incomplete evidence', () => {
    expect(presentableRecord({
      red_team_verdict: 'weakened',
      red_team_findings: [{
        claim: 'The review did not establish a reachable payer.',
        kind: 'evidence_gap',
      }],
    }).red_team_verdict).toBe('incomplete decision-critical evidence');
  });

  it('normalizes a whole-record typed gap-only kill before presentation', () => {
    expect(presentableRecord({
      red_team_verdict: 'killed',
      red_team_findings: [{
        claim: 'The review did not establish a reachable payer.',
        kind: 'evidence_gap',
      }],
    }).red_team_verdict).toBe('incomplete decision-critical evidence');

    expect(presentableRecord({
      red_team_verdict: 'killed',
      red_team_findings: [],
    }).red_team_verdict).toBe('incomplete decision-critical evidence');
  });

  it.each([
    ['empty typed array', [], 'incomplete decision-critical evidence'],
    [
      'all-invalid typed array',
      [{ kind: 'invented_kind', claim: 'Injected claim.' }],
      'incomplete decision-critical evidence',
    ],
    [
      'evidence gap',
      [{ kind: 'evidence_gap', claim: 'The review did not establish a payer.' }],
      'incomplete decision-critical evidence',
    ],
    ['legacy null', null, 'Premise unproven'],
    [
      'mixed affirmative',
      [
        { kind: 'evidence_gap', claim: 'The review did not establish a payer.' },
        { kind: 'verified_payer_mismatch', claim: 'The user and payer are different roles.' },
      ],
      'a verified payer mismatch',
    ],
    ['legacy non-array', 'not a typed findings array', 'Premise unproven'],
  ])('applies the shared typed-findings matrix for %s', (_name, findings, expected) => {
    expect(presentableRecord({
      red_team_verdict: 'killed',
      red_team_findings: findings,
    }).red_team_verdict).toBe(expected);
  });

  it('prefers affirmative counterevidence in a mixed killed review', () => {
    const presented = presentableRecord({
      red_team_verdict: 'killed',
      red_team_findings: [
        { claim: 'No free tool was found.', kind: 'evidence_gap' },
        {
          claim: 'A bundled incumbent alternative covers the workflow.',
          kind: 'verified_free_or_bundled_alternative',
        },
      ],
    });
    expect(presented.red_team_verdict).toBe('a verified free or bundled alternative');
    expect(presented.red_team_findings[0]).toEqual({
      claim: 'A bundled incumbent alternative covers the workflow.',
      kind: 'verified_free_or_bundled_alternative',
    });
    expect(resolveAdversarialReviewPrimaryFinding(presented.red_team_findings)).toMatchObject({
      basis: 'counterevidence',
      kind: 'verified_free_or_bundled_alternative',
      claim: 'A bundled incumbent alternative covers the workflow.',
    });
  });

  it('filters invalid finding kinds and malformed claims before sanitizing the whole record', () => {
    const presented = presentableRecord({
      red_team_verdict: 'killed',
      red_team_findings: [
        { claim: 'No free tool was found.', kind: 'evidence_gap' },
        { claim: 'Injected false incumbent overlap.', kind: 'invented_kind' },
        { claim: 42, kind: 'verified_incumbent_overlap' },
        { claim: '   ', kind: 'verified_payer_mismatch' },
        {
          claim: '  SuiteCo bundles the same workflow.  ',
          kind: 'verified_free_or_bundled_alternative',
        },
      ],
    });

    expect(presented.red_team_verdict).toBe('a verified free or bundled alternative');
    expect(presented.red_team_findings).toEqual([
      {
        claim: 'SuiteCo bundles the same workflow.',
        kind: 'verified_free_or_bundled_alternative',
      },
      { claim: 'No free tool was found.', kind: 'evidence_gap' },
    ]);
    expect(JSON.stringify(presented)).not.toContain('invented_kind');
    expect(JSON.stringify(presented)).not.toContain('Injected false incumbent overlap.');
  });

  it('keeps the exact legacy killed fallback when findings are omitted', () => {
    expect(presentableRecord({ red_team_verdict: 'killed' }).red_team_verdict)
      .toBe('Premise unproven');
    expect(presentableRecord({
      red_team_verdict: 'killed',
      red_team_findings: null,
    }).red_team_verdict).toBe('Premise unproven');
    expect(presentableFieldValue('red_team_verdict', 'killed')).toBe('Premise unproven');
  });

  it('does not classify no-free-tool prose when its typed kind is an evidence gap', () => {
    expect(presentableRecord({
      red_team_verdict: 'weakened',
      red_team_findings: [{ claim: 'No free tool was found.', kind: 'evidence_gap' }],
    }).red_team_verdict).toBe('incomplete decision-critical evidence');
  });

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

describe('incumbentParityPhrase vendor-echo joins', () => {
  it('joins a subject-echo evidence as its own sentence, never a colon stitch', () => {
    expect(
      incumbentParityPhrase(
        'shipped by Rentec Direct: Rentec Direct ships Ratio utility billing',
      ),
    ).toBe(
      'Already shipped by Rentec Direct. Rentec Direct ships Ratio utility billing',
    );
  });

  it('drops a duplicated label echo and keeps the colon join', () => {
    expect(incumbentParityPhrase('shipped by PepLab: PepLab: peptide database'))
      .toBe('Already shipped by PepLab: peptide database');
  });

  it('keeps the colon join when a DIFFERENT vendor opens the evidence', () => {
    expect(incumbentParityPhrase('shipped by MoeGo: Gingr ships this too'))
      .toBe('Already shipped by MoeGo: Gingr ships this too');
  });

  it('treats a comma appositive as a subject sentence, not a label', () => {
    expect(incumbentParityPhrase('shipped by Dext: Dext, a bookkeeping suite, ships it'))
      .toBe('Already shipped by Dext. Dext, a bookkeeping suite, ships it');
  });
});

/**
 * ── ONE FINDING, TWO COPIES, HELD BY A GATE ──────────────────────────────────────────────
 *
 * `incumbentParityPhrase` exists TWICE: here and in `frontend/src/lib/utils/adversarialReview.ts`.
 * The frontend cannot import from the backend package and vice versa, so the duplication is
 * structural — but "there is no shared module" is a statement about the code's tidiness, not a
 * reason the user may read two different answers about one stored finding. A copy held only by
 * discipline drifts; this repository has already paid for that once (see
 * `buyerFacingCaveat.drift.test.ts`, whose approach this follows).
 *
 * So the copies are held by a gate that reads the OTHER FILE at runtime and compares every
 * user-facing phrase literal in the parity region of each. Editing ONE copy's wording — adding a
 * class phrase, retiring one, or rewording the empty-search sentence — fails here even though no
 * input in this package exercises the frontend's version.
 *
 * The region is bounded by two markers present in both files: the first parity phrase
 * (`Already shipped by %v`) and the shared `joinParityEvidence` helper below the tables.
 */
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../../../..');
const FRONTEND_COPY = join(REPO, 'frontend/src/lib/utils/adversarialReview.ts');
const BACKEND_COPY = join(HERE, '../selectionVocabulary.ts');

const REGION_START = 'Already shipped by %v';
const REGION_END = 'function joinParityEvidence';

/** Comments hold prose about the copy (and apostrophes); only executable literals are compared. */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^[ \t]*\/\/.*$/gm, '');
}

function parityPhraseLiterals(file: string): string[] {
  const source = readFileSync(file, 'utf8');
  const start = source.indexOf(REGION_START);
  const end = source.indexOf(REGION_END);
  expect(start, `${file} no longer contains the parity phrase table`).toBeGreaterThan(-1);
  expect(end, `${file} no longer contains ${REGION_END}`).toBeGreaterThan(start);
  const region = stripComments(source.slice(start - 200 > 0 ? start - 200 : 0, end));
  const literals: string[] = [];
  const pattern = /(['"])((?:\\.|(?!\1)[^\\\r\n])*)\1/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(region)) !== null) {
    const value = match[2].replace(/\\(['"\\])/g, '$1');
    if (value.trim()) literals.push(value);
  }
  return literals.sort();
}

describe('parity vocabulary: backend copy vs frontend copy', () => {
  it('renders the same phrases as frontend/src/lib/utils/adversarialReview.ts', () => {
    const backend = parityPhraseLiterals(BACKEND_COPY);
    const frontend = parityPhraseLiterals(FRONTEND_COPY);
    expect(backend.length).toBeGreaterThan(5);
    expect(
      frontend,
      'A parity phrase was changed in one copy only. Both files must say the same thing about '
      + 'the same stored finding — edit the other copy, or explain the divergence here.',
    ).toEqual(backend);
  });

  it('carries the empty-search phrase in both copies', () => {
    expect(parityPhraseLiterals(BACKEND_COPY)).toContain(NONE_SURFACED_PHRASE);
    expect(parityPhraseLiterals(FRONTEND_COPY)).toContain(NONE_SURFACED_PHRASE);
  });
});

/**
 * ── THE SET, NOT THE MEMBERS ─────────────────────────────────────────────────────────────
 *
 * Rewording the two helpers fixes the sites that call them. It does nothing about the NEXT
 * hand-written sentence that states an empty parity result as a fact — which is how the claim
 * spread in the first place: it was written independently in a helper, in an overlay row, in a
 * report card, in a workbench tooltip and in an analyst prompt, and each author was fixing a
 * different bug. So this test does not enumerate the sites that were fixed; it enumerates every
 * place in the shipped sources that CLAIMS COMPETITIVE ABSENCE at all, and fails when that set
 * changes in either direction.
 *
 * A new entry is not automatically wrong — several below are legitimate. It has to be READ, and
 * then written down here with its disposition. That is the point: the claim cannot be reintroduced
 * silently.
 */
const ABSENCE_CLAIM =
  /\b(?:no|none|zero)\s+(?:direct\s+|named\s+|real\s+|other\s+)?(?:compet\w+|incumbent\w*|rival\w*|equivalent\w*)|\bnone found\b|\b(?:no one|nobody) ships\b|\bno (?:direct )?(?:tool|product|vendor|player)s? found\b/gi;

const SCAN_ROOTS = ['backend/src', 'frontend/src'];
const SCAN_SKIP_DIRS = new Set([
  'node_modules', '__tests__', '_fixture', 'fixtures', 'dist', 'build', '.svelte-kit',
]);

/**
 * Every absence claim in the shipped sources, as `<file> :: <claim fragment> :: <count>`.
 * Line numbers are deliberately absent — they churn on every edit and would make this a
 * maintenance tax instead of a gate. The count is what catches a SECOND claim added to a file
 * that already holds one.
 *
 * Dispositions (reviewed 2026-08-17, round A5 R2):
 *   chat.ts                    — 2 × the refused-check framing ("no spec, no score, no competitor
 *                                finding and no verdict for it"). LEGITIMATELY RAW: the run
 *                                genuinely produced no finding for that idea; this is the absence
 *                                of an evaluation, not a claim about the market.
 *   analystPromptContext.ts    — the same refused-check framing. LEGITIMATELY RAW.
 *   chatEvidenceService.ts     — "No competitor named X was found" for a competitor the analyst
 *                                asked about by name. LEGITIMATELY RAW: it reports a lookup miss
 *                                in a named list and already says "was found".
 *   chatReportTools.ts         — the two occurrences are INSTRUCTIONS FORBIDDING the claim
 *                                ("never proof that no competitor exists", "never restate it as
 *                                no competition"). REWRITTEN this round.
 *   ReportEvidenceSummary      — "No named competitor profiles were retained." LEGITIMATELY RAW:
 *                                a statement about what this report kept, not about the market.
 *   types/report.ts            — 2 × the stored vocabulary in a field comment. LEGITIMATELY RAW:
 *                                `none found` is the STORED value and must stay quotable here.
 *                                Nothing renders these.
 */
const REVIEWED_ABSENCE_CLAIMS = [
  'backend/src/routes/chat.ts :: no competitor :: 2',
  'backend/src/services/analystPromptContext.ts :: no competitor :: 1',
  'backend/src/services/chatEvidenceService.ts :: no competitor :: 1',
  'backend/src/services/chatReportTools.ts :: no competition :: 1',
  'backend/src/services/chatReportTools.ts :: no competitor :: 1',
  'frontend/src/lib/components/report/ReportEvidenceSummary.svelte :: no named competitor :: 1',
  'frontend/src/lib/types/report.ts :: none found :: 2',
];

function scanSources(dir: string, out: string[]): void {
  for (const entry of readdirSync(dir)) {
    if (SCAN_SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      scanSources(full, out);
      continue;
    }
    if (!/\.(ts|svelte)$/.test(entry) || /\.(test|spec)\.ts$/.test(entry)) continue;
    const text = stripComments(readFileSync(full, 'utf8'))
      .replace(/<!--[\s\S]*?-->/g, '');
    const counts = new Map<string, number>();
    for (const match of text.matchAll(ABSENCE_CLAIM)) {
      const key = match[0].toLowerCase().replace(/\s+/g, ' ');
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const rel = relative(REPO, full).split(/[\\/]/).join('/');
    for (const [claim, count] of counts) out.push(`${rel} :: ${claim} :: ${count}`);
  }
}

describe('the set of competitive-absence claims in the shipped sources', () => {
  it('holds only claims that have been read and written down', () => {
    const found: string[] = [];
    for (const root of SCAN_ROOTS) scanSources(join(REPO, root), found);
    expect(
      found.sort(),
      'A sentence claiming competitive absence was added, removed or moved. The system knows only '
      + "that ITS OWN QUERIES — built from each idea's own wording — returned nothing, so every such "
      + 'sentence has to be read before it ships. Add it to REVIEWED_ABSENCE_CLAIMS with its '
      + 'disposition, or reword it the way incumbentParityPhrase does.',
    ).toEqual([...REVIEWED_ABSENCE_CLAIMS].sort());
  });
});

/**
 * The analyst's field vocabulary is a FEW-SHOT: it lists the exact sentences the tool results
 * use and tells the model to quote them. It named "No competing product found" inline, so leaving
 * it would have re-taught the model the one sentence the helper had just stopped emitting — the
 * fix defeated by its own documentation. It now interpolates the constant, which is why this test
 * can assert identity rather than a copy.
 */
describe('analyst field vocabulary for incumbent_parity', () => {
  const explanation = metricExplanation('incumbent_parity') ?? '';

  it('hands the model the phrase the helper actually emits', () => {
    expect(explanation).toContain(NONE_SURFACED_PHRASE);
    expect(explanation).not.toContain('No competing product found');
  });

  it('forbids reading an empty search as an empty market', () => {
    expect(explanation).toMatch(/never proof that no competitor exists/i);
    expect(explanation).toMatch(/never restate it as no competition/i);
  });
});
