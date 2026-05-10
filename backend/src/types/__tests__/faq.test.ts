import { describe, it, expect } from 'vitest';
import {
  FaqEntrySchema,
  FaqArraySchema,
  FaqJsonMetaSchema,
} from '../faq.js';

// FaqEntrySchema is the per-entry shape — already battle-tested by the
// existing PATCH /categories/:id route. We add coverage for the new
// FaqArraySchema (used by the LLM-generation save path) since its
// array-level rules are what gate the new feature.

describe('FaqEntrySchema', () => {
  it('accepts a well-formed entry', () => {
    expect(
      FaqEntrySchema.safeParse({
        q: 'What is this niche about?',
        a: 'A short answer that satisfies the 10-character minimum.',
      }).success,
    ).toBe(true);
  });

  it('rejects HTML in q or a', () => {
    expect(
      FaqEntrySchema.safeParse({ q: 'Hello <b>world</b>?', a: 'plain answer text' }).success,
    ).toBe(false);
    expect(
      FaqEntrySchema.safeParse({ q: 'Plain question?', a: 'Has <script>alert(1)</script>' })
        .success,
    ).toBe(false);
  });

  it('enforces length bounds', () => {
    expect(FaqEntrySchema.safeParse({ q: 'tiny', a: 'plain answer text' }).success).toBe(
      false,
    );
    expect(FaqEntrySchema.safeParse({ q: 'Question?', a: 'short' }).success).toBe(false);
  });
});

describe('FaqArraySchema(anchorTerms)', () => {
  const validEntry = (q: string, a: string) => ({ q, a });

  // Minimal sub-niche fixture — entries reference the anchor term in the answer.
  function fixtureForNiche(niche: string) {
    return [
      validEntry(
        'What pain points are most common?',
        `Across discussions in ${niche}, the most-mentioned pains include slow CI feedback, lint noise, and missing context.`,
      ),
      validEntry(
        'What kinds of solutions are emerging?',
        `Several validated ideas in ${niche} ship in 4-6 weeks; most target solo developers and small teams.`,
      ),
      validEntry(
        'Who experiences these pain points?',
        `Active groups discussing ${niche}: solo developers, engineering managers, and DevOps engineers.`,
      ),
    ];
  }

  it('accepts a well-formed array with anchor presence in answers', () => {
    const result = FaqArraySchema(['AI Code Review Tools']).safeParse(
      fixtureForNiche('AI Code Review Tools'),
    );
    expect(result.success).toBe(true);
  });

  it('rejects arrays smaller than 2', () => {
    const result = FaqArraySchema(['Anything']).safeParse([
      validEntry('Just one question?', 'Just one answer here.'),
    ]);
    expect(result.success).toBe(false);
  });

  it('rejects arrays larger than 10', () => {
    const arr = Array.from({ length: 11 }, (_, i) =>
      validEntry(`Question number ${i}?`, `Answer about Anything ${i} long enough text.`),
    );
    const result = FaqArraySchema(['Anything']).safeParse(arr);
    expect(result.success).toBe(false);
  });

  it('rejects arrays with duplicate question strings (case-insensitive)', () => {
    const arr = [
      validEntry('What is X about Anything?', 'Answer one about Anything.'),
      validEntry('what is X about anything?', 'Different answer about Anything.'),
    ];
    const result = FaqArraySchema(['Anything']).safeParse(arr);
    expect(result.success).toBe(false);
  });

  it('rejects arrays where fewer than 50% of entries reference an anchor term', () => {
    const arr = [
      validEntry('First plain question?', 'First plain answer no anchor.'),
      validEntry('Second plain question?', 'Second plain answer no anchor.'),
      validEntry('Third plain question?', 'Third plain answer no anchor.'),
    ];
    const result = FaqArraySchema(['Specific Niche Name']).safeParse(arr);
    expect(result.success).toBe(false);
  });

  it('accepts when exactly half the entries reference the anchor term', () => {
    const arr = [
      validEntry(
        'What is the AI Code Review Tools market like?',
        'There is healthy demand for tooling here.',
      ),
      validEntry(
        'How long to build something useful?',
        'Around 4-6 weeks for a single-purpose MVP.',
      ),
      validEntry(
        'What audience cares most about AI Code Review Tools?',
        'Solo developers and engineering managers at fast-shipping startups.',
      ),
      validEntry(
        'Where does the data come from?',
        'Primarily Reddit and Hacker News scraping over the past year.',
      ),
    ];
    const result = FaqArraySchema(['AI Code Review Tools']).safeParse(arr);
    expect(result.success).toBe(true);
  });

  it('skips the anchor check when anchorTerms is empty (escape hatch)', () => {
    const arr = [
      validEntry('First plain question?', 'First plain answer no anchor.'),
      validEntry('Second plain question?', 'Second plain answer no anchor.'),
    ];
    expect(FaqArraySchema([]).safeParse(arr).success).toBe(true);
  });
});

describe('FaqJsonMetaSchema', () => {
  it('accepts a generated-source meta with model and timestamps', () => {
    const result = FaqJsonMetaSchema.safeParse({
      source: 'generated',
      model: 'gpt-4o-mini',
      generatedAt: '2026-05-08T12:00:00.000Z',
      tokensUsed: 1234,
      updatedAt: '2026-05-08T12:00:01.000Z',
    });
    expect(result.success).toBe(true);
  });

  it('accepts a manual-source meta with only updatedAt', () => {
    const result = FaqJsonMetaSchema.safeParse({
      source: 'manual',
      updatedAt: '2026-05-08T12:00:00.000Z',
    });
    expect(result.success).toBe(true);
  });

  it('rejects unknown source values', () => {
    const result = FaqJsonMetaSchema.safeParse({
      source: 'pipeline',
      updatedAt: '2026-05-08T12:00:00.000Z',
    });
    expect(result.success).toBe(false);
  });
});
