import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

import { buildSelectionChallengeEvidence } from '../selectionChallengeEvidence.js';
import type { IdeaRecord } from '../../utils/ideaIdentity.js';

/**
 * `caveatSources` used to put `data_quality_summary.quality_caveats` into `excerpt` RAW, and
 * `EvidenceChallenge.svelte` prints that string to the owner unchanged. The frontend's
 * `buyerFacingCoverageNote` reads the same field on the report and the shortlist, but no
 * TypeScript module in the frontend can reach a string the API already baked into a stored
 * evidence snapshot — so the leak had to be closed on this side (finding D27).
 *
 * The assertions below are on the RENDERED excerpt, not on the service's return value alone:
 * the component's own `readableEvidenceExcerpt` is lifted out of the `.svelte` file at runtime
 * and run over what this service produced.
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../../../..');
const COMPONENT = join(REPO, 'frontend/src/lib/components/selection/EvidenceChallenge.svelte');

/**
 * The producer phrases that reach the buyer whole. A snake_case-token scan reads 0 on most of
 * these — that blind metric is what let two earlier rounds call this leak closed.
 */
const PRODUCER_PHRASES: [string, RegExp][] = [
  ['Calibration note', /\bCalibration note\b/i],
  ['route verifier', /\broute verifier\b/i],
  ['cites data route', /\bcites? (?:a )?data route\b/i],
  ['as market-fit support', /\bas market-fit support\b/i],
  ['market-fit score', /\bmarket-fit score\b/i],
  ['unverified on the data-route dimension', /\bunverified on the data-route dimension\b/i],
  // Bare, not "Idea-set coverage —": the anchored COVERAGE_NOTE misses a TRUNCATED input, and
  // the blind clause-dash rule then turns the head into "Idea-set coverage." — still the
  // producer's own label, and a dash-suffixed pattern reads 0 on it.
  ['Idea-set coverage', /\bIdea-set coverage\b/i],
  ['Concentration may reflect …', /Concentration may reflect where the real opportunity is/i],
  ['Novelty/obviousness collapsed', /Novelty\/obviousness collapsed/i],
  ['prioritised for ideation', /was prioritised for ideation as the closest match/i],
];
const INTERNAL_TOKEN = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|\bWTP\b/;
/** A SPACED dash is a clause break. A tight one is a numeric range or a compound. */
const CLAUSE_DASH = /\S\s+[—–]+\s+\S/;

const RAW_CAVEATS = [
  'Calibration note for "AgencySeatTaxCalc" cites data route "Deterministic arithmetic on the user\'s own inputs" as market-fit support, but the route verifier did not confirm it (data_access_model: unverified). Treat the market-fit score as unverified on the data-route dimension.',
  'Idea-set coverage — 3 of 5 ideas address "Manual invoicing eats the week"; validated pains with no idea: Delayed month-end close. Concentration may reflect where the real opportunity is, not a defect — shown for your judgment.',
  'Core pain point \'title=\'Burnout and Mental Health Struggles\' severity_score=0.9 willingness_to_pay_score=0.6 representative_quote="I am burnt the F out. I had a bit of a breakdown 1.5 weeks ago." source_platform=\'Reddit r/gamedev\'\' (the #1 pain point by severity+WTP) is not in the selected solution\'s pain_points_addressed list.',
  'Novelty/obviousness collapsed to exact complements this run — treat the two originality axes as one signal.',
  "High-severity pain 'Morning espresso routine takes 15–20 minutes, causing delays to work' is not addressed by any generated solution.",
];

const IDEA: IdeaRecord = { idea_id: 'idea_1', idea_revision: 1, solution_name: 'PayoutClarity' };
const PREVIEW = { data_quality_summary: { quality_caveats: RAW_CAVEATS } };

function caveatExcerpts(): string[] {
  return buildSelectionChallengeEvidence('demand', IDEA, PREVIEW, {})
    .filter((source) => source.kind === 'market_caveat')
    .map((source) => source.excerpt);
}

/**
 * `readableEvidenceExcerpt`, lifted out of the component and transpiled. It is plain
 * TypeScript with no runes and no imports, so it runs here exactly as it runs in the browser —
 * which is the point: this asserts the string the owner READS, not the one the service returns.
 */
function componentRenderer(): (excerpt: string) => { text: string; raw: string | null } {
  const component = readFileSync(COMPONENT, 'utf8');
  const script = component.match(/<script[^>]*>([\s\S]*?)<\/script>/)?.[1];
  expect(script, 'EvidenceChallenge.svelte has no <script> block').toBeTruthy();
  // Parsed rather than brace-matched: the signature's own return type is an object literal,
  // and a naive scan for the first `{` stops at `{ text: string; raw: string | null }`.
  const parsed = ts.createSourceFile('EvidenceChallenge.ts', script!, ts.ScriptTarget.Latest, true);
  const declaration = parsed.statements.find(
    (statement): statement is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(statement) && statement.name?.text === 'readableEvidenceExcerpt',
  );
  expect(declaration, 'readableEvidenceExcerpt is gone from EvidenceChallenge.svelte').toBeTruthy();
  const transpiled = ts.transpileModule(declaration!.getText(parsed), {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return new Function(`${transpiled}\nreturn readableEvidenceExcerpt;`)() as (
    excerpt: string,
  ) => { text: string; raw: string | null };
}

describe('quality_caveats on the EvidenceChallenge render path', () => {
  it('still reaches the owner through readableEvidenceExcerpt and a plain <p>', () => {
    // If either of these moves, the render assertions below stop meaning anything.
    const component = readFileSync(COMPONENT, 'utf8');
    expect(component).toContain('readableEvidenceExcerpt(source.excerpt)');
    expect(component).toContain('<p>{readableExcerpt.text}</p>');
  });

  it('renders no producer phrase, clause dash or internal token', () => {
    const render = componentRenderer();
    const excerpts = caveatExcerpts();
    expect(excerpts).toHaveLength(RAW_CAVEATS.length);

    for (const excerpt of excerpts) {
      const rendered = render(excerpt);
      expect(rendered.raw, 'the caveat took the "could not be formatted" branch').toBeNull();
      for (const [name, pattern] of PRODUCER_PHRASES) {
        expect(rendered.text, `rendered producer phrase: ${name}`).not.toMatch(pattern);
      }
      expect(rendered.text, 'rendered internal token').not.toMatch(INTERNAL_TOKEN);
      expect(rendered.text, 'rendered clause dash').not.toMatch(CLAUSE_DASH);
      expect(rendered.text.trim()).not.toBe('');
    }
  });

  it('keeps a tight numeric range and the buyer\'s own quoted words intact', () => {
    const render = componentRenderer();
    const rendered = caveatExcerpts().map((excerpt) => render(excerpt).text);
    expect(rendered.some((text) => text.includes('15–20 minutes'))).toBe(true);
    expect(rendered.some((text) => text.includes('I am burnt the F out.'))).toBe(true);
  });

  it('reads the calibration caveat as the product reads it', () => {
    const render = componentRenderer();
    const calibration = render(caveatExcerpts()[0]).text;
    expect(calibration).toContain('Research caveat');
    expect(calibration).toContain('uses a data source');
    expect(calibration).toContain('Data access: Not verified');
  });

  it('leaves the other evidence kinds untouched', () => {
    // The sanitiser is scoped to one field. A competitor or audience fact is assembled from a
    // different part of the preview report and must arrive exactly as `text()` built it.
    const sources = buildSelectionChallengeEvidence(
      'competition',
      IDEA,
      {
        ...PREVIEW,
        market_reality: {
          incumbents: [{ name: 'Notion', focus: 'Docs — and databases', pricing: '$10/seat' }],
        },
      },
      {},
    );
    const competitor = sources.find((source) => source.kind === 'competitor_fact');
    expect(competitor?.excerpt).toBe('Focus: Docs — and databases · Pricing: $10/seat');
  });
});

/**
 * THE SECOND FIELD IN THE SAME `SourceInput[]` (finding D28). `caveatSources` also pushes
 * `niche_difficulty_verdict.narrative_summary ?? .headline` into `excerpt`, rendered by the
 * same `<p>`, and it went in RAW.
 *
 * A TOKEN METRIC READS THIS FIELD CLEAN. `_without_long_dashes` runs on the persisted path, so
 * over the 28 distinct narratives under `output/` there are ZERO clause dashes and ZERO
 * snake_case tokens — and 24 of them still say "corpus"/"corpora" (21), "cold-start" (17) or
 * "wedge" (6) to the owner. The assertions below are on PHRASES.
 *
 * WHICH GLOSS, MEASURED. An earlier round asserted that reusing the coverage-note entry point
 * "would print the wrong noun on 19 of the 28 distinct verdict values". That was false in its
 * number AND in its direction. Run over all 28, the two entry points differ on TWO —
 * "requiring a new corpus" and "require a corpus that does not yet exist" — and on both the
 * COVERAGE-NOTE reading ("a new dataset", "a dataset that does not yet exist") is the correct
 * one: all 21 corpus-bearing narratives mean the dataset a product would have to build, every
 * one of them beside "require", "seed", "cold-start" or "does not yet exist". The evidence
 * reading belongs to `key_challenges` ("The corpus drifts from the stated audience") — a field
 * `caveatSources` never reads. So the narrative and the headline take
 * `buyerFacingVerdictNarrative` / `buyerFacingVerdictHeadline` and the dataset gloss; they are
 * still a separate entry point from `buyerFacingCoverageNote`, which owns a coverage and
 * calibration stanza the verdict must not be run through.
 *
 * `corpora` is on the list because `\bcorpus\b` cannot match it, and 2 of the 28 narratives
 * carry it — the exact shape a lemma-blind phrase list certifies as clean.
 */
const VERDICT_PRODUCER_PHRASES: [string, RegExp][] = [
  ['corpus', /\bcorpus\b/i],
  ['corpora', /\bcorpora\b/i],
  ['cold-start', /\bcold[-\s]start\b/i],
  ['wedge', /\bwedge\b/i],
  ['web-verified', /\bweb-verified\b/i],
];

/**
 * AN ARTICLE HAS TO AGREE WITH THE NOUN THE GLOSS PUT BEHIND IT. This is the assertion the
 * round-1 test could not make: its own fixture ("…requiring a new corpus…") rendered
 * "requiring a new collected evidence" and satisfied every phrase, token and dash check on the
 * list above. A mass-noun replacement under an indefinite article is the defect, adjacent or
 * not; `corpus` -> "collected evidence" and `wedge` -> "entry point" have both shipped it.
 *
 * The two mass phrases the vocabulary can emit are "collected evidence" and "up-front data".
 * Both are legal in two positions this must NOT flag, so the pattern is bounded at both ends:
 *
 *   as a MODIFIER — "an up-front data play", which the module ships today. So the phrase has
 *   to be in HEAD position: followed by punctuation, a function word, or the end.
 *
 *   under a DIFFERENT head — "a gap in the collected evidence", the corpus-evidence-gap rule's
 *   own output. So the run between the article and the phrase excludes the function words that
 *   mean the article's own noun phrase already ended.
 */
const NOT_A_MODIFIER = String.raw`the|an?|of|in|on|to|that|which|and|or|for|with|from|by|is|are|was|were|as`;
const MASS_HEADS = String.raw`collected evidence|up-front data`;
const MASS_NOUN_UNDER_ARTICLE = new RegExp(
  String.raw`\b(?:a|an)\s+(?:(?!(?:${NOT_A_MODIFIER})\b)[A-Za-z][\w'’-]*,?\s+){0,3}(?:${MASS_HEADS})`
  + String.raw`(?=\s*[.,;:!?)]|\s+(?:that|which|who|is|are|was|were|and|or|to|in|on|for|from|before|after|so|rather|but|with)\b|$)`,
  'i',
);

/** Real `niche_difficulty_verdict.narrative_summary` values, copied verbatim from `output/`. */
const RAW_NARRATIVES = [
  'Software can directly own nearly all the workflow and data pains found in auto repair shops, but you must prioritize building a free tool with built-in distribution like lead-gen or sponsorship rather than a subscription product due to weak buying signals. The high difficulty stems from a saturated tool ecosystem where most obvious angles already ship, so your success depends on finding a sharper wedge rather than just feasibility. Focus your efforts on ideas that utilize existing reachable data rather than those requiring a new corpus, and consider usage-based pricing models since many shop tasks occur only episodically.',
  'Software can directly own the repetitive communication tasks and brand monitoring pains within this niche, though high difficulty persists due to cold-start risks and a dense existing tool ecosystem. Because buying signals are weak, you should build free tools with built-in distribution mechanisms like lead-gen or sponsorship rather than pursuing subscription pricing. Focus on solving the cold-start data problem early, as many concepts require a corpus that does not yet exist to be truly useful.',
  'You should build a solution that directly owns community management tasks, but you must tighten your wedge specifically for small SaaS operators to avoid serving the wrong user. While software can solve most of these pains, you face high difficulty due to a dense tool ecosystem and the need for a cold-start strategy to build a data corpus that does not yet exist. Buyers demonstrate strong willingness to pay, so focus on a subscription model that emphasizes convenience over existing DIY methods.',
  // The PLURAL lemma. `\bcorpus\b` cannot match "corpora", so both of these shipped the
  // producer's word to the owner verbatim while every assertion on this file passed.
  'You should build tools that directly own the administrative burden of scheduling and roster management, as software can solve about half of the core pains in this niche. While the fit is strong, the high difficulty stems from the need to overcome a significant cold-start risk, as many effective solutions require data corpora that do not currently exist. Because the niche features a dense ecosystem of existing tools, you must plan to compete for attention within an established stack rather than assuming a vacant market.',
  'Software can directly own most bookkeeping pains, but you should avoid traditional subscription models in favor of free tools with built-in distribution like lead-gen or sponsorship due to weak buying signals. The high difficulty stems from a saturated tool ecosystem and the need for a cold-start strategy to build data corpora that do not currently exist. Focus your development on a sharp wedge that competes directly against established incumbents rather than attempting to fill an empty market.',
  // An article separated from the noun by a MODIFIER RUN.
  'Software can directly own about half of the technical and logistical pains in this niche, though you should focus on ideas that leverage existing user data rather than those requiring a new, unproven data corpus. While the software fit is strong, the difficulty is high because the tool ecosystem is already moderately saturated and you must compete head-on with established incumbents for attention. Given that willingness to pay is moderate and some ideas are used only episodically, prioritize models that target specific high-value pain points rather than relying on broad subscription tiers.',
];
const RAW_HEADLINE = 'Software Fit: Moderate: the corpus is thinner than the wedge needs';

function verdictSource(verdict: Record<string, unknown>) {
  const sources = buildSelectionChallengeEvidence(
    'demand',
    IDEA,
    { niche_difficulty_verdict: verdict },
    {},
  ).filter((source) => source.kind === 'market_caveat');
  expect(sources).toHaveLength(1);
  return sources[0];
}

describe('niche_difficulty_verdict on the EvidenceChallenge render path', () => {
  it('renders no producer phrase, clause dash or internal token', () => {
    const render = componentRenderer();
    for (const narrative of RAW_NARRATIVES) {
      const rendered = render(verdictSource({ narrative_summary: narrative, headline: RAW_HEADLINE }).excerpt);
      expect(rendered.raw, 'the verdict took the "could not be formatted" branch').toBeNull();
      for (const [name, pattern] of VERDICT_PRODUCER_PHRASES) {
        expect(rendered.text, `rendered producer phrase: ${name}`).not.toMatch(pattern);
      }
      expect(rendered.text, 'rendered internal token').not.toMatch(INTERNAL_TOKEN);
      expect(rendered.text, 'rendered clause dash').not.toMatch(CLAUSE_DASH);
      expect(rendered.text, 'mass noun under an indefinite article').not.toMatch(MASS_NOUN_UNDER_ARTICLE);
      expect(rendered.text.trim()).not.toBe('');
    }
  });

  it('reads the narrative\'s "corpus" as the dataset a product would have to build', () => {
    const render = componentRenderer();
    // MEASURED, not assumed: all 21 corpus-bearing narratives under `output/` read this way.
    // This is the real value the round-1 fixture used, and its rendered form was "…requiring a
    // new collected evidence…" — grammatical nonsense that every phrase and token check passed.
    const rendered = render(verdictSource({ narrative_summary: RAW_NARRATIVES[0] }).excerpt);
    expect(rendered.text).toContain('those requiring a new dataset');
    expect(rendered.text).not.toContain('a new collected evidence');

    // The plural, which no rule matched at all before this round.
    expect(render(verdictSource({ narrative_summary: RAW_NARRATIVES[3] }).excerpt).text)
      .toContain('require bodies of data that do not currently exist');

    // The caveat entry point, on the same card, still runs its own stanza on its own field.
    expect(render(verdictSource({ narrative_summary: 'x' }).excerpt).text).toBe('x');
  });

  it('takes the headline through the verdict treatment, in the title and in the excerpt', () => {
    const render = componentRenderer();
    // The title is the headline on every verdict; the excerpt is the headline only when the
    // producer wrote no narrative.
    const withNarrative = verdictSource({ narrative_summary: 'Plain narrative.', headline: RAW_HEADLINE });
    // The tail takes the NARRATIVE's reading: `niche_difficulty.py` writes the headline and
    // the narrative as one LLM pair, and `caveatSources` puts them in the same excerpt slot.
    // No real headline says "corpus" (0 of the 28 under `output/`), so this fixture is here
    // for the colon separator; the noun follows the field it is a compression of.
    expect(withNarrative.title).toBe(
      'Software Fit: Moderate — the dataset is thinner than the entry point needs',
    );

    const headlineOnly = verdictSource({ headline: RAW_HEADLINE });
    const rendered = render(headlineOnly.excerpt).text;
    expect(rendered).toBe(withNarrative.title);
    // The rating word and its separator survive: both frontend consumers parse on them.
    expect(rendered).toMatch(/^Software Fit: Moderate — /);
    for (const [name, pattern] of VERDICT_PRODUCER_PHRASES) {
      expect(rendered, `rendered producer phrase: ${name}`).not.toMatch(pattern);
    }
    expect(rendered, 'mass noun under an indefinite article').not.toMatch(MASS_NOUN_UNDER_ARTICLE);
  });

  it('sanitises BEFORE the 1,500-character clip', () => {
    // The rules that carry the most weight are keyed to WHOLE producer sentences. Clip first
    // and the clip lands inside one, the sentence rule stops matching, and the word-level
    // fallbacks print a different reading of the same sentence. The longest verdict value
    // under `output/` is 629 characters, so this ordering is inert TODAY — and the test does
    // not depend on that staying true.
    const producerSentence =
      "Most ideas need a data corpus that doesn't exist yet — plan a cold-start play (seed it, "
      + 'scrape it, or partner) before the product is useful.';
    const padding = 'The niche is crowded and the buyers are cautious. '.repeat(29);
    expect(padding.length).toBeLessThan(1_500);
    expect(padding.length + producerSentence.length).toBeGreaterThan(1_500);

    const rendered = componentRenderer()(
      verdictSource({ narrative_summary: `${padding}${producerSentence}` }).excerpt,
    ).text;
    // The discriminator is narrow BY CONSTRUCTION: `data corpus` -> "body of data" is a
    // word-level rule and fires in either order. Only the whole-sentence rule rewrites the
    // contraction, and it can only fire on a sentence the clip has not yet cut.
    expect(rendered).toContain('Most ideas need a body of data that does not exist');
    expect(rendered, 'the sentence was clipped before it was read').not.toContain("doesn't exist");
    expect(rendered).not.toContain('corpus');
    expect(rendered).not.toContain('cold-start');
  });

  it('never empties the verdict and is idempotent', () => {
    for (const narrative of RAW_NARRATIVES) {
      const once = verdictSource({ narrative_summary: narrative }).excerpt;
      expect(once.trim()).not.toBe('');
      expect(verdictSource({ narrative_summary: once }).excerpt).toBe(once);
    }
    const title = verdictSource({ narrative_summary: 'x', headline: RAW_HEADLINE }).title;
    expect(verdictSource({ narrative_summary: 'x', headline: title }).title).toBe(title);
  });

  it('keeps a headline-less verdict off the packet, exactly as before', () => {
    // `hasValue(narrative ?? headline)` must keep its nullish semantics: an EMPTY narrative
    // wins over a present headline, because `??` never looked at emptiness.
    expect(
      buildSelectionChallengeEvidence('demand', IDEA, { niche_difficulty_verdict: {} }, {}),
    ).toEqual([]);
    expect(
      buildSelectionChallengeEvidence(
        'demand', IDEA, { niche_difficulty_verdict: { narrative_summary: '', headline: RAW_HEADLINE } }, {},
      ),
    ).toEqual([]);
  });
});
