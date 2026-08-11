import { existsSync, mkdtempSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

import {
  buyerFacingCoverageNote,
  buyerFacingIdeaProse,
  buyerFacingResearchProse,
  buyerFacingVerdictHeadline,
  buyerFacingVerdictNarrative,
  humanizeInternalJargon,
} from '../buyerFacingCaveat.js';
import { buildSelectionChallengeEvidence } from '../../services/selectionChallengeEvidence.js';
import type { IdeaRecord } from '../ideaIdentity.js';

/**
 * THE ANTI-DRIFT GATE FOR THE BACKEND PORT.
 *
 * `utils/buyerFacingCaveat.ts` is a copy of two frontend modules, which stay the authority.
 * A copy that is only held in place by discipline drifts; this program has already paid for
 * two implementations of one rule diverging silently. So the copy is held by two checks that
 * read the OTHER SIDE at runtime:
 *
 *   1. SOURCE REGIONS (hard gate, no dependencies beyond the committed frontend sources).
 *      Every declaration the port copied is parsed out of the frontend file it came from and
 *      compared against the port's own declaration of the same name, whole-line comments
 *      stripped and whitespace collapsed. A rule ADDED, REMOVED, REORDERED or REWORDED on the
 *      frontend fails here even if no input in this repository exercises it — which is the
 *      case a behavioural test cannot cover.
 *
 *   2. BEHAVIOURAL DIFFERENTIAL (runs when the frontend module can be imported). The real
 *      `$lib/selection/buyerFacingResearchProse` is imported and its output compared with the
 *      port's, byte for byte, over the real corpus values below and over every
 *      `quality_caveats` / `user_adjustments` value under `output/` when that directory is
 *      present. It needs `frontend/node_modules` (the authority pulls in `marked` and
 *      `isomorphic-dompurify` at module scope), so it degrades to a loud warning rather than
 *      failing a backend-only checkout. Check 1 is the one that must never be skipped.
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../../../..');
const FORMAT_SOURCE = join(REPO, 'frontend/src/lib/utils/format.ts');
const PROSE_SOURCE = join(REPO, 'frontend/src/lib/selection/buyerFacingResearchProse.ts');
const PORT_SOURCE = join(HERE, '../buyerFacingCaveat.ts');
const OUTPUT_DIR = join(REPO, 'output');

/**
 * Every declaration the port copied, and the frontend file it was copied from. The list is
 * CLOSED on purpose: `sanitize`, `vocabularyRules` and `buyerFacingIdeaProse` are on it, so a
 * new rule table wired into any of them changes one of those bodies and fails check 1 even
 * though the new table itself has no counterpart here to compare.
 *
 * `buyerFacingNicheDifficultyVerdict`, `buyerFacingSolutionPreview` and `buyerFacingReport`
 * are deliberately absent: they walk a whole report or a whole idea object, and the backend
 * reaches its two fields one string at a time. `NON_PROSE_KEY` / `humanizeNode` /
 * `humanizeReportProse` are absent because they guard a field-blind deep walk the backend does
 * not perform — see the header of the module under test.
 *
 * `RESEARCH_CORPUS_GLOSS`, `RESEARCH_RULES`, `buyerFacingResearchProse`, `FIT_HEADLINE`,
 * `buyerFacingVerdictHeadline`, `VERDICT_NARRATIVE_RULES` and `buyerFacingVerdictNarrative`
 * WERE on that absent list until `caveatSources` started printing `niche_difficulty_verdict`
 * to the owner (finding D28). The last two are the reading `caveatSources` actually uses; the
 * evidence gloss is gated with them because the two readings live in one table and a frontend
 * edit to either must fail here.
 */
const PORTED_DECLARATIONS: Record<string, string> = {
  // frontend/src/lib/utils/format.ts
  MONEY_UNITS: FORMAT_SOURCE,
  MONEY_IN_TEXT: FORMAT_SOURCE,
  moneyAmount: FORMAT_SOURCE,
  moneyDigits: FORMAT_SOURCE,
  formatMoneyRange: FORMAT_SOURCE,
  matchCase: FORMAT_SOURCE,
  labelledIntentScale: FORMAT_SOURCE,
  commercialIntentPhrase: FORMAT_SOURCE,
  JargonReplacer: FORMAT_SOURCE,
  JargonRule: FORMAT_SOURCE,
  REPR_FIELD_LABELS: FORMAT_SOURCE,
  PAIN_REPR_TITLE: FORMAT_SOURCE,
  INTERNAL_JARGON_RULES: FORMAT_SOURCE,
  humanizeInternalJargon: FORMAT_SOURCE,
  // frontend/src/lib/selection/buyerFacingResearchProse.ts
  SEP: PROSE_SOURCE,
  sentenceRule: PROSE_SOURCE,
  SENTENCE_RULES: PROSE_SOURCE,
  CORPUS_COMPOUND_RULES: PROSE_SOURCE,
  RESEARCH_CORPUS_GLOSS: PROSE_SOURCE,
  IDEA_CORPUS_GLOSS: PROSE_SOURCE,
  VOCABULARY_TAIL_RULES: PROSE_SOURCE,
  vocabularyRules: PROSE_SOURCE,
  RESEARCH_RULES: PROSE_SOURCE,
  VERDICT_NARRATIVE_RULES: PROSE_SOURCE,
  sanitize: PROSE_SOURCE,
  buyerFacingResearchProse: PROSE_SOURCE,
  buyerFacingVerdictNarrative: PROSE_SOURCE,
  FIT_HEADLINE: PROSE_SOURCE,
  buyerFacingVerdictHeadline: PROSE_SOURCE,
  DATA_ROUTE_UNVERIFIED: PROSE_SOURCE,
  IDEA_WORD_RULES: PROSE_SOURCE,
  IDEA_RULES: PROSE_SOURCE,
  buyerFacingIdeaProse: PROSE_SOURCE,
  DATA_ACCESS_LABELS: PROSE_SOURCE,
  COVERAGE_NOTE: PROSE_SOURCE,
  coverageNoteStanza: PROSE_SOURCE,
  buyerFacingCoverageNote: PROSE_SOURCE,
  PRODUCT_NAME_SPAN: PROSE_SOURCE,
  VOCABULARY_WORD: PROSE_SOURCE,
  isVocabularyRun: PROSE_SOURCE,
  NAME_INTERNAL_GAP: PROSE_SOURCE,
  MASK_TOKEN: PROSE_SOURCE,
  maskProductNames: PROSE_SOURCE,
  restoreProductNames: PROSE_SOURCE,
  startsSentence: PROSE_SOURCE,
  applyWordRules: PROSE_SOURCE,
  normalizeClauseDashes: PROSE_SOURCE,
  bracketDepth: PROSE_SOURCE,
  SPACED_DASH: PROSE_SOURCE,
  SPACED_DASH_CLAUSE: PROSE_SOURCE,
  RELATIVE_PRONOUN: PROSE_SOURCE,
  PARTICIPLE_TAIL: PROSE_SOURCE,
  FINITE_BE: PROSE_SOURCE,
  RELATIVE_MARKER: PROSE_SOURCE,
  NOUN_TAIL: PROSE_SOURCE,
  isParticipialAdjunct: PROSE_SOURCE,
  breakLoneClauseDash: PROSE_SOURCE,
  sentenceCase: PROSE_SOURCE,
};

/** Top-level declaration texts of a TypeScript file, keyed by declared name. */
function declarations(file: string): Map<string, string> {
  const source = ts.createSourceFile(
    file,
    readFileSync(file, 'utf8'),
    ts.ScriptTarget.Latest,
    /* setParentNodes */ true,
  );
  const found = new Map<string, string>();
  for (const statement of source.statements) {
    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name)) found.set(declaration.name.text, statement.getText(source));
      }
      continue;
    }
    if (
      (ts.isFunctionDeclaration(statement) || ts.isTypeAliasDeclaration(statement))
      && statement.name
    ) {
      found.set(statement.name.text, statement.getText(source));
    }
  }
  return found;
}

/**
 * Comments carry the rationale, and the port keeps a shortened form of it — so they are the
 * one thing allowed to differ. Whole-line comments are dropped and whitespace collapsed;
 * everything else, string quoting and regex flags included, must match character for
 * character. Trailing same-line comments are NOT stripped (a `//` strip would have to know
 * whether it is inside a regex literal), so the port keeps those verbatim.
 */
function comparable(declaration: string): string {
  return declaration
    .split('\n')
    .filter((line) => {
      const trimmed = line.trim();
      return !(trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*'));
    })
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Real `data_quality_summary.quality_caveats` / `user_adjustments` values, copied verbatim
 * from runs under `output/`. `output/` is not committed, so these travel with the test; the
 * sweep below adds the rest of the corpus when the directory is there.
 *
 * They are chosen to reach every stanza the module owns AND every constraint it must not
 * break: the calibration sentence, both coverage-note shapes, the interpolated PainPoint repr
 * with a real user's words inside it, the severity-pain note with a TIGHT en-dash numeric
 * range, and the two `user_adjustments` values.
 */
const CORPUS: string[] = [
  'Calibration note for "AgencySeatTaxCalc" cites data route "Deterministic arithmetic on the user\'s own inputs" as market-fit support, but the route verifier did not confirm it (data_access_model: unverified). Treat the market-fit score as unverified on the data-route dimension.',
  'Core pain point \'title=\'Burnout and Mental Health Struggles\' severity_score=0.9 willingness_to_pay_score=0.6 representative_quote="I am burnt the F out. I had a bit of a breakdown 1.5 weeks ago, then another a few days after that, and another a few days after that. I haven\'t taken a full week off since I started the company in 2016." source_platform=\'Reddit r/gamedev\'\' (the #1 pain point by severity+WTP) is not in the selected solution\'s pain_points_addressed list. The recommended solution does not claim to address the top problem.',
  'Core pain point \'Manual invoicing and payment tracking consumes 3-5 hours per studio per week\' (the #1 pain point by severity+WTP) is not in the selected solution\'s pain_points_addressed list. The recommended solution does not claim to address the top problem.',
  'Idea-set coverage — validated pains with no idea: Severe adverse reactions like heart palpitations without emergency guidance; Weight loss stalls for months despite max GLP-1 dose, no clear next step; Risk of adverse interactions when stacking multiple peptides without clinical data; Difficulty sourcing all peptides for a stack from reliable vendors (+3 more). Concentration may reflect where the real opportunity is, not a defect — shown for your judgment.',
  'Idea-set coverage — validated pains with no idea: SMS interface takes 10 minutes to load after login. Concentration may reflect where the real opportunity is, not a defect — shown for your judgment.',
  'Suspiciously low volume filter ratio (0.1%): dashboard niche-relevant volume (1,490) vs seo_analytics total volume (1,908,170). Keyword filtering may be overly aggressive.',
  'Novelty/obviousness collapsed to exact complements this run — treat the two originality axes as one signal.',
  '“Cannot preserve channel-specific content when scheduling social posts” was prioritised for ideation as the closest match to your niche focus; research scored a related pain higher on severity (“Cannot route social content through legal, executive, client, and team review”, 0.58 vs 0.43).',
  "High-severity pain 'Morning espresso routine takes 15–20 minutes, causing delays to work' is not addressed by any generated solution.",
  'Gate 1 (niche context): niche details were adjusted before research began.',
  'Gate 2 (audience & pains): excluded 1 pain point(s) from ideation — Local bookings often signal party intent or boundary violations.',
];

/**
 * Real `niche_difficulty_verdict` values, copied verbatim from runs under `output/`. The
 * narrative is stored as the LLM wrote it, so this is where the research vocabulary actually
 * lives: 24 of the 28 distinct narratives under `output/` carry one of these words, with ZERO
 * clause dashes and ZERO internal tokens, because `_without_long_dashes` already ran on the
 * persisted path. A token-only metric reads this corpus perfectly clean.
 *
 * Chosen to reach the bare noun, the ARTICLE-PLUS-MODIFIER form ("requiring a new corpus"),
 * the article-adjacent form, the PLURAL LEMMA ("data corpora"), both cold-start spellings, the
 * bare wedge, and all three separator shapes the headline arrives with. The per-word counts
 * are corpus/corpora 21, cold-start 17, wedge 6, web-verified 0; 24 distinct narratives carry
 * at least one.
 */
const VERDICT_NARRATIVES: string[] = [
  'Software can directly own nearly all the workflow and data pains found in auto repair shops, but you must prioritize building a free tool with built-in distribution like lead-gen or sponsorship rather than a subscription product due to weak buying signals. The high difficulty stems from a saturated tool ecosystem where most obvious angles already ship, so your success depends on finding a sharper wedge rather than just feasibility. Focus your efforts on ideas that utilize existing reachable data rather than those requiring a new corpus, and consider usage-based pricing models since many shop tasks occur only episodically.',
  'Software can directly own the repetitive communication tasks and brand monitoring pains within this niche, though high difficulty persists due to cold-start risks and a dense existing tool ecosystem. Because buying signals are weak, you should build free tools with built-in distribution mechanisms like lead-gen or sponsorship rather than pursuing subscription pricing. Focus on solving the cold-start data problem early, as many concepts require a corpus that does not yet exist to be truly useful.',
  'You should build a solution that directly owns community management tasks, but you must tighten your wedge specifically for small SaaS operators to avoid serving the wrong user. While software can solve most of these pains, you face high difficulty due to a dense tool ecosystem and the need for a cold-start strategy to build a data corpus that does not yet exist. Buyers demonstrate strong willingness to pay, so focus on a subscription model that emphasizes convenience over existing DIY methods.',
  'Software can address 62% of pains for Dota 2 and CS2 fans, but with 62% only partially solvable, tools will advise and organize rather than fix root causes. The dominant idea shape is an aggregator, yet only 29% of ideas fit this category. Be aware that 100% of ideas require a data corpus that doesn\'t exist yet, and raw scores were corrected down from optimistic, suggesting obvious approaches are less promising.',
  // The two PLURAL narratives. Nothing in the module matched `corpora` before this round, so
  // both shipped the internal word verbatim to the owner.
  'You should build tools that directly own the administrative burden of scheduling and roster management, as software can solve about half of the core pains in this niche. While the fit is strong, the high difficulty stems from the need to overcome a significant cold-start risk, as many effective solutions require data corpora that do not currently exist. Because the niche features a dense ecosystem of existing tools, you must plan to compete for attention within an established stack rather than assuming a vacant market.',
  'Software can directly own most bookkeeping pains, but you should avoid traditional subscription models in favor of free tools with built-in distribution like lead-gen or sponsorship due to weak buying signals. The high difficulty stems from a saturated tool ecosystem and the need for a cold-start strategy to build data corpora that do not currently exist. Focus your development on a sharp wedge that competes directly against established incumbents rather than attempting to fill an empty market.',
  // The article-plus-modifier form the adjacency-bound rule fell through on.
  'Software can directly own about half of the technical and logistical pains in this niche, though you should focus on ideas that leverage existing user data rather than those requiring a new, unproven data corpus. While the software fit is strong, the difficulty is high because the tool ecosystem is already moderately saturated and you must compete head-on with established incumbents for attention. Given that willingness to pay is moderate and some ideas are used only episodically, prioritize models that target specific high-value pain points rather than relying on broad subscription tiers.',
];

const VERDICT_HEADLINES: string[] = [
  // The authored em dash.
  'Software Fit: Strong — automating dispatch and parts procurement for appliance repair fleets',
  'Software Fit: Limited — Hardware limitations mean software can only advise, not fix root causes',
  // What `_without_long_dashes` leaves on the paying-wallet path.
  'Software Fit: Moderate: the corpus is thinner than the wedge needs',
  // The tight dash the LLM can return.
  'Software Fit: Strong—automating inventory and controlled substance compliance',
  // No `Software Fit:` head at all: the whole string goes through the research prose instead.
  'Cold-start data corpus required before the wedge is usable',
];

/**
 * Every distinct value of the caveat fields and of `niche_difficulty_verdict` under `output/`,
 * when the runs are present — a few thousand JSON artifacts, so the sweep is done once and
 * shared by every test below.
 */
type OutputCorpus = { caveats: string[]; verdicts: string[] };
let outputCorpusCache: OutputCorpus | null = null;
function outputCorpus(): string[] {
  return (outputCorpusCache ??= sweepOutputCorpus()).caveats;
}
function outputVerdictCorpus(): string[] {
  return (outputCorpusCache ??= sweepOutputCorpus()).verdicts;
}

function sweepOutputCorpus(): OutputCorpus {
  if (!existsSync(OUTPUT_DIR)) return { caveats: [], verdicts: [] };
  const values = new Set<string>();
  const verdicts = new Set<string>();
  const visit = (node: unknown): void => {
    if (Array.isArray(node)) {
      for (const child of node) visit(child);
      return;
    }
    if (!node || typeof node !== 'object') return;
    for (const [key, value] of Object.entries(node)) {
      if ((key === 'quality_caveats' || key === 'user_adjustments') && Array.isArray(value)) {
        for (const entry of value) if (typeof entry === 'string' && entry.trim()) values.add(entry);
      }
      // The two fields `caveatSources` reads: the excerpt is `narrative_summary ?? headline`
      // and the title is the headline, so both reach the owner.
      if (key === 'niche_difficulty_verdict' && value && typeof value === 'object' && !Array.isArray(value)) {
        for (const field of ['narrative_summary', 'headline']) {
          const entry = (value as Record<string, unknown>)[field];
          if (typeof entry === 'string' && entry.trim()) verdicts.add(entry);
        }
      }
      visit(value);
    }
  };
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      let stats;
      try { stats = statSync(path); } catch { continue; }
      if (stats.isDirectory()) walk(path);
      else if (entry.endsWith('.json')) {
        try { visit(JSON.parse(readFileSync(path, 'utf8'))); } catch { /* not a run artifact */ }
      }
    }
  };
  walk(OUTPUT_DIR);
  return { caveats: [...values], verdicts: [...verdicts] };
}

/** Every verdict string the two surfaces can hand the port. */
function verdictCorpus(): string[] {
  return [...new Set([...VERDICT_NARRATIVES, ...VERDICT_HEADLINES, ...outputVerdictCorpus()])];
}

type FrontendVerdict = {
  headline: string;
  narrative_summary: string;
  key_challenges: string[];
};

type FrontendAuthority = {
  buyerFacingCoverageNote: (value: string | null | undefined) => string;
  buyerFacingNicheDifficultyVerdict: (verdict: unknown) => FrontendVerdict;
  buyerFacingResearchProse: (value: string) => string;
  buyerFacingVerdictHeadline: (value: string) => string;
  buyerFacingVerdictNarrative: (value: string) => string;
};

/**
 * The frontend module, imported through vitest's `$lib` alias. The specifier is held in a
 * variable so `tsc` treats it as `any` — the backend program has no `$lib` path and must not
 * grow one, because the API compiles and ships without the frontend sources.
 */
const AUTHORITY_SPECIFIER = '$lib/selection/buyerFacingResearchProse';

async function loadAuthority(): Promise<FrontendAuthority | null> {
  try {
    return await import(/* @vite-ignore */ AUTHORITY_SPECIFIER) as FrontendAuthority;
  } catch (error) {
    console.warn(
      `[buyerFacingCaveat.drift] Behavioural differential skipped — could not import ${AUTHORITY_SPECIFIER}. `
      + 'Run `npm --prefix frontend ci` to enable it. The source-region check below still runs.\n',
      error,
    );
    return null;
  }
}

type SourceGateResult = { missingHere: string[]; missingThere: string[]; drifted: string[] };

/**
 * Check 1, as a function, so the test below can run it against a MUTATED copy of the frontend
 * source and prove it has teeth. `frontend` is keyed by file so each declaration is looked up
 * in the file it was actually copied from.
 */
function sourceGate(frontend: Map<string, Map<string, string>>): SourceGateResult {
  const port = declarations(PORT_SOURCE);
  const result: SourceGateResult = { missingHere: [], missingThere: [], drifted: [] };
  for (const [name, file] of Object.entries(PORTED_DECLARATIONS)) {
    const mine = port.get(name);
    const theirs = frontend.get(file)?.get(name);
    if (!mine) { result.missingHere.push(name); continue; }
    if (!theirs) { result.missingThere.push(`${name} (${file})`); continue; }
    if (comparable(mine) !== comparable(theirs)) {
      result.drifted.push(`${name}\n  frontend: ${comparable(theirs)}\n  backend : ${comparable(mine)}`);
    }
  }
  return result;
}

function frontendDeclarations(): Map<string, Map<string, string>> {
  return new Map<string, Map<string, string>>([
    [FORMAT_SOURCE, declarations(FORMAT_SOURCE)],
    [PROSE_SOURCE, declarations(PROSE_SOURCE)],
  ]);
}

describe('buyerFacingCaveat is a held-by-test port of the frontend authority', () => {
  it('declares the same rules as the frontend source, character for character', () => {
    const { missingHere, missingThere, drifted } = sourceGate(frontendDeclarations());

    expect(missingThere, 'declarations removed or renamed on the frontend').toEqual([]);
    expect(missingHere, 'declarations the port lost').toEqual([]);
    expect(drifted.join('\n\n'), 'ported rules that no longer match the frontend authority').toBe('');
  });

  /**
   * THE GATE ABOVE, GATED. A check that never fires is indistinguishable from one that cannot,
   * and check 1 exists precisely for the changes check 2 cannot see. So: take the frontend
   * source, widen ONE ported rule with an alternative no value in either corpus contains, and
   * assert (a) the source gate names that declaration, and (b) the behavioural differential is
   * blind to it, because nothing exercises the alternative. The mutation is applied to a COPY
   * in a temp directory; the frontend file is never touched.
   */
  it('fails on a frontend rule change that no input exercises', { timeout: 60_000 }, () => {
    const original = readFileSync(PROSE_SOURCE, 'utf8');
    const RULE = String.raw`[/\b(?:a|an)(\s+)corpus\b/gi, "a$1body of evidence"],`;
    const WIDENED = String.raw`[/\b(?:a|an|one)(\s+)corpus\b/gi, "a$1body of evidence"],`;
    expect(
      original.includes(RULE),
      'the RESEARCH_CORPUS_GLOSS article rule was reworded — re-key this mutation to the rule as it now reads',
    ).toBe(true);

    const directory = mkdtempSync(join(tmpdir(), 'buyerFacingCaveat-drift-'));
    const mutatedPath = join(directory, 'buyerFacingResearchProse.ts');
    writeFileSync(mutatedPath, original.replace(RULE, WIDENED));

    const mutated = frontendDeclarations();
    mutated.set(PROSE_SOURCE, declarations(mutatedPath));
    const { drifted, missingHere, missingThere } = sourceGate(mutated);

    expect(missingHere).toEqual([]);
    expect(missingThere).toEqual([]);
    expect(
      drifted.map((entry) => entry.split('\n')[0]),
      'the source gate did not notice a rule that changed on the frontend',
    ).toEqual(['RESEARCH_CORPUS_GLOSS']);

    // (b) — and check 2 would have passed: the widened alternative matches nothing in either
    // corpus, so every output is byte-identical with and without the mutation.
    const unexercised = [...verdictCorpus(), ...CORPUS, ...outputCorpus()]
      .filter((value) => /\bone\s+corpus\b/i.test(value));
    expect(unexercised, 'the mutation is exercised after all — pick another rule').toEqual([]);
  });

  it('keeps the `$lib` alias out of production code', () => {
    // The alias exists in vitest.config.ts so THIS FILE can reach the authority. `tsc` has no
    // such path and the API ships from `dist` without the frontend sources, so a production
    // import would pass the type-check here and fail at runtime in the container.
    const offenders: string[] = [];
    const walk = (dir: string): void => {
      for (const entry of readdirSync(dir)) {
        if (entry === '__tests__' || entry === 'node_modules') continue;
        const path = join(dir, entry);
        if (statSync(path).isDirectory()) walk(path);
        else if (entry.endsWith('.ts') && /from\s+['"]\$lib|import\(\s*['"]\$lib/.test(readFileSync(path, 'utf8'))) {
          offenders.push(path);
        }
      }
    };
    walk(join(HERE, '../..'));
    expect(offenders, 'production modules importing through the test-only $lib alias').toEqual([]);
  });

  it('produces byte-identical output to the frontend authority on every real corpus value', { timeout: 60_000 }, async () => {
    const authority = await loadAuthority();
    if (!authority) return;

    const corpus = [...new Set([...CORPUS, ...outputCorpus()])];
    expect(corpus.length).toBeGreaterThanOrEqual(CORPUS.length);

    const mismatches = corpus
      .filter((value) => authority.buyerFacingCoverageNote(value) !== buyerFacingCoverageNote(value))
      .map((value) => (
        `IN:       ${value}\nfrontend: ${authority.buyerFacingCoverageNote(value)}\nbackend:  ${buyerFacingCoverageNote(value)}`
      ));
    expect(mismatches.join('\n\n')).toBe('');
  });

  it('reads the niche-difficulty verdict exactly as the frontend authority does', { timeout: 60_000 }, async () => {
    const authority = await loadAuthority();
    if (!authority) return;

    const corpus = verdictCorpus();
    expect(corpus.length).toBeGreaterThanOrEqual(VERDICT_NARRATIVES.length + VERDICT_HEADLINES.length);

    const mismatches: string[] = [];
    for (const value of corpus) {
      // Every entry point over every value: the excerpt takes the narrative through
      // `buyerFacingVerdictNarrative` and the headline through `buyerFacingVerdictHeadline`.
      // `buyerFacingResearchProse` is here because the same table feeds `key_challenges` on
      // the frontend, and a gloss edit must be caught on both readings, not just the one
      // `caveatSources` calls.
      for (const [name, mine, theirs] of [
        ['buyerFacingResearchProse', buyerFacingResearchProse, authority.buyerFacingResearchProse],
        ['buyerFacingVerdictNarrative', buyerFacingVerdictNarrative, authority.buyerFacingVerdictNarrative],
        ['buyerFacingVerdictHeadline', buyerFacingVerdictHeadline, authority.buyerFacingVerdictHeadline],
      ] as [string, (value: string) => string, (value: string) => string][]) {
        if (mine(value) !== theirs(value)) {
          mismatches.push(`${name}\nIN:       ${value}\nfrontend: ${theirs(value)}\nbackend:  ${mine(value)}`);
        }
      }
    }
    expect(mismatches.join('\n\n')).toBe('');
  });
});

describe('the constraints the frontend rules were built around survive the port', () => {
  it('keeps a tight en dash inside a numeric range', () => {
    // The clause-dash rule fires on a SPACED dash only. "15–20 minutes" is a range, and an
    // earlier hand-rolled chain turned it into "15. 20 minutes" on its second pass.
    const note = "High-severity pain 'Morning espresso routine takes 15–20 minutes, causing delays to work' is not addressed by any generated solution.";
    expect(buyerFacingCoverageNote(note)).toContain('15–20 minutes');
    expect(buyerFacingIdeaProse('Incumbents price this at $99–399/mo across the market.'))
      .toContain('$99–399/mo');
  });

  it('breaks a spaced clause dash and sentence-cases the tail', () => {
    expect(buyerFacingIdeaProse('The signal is thin — buyers still ask for it weekly.'))
      .toBe('The signal is thin. Buyers still ask for it weekly.');
  });

  it('leaves a parenthetical dash PAIR alone', () => {
    const paired = 'The buyer — a clinic owner — signs the check.';
    expect(buyerFacingIdeaProse(paired)).toBe(paired);
  });

  it('gates the repr field names on a following `=`, so a product JSON schema is left alone', () => {
    // A real `technical_approach` value names `severity_score` as a COLUMN of a schema the
    // PRODUCT would define, beside two names this table does not own. Renaming one of three
    // would leave the list half-translated.
    const productSchema = 'Store each complaint in a structured JSON schema (complaint, workaround, severity_score, pay_signal, source_url).';
    expect(humanizeInternalJargon(productSchema)).toBe(productSchema);
  });

  it('renames the repr field names in front of `=` and leaves the buyer\'s own words verbatim', () => {
    const quote = "I am burnt the F out. I had a bit of a breakdown 1.5 weeks ago";
    const repr = `Core pain point 'title='Burnout and Mental Health Struggles' severity_score=0.9 willingness_to_pay_score=0.6 representative_quote="${quote}" source_platform='Reddit r/gamedev'' (the #1 pain point by severity+WTP) is not in the selected solution's pain_points_addressed list.`;
    const out = buyerFacingCoverageNote(repr);
    expect(out).toContain(quote);
    expect(out).not.toMatch(/\b(?:severity_score|willingness_to_pay_score|representative_quote|source_platform)\b/);
    expect(out).not.toContain('pain_points_addressed');
  });

  it('keeps the calibration stanza, which no other rule owns', () => {
    // A residual-TOKEN metric reads 0 on this input even with the stanza deleted, because
    // producer PROSE carries no internal token. Assert the PHRASES.
    const out = buyerFacingCoverageNote(CORPUS[0]);
    for (const phrase of [
      'Calibration note',
      'route verifier',
      'cites data route',
      'as market-fit support',
      'market-fit score',
      'unverified on the data-route dimension',
      'data_access_model',
    ]) {
      expect(out, `producer phrase still shipped: ${phrase}`).not.toContain(phrase);
    }
    expect(out).toContain('Research caveat');
    expect(out).toContain('Data access: Not verified');
  });

  it('glosses "corpus" per FIELD, not per surface', () => {
    // MEASURED, because a round shipped this fork backwards on an unmeasured assertion. Over
    // the 28 distinct `niche_difficulty_verdict.narrative_summary` values under `output/`, 21
    // say "corpus"/"corpora" and every one means the dataset a product would have to build.
    // Only `key_challenges` carries the evidence reading, in one value.
    expect(buyerFacingVerdictNarrative(
      'Many concepts require a corpus that does not yet exist.',
    )).toBe('Many concepts require a dataset that does not yet exist.');
    expect(buyerFacingResearchProse('The corpus drifts from the stated audience.'))
      .toBe('The collected evidence drifts from the stated audience.');
    expect(buyerFacingCoverageNote('The recipe corpus is reachable.'))
      .toBe('The recipe dataset is reachable.');
    // The evidence reading is a MASS noun, so an indefinite article needs a count head — and
    // the article does not have to be adjacent to get one. "a new collected evidence" is what
    // the adjacency-bound rule shipped.
    expect(buyerFacingResearchProse('Many concepts require a corpus that does not yet exist.'))
      .toBe('Many concepts require a body of evidence that does not yet exist.');
    expect(buyerFacingResearchProse('Ideas requiring a new corpus are the risky ones.'))
      .toBe('Ideas requiring a new body of evidence are the risky ones.');
    expect(buyerFacingResearchProse('Ideas requiring a new, unproven corpus are the risky ones.'))
      .toBe('Ideas requiring a new, unproven body of evidence are the risky ones.');
    // The article agrees with what now FOLLOWS it, which is the modifier when there is one.
    expect(buyerFacingResearchProse('This needs an unproven corpus.'))
      .toBe('This needs an unproven body of evidence.');
    // …and the noun itself when there is not.
    expect(buyerFacingResearchProse('This needs an corpus.'))
      .toBe('This needs a body of evidence.');
    // A determiner ends the article's noun phrase: no count head is owed here.
    expect(buyerFacingResearchProse('Build a tool that indexes the corpus.'))
      .toBe('Build a tool that indexes the collected evidence.');
    // THE PLURAL LEMMA. `\bcorpus\b` cannot match "corpora", and 2 of the 28 narratives
    // carry it, so both glosses need a backstop of their own.
    expect(buyerFacingVerdictNarrative(
      'Many effective solutions require data corpora that do not currently exist.',
    )).toBe('Many effective solutions require bodies of data that do not currently exist.');
    expect(buyerFacingResearchProse('The corpora disagree.'))
      .toBe('The bodies of evidence disagree.');
    expect(buyerFacingCoverageNote('The recipe corpora are reachable.'))
      .toBe('The recipe datasets are reachable.');
  });

  it('keeps the headline\'s structural separator and sanitises only its tail', () => {
    // Both frontend consumers split on "Software Fit: <Tier> — <clause>", so the rating word
    // and the separator survive; the clause behind it takes the narrative's reading, because
    // `niche_difficulty.py` writes the headline and the narrative as ONE LLM pair and
    // `caveatSources` puts them in the SAME excerpt slot. No real headline says "corpus" —
    // 0 of the 28 distinct values under `output/` — so this input exercises the COLON
    // separator; the noun follows the field it is a compression of.
    expect(buyerFacingVerdictHeadline('Software Fit: Moderate: the corpus is thinner than the wedge needs'))
      .toBe('Software Fit: Moderate — the dataset is thinner than the entry point needs');
    expect(buyerFacingVerdictHeadline('Software Fit: Strong—automating inventory and controlled substance compliance'))
      .toBe('Software Fit: Strong — automating inventory and controlled substance compliance');
    // No head, no structure to keep: the whole string is prose.
    expect(buyerFacingVerdictHeadline('Cold-start data corpus required before the wedge is usable'))
      .toBe('Up-front body of data required before the entry point is usable');
  });

  it('is idempotent on every verdict value and never empties one', { timeout: 60_000 }, () => {
    for (const value of verdictCorpus()) {
      for (const read of [
        buyerFacingResearchProse,
        buyerFacingVerdictNarrative,
        buyerFacingVerdictHeadline,
      ]) {
        const once = read(value);
        expect(once.trim(), `emptied: ${value}`).not.toBe('');
        expect(read(once), `not idempotent: ${value}`).toBe(once);
      }
    }
  });

  it('is idempotent on every corpus value', { timeout: 60_000 }, () => {
    for (const value of [...new Set([...CORPUS, ...outputCorpus()])]) {
      const once = buyerFacingCoverageNote(value);
      expect(buyerFacingCoverageNote(once), `not idempotent: ${value}`).toBe(once);
    }
  });

  it('never empties a caveat', { timeout: 60_000 }, () => {
    for (const value of [...new Set([...CORPUS, ...outputCorpus()])]) {
      expect(buyerFacingCoverageNote(value).trim(), `emptied: ${value}`).not.toBe('');
    }
  });
});

/**
 * NEITHER GATE ABOVE HOLDS THE ROUTING, ONLY THE RULES.
 *
 * The two checks at the top of this file prove the port DECLARES what the frontend declares.
 * They say nothing about which reader each side hands each FIELD to, and the two sides route
 * independently: the frontend forks `niche_difficulty_verdict` in
 * `buyerFacingNicheDifficultyVerdict`, this API forks the same object again in
 * `caveatSources`. Flip either fork and the same stored field prints one noun on the job page
 * and the other on the evidence card, with every rule identical and both gates green.
 *
 * The verdict below is built so the two glosses ANSWER DIFFERENTLY on every field that forks:
 * a bare `corpus` reads "dataset" on the narrative and the headline, "collected evidence" on
 * `key_challenges`. Comparing the API's output against the frontend authority's therefore
 * fails on a fork flip on EITHER side, which is the property neither drift check can see.
 */
describe('the two sides route each verdict field to the same reader', () => {
  const IDEA: IdeaRecord = { idea_id: 'idea_1', idea_revision: 1, solution_name: 'PayoutClarity' };
  const FORKING_VERDICT = {
    headline: 'Software Fit: Moderate — the corpus is thinner than the wedge needs',
    narrative_summary: 'Many concepts require a corpus that does not yet exist.',
    key_challenges: ['The corpus drifts from the stated audience.'],
  };

  it('agrees with the frontend on the narrative and the headline, field for field', async () => {
    const authority = await loadAuthority();
    if (!authority) return;

    const sources = buildSelectionChallengeEvidence(
      'demand', IDEA, { niche_difficulty_verdict: FORKING_VERDICT }, {},
    ).filter((source) => source.kind === 'market_caveat');
    expect(sources).toHaveLength(1);

    // The fixture discriminates: assert that first, so this can never pass vacuously on a
    // verdict both glosses happen to answer identically.
    expect(authority.buyerFacingVerdictNarrative(FORKING_VERDICT.narrative_summary))
      .not.toBe(authority.buyerFacingResearchProse(FORKING_VERDICT.narrative_summary));

    // Compared against the frontend's OWN ROUTING — `buyerFacingNicheDifficultyVerdict`, the
    // function that decides which reader each verdict field gets over there — and not against
    // the reader this side happens to call. A fork flip on EITHER side breaks this.
    const theirs = authority.buyerFacingNicheDifficultyVerdict(FORKING_VERDICT);
    expect(sources[0].excerpt).toBe(theirs.narrative_summary);
    expect(sources[0].title).toBe(theirs.headline);
    // …and the noun each field actually lands on, stated rather than inferred.
    expect(sources[0].excerpt).toContain('require a dataset that does not yet exist');
    expect(sources[0].title).toContain('the dataset is thinner');
  });

  it('keeps `key_challenges` on the OTHER reading, which this API never prints', async () => {
    const authority = await loadAuthority();
    if (!authority) return;
    // The evidence gloss is gated in this file only because it shares a table with the
    // dataset one. This pins the fork itself: same word, same object, different noun.
    const theirs = authority.buyerFacingNicheDifficultyVerdict(FORKING_VERDICT);
    expect(theirs.key_challenges[0]).toBe('The collected evidence drifts from the stated audience.');
    expect(theirs.narrative_summary).toContain('require a dataset that does not yet exist');
    expect(buyerFacingResearchProse(FORKING_VERDICT.key_challenges[0]))
      .toBe(theirs.key_challenges[0]);
  });
});
