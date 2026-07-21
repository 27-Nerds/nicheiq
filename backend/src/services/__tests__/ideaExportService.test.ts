import { describe, expect, it } from 'vitest';
import {
  findIdeaForExport,
  ideaExportFilename,
  renderIdeaMarkdown,
  serializeIdeaJson,
} from '../ideaExportService.js';
import type { IdeaRecord } from '../../utils/ideaIdentity.js';

const IDEA: IdeaRecord = {
  idea_id: 'idea-abc',
  idea_revision: 2,
  solution_name: 'GLP-1 SafeSwitch Navigator',
  headline: 'Taper off GLP-1 without the rebound',
  description: 'A guided tapering companion.',
  market_fit_score: 0.82,
  core_features: ['Taper plans', 'Rebound alerts'],
  validation: { verdict: 'promising', signals: 3 },
  incumbent_parity: null,
  core_features_empty: [],
  tags: {},
};

describe('findIdeaForExport', () => {
  const ideas: IdeaRecord[] = [
    { idea_id: 'idea-abc', idea_revision: 1, solution_name: 'Old revision' },
    IDEA,
    { idea_id: 'idea-xyz', idea_revision: 1, solution_name: 'Other idea' },
  ];

  it('returns the exact idea_id + revision match', () => {
    expect(findIdeaForExport(ideas, 'idea-abc', 1)?.solution_name).toBe('Old revision');
    expect(findIdeaForExport(ideas, 'idea-abc', 2)?.solution_name).toBe('GLP-1 SafeSwitch Navigator');
  });

  it('falls back to the highest revision when no revision is given', () => {
    expect(findIdeaForExport(ideas, 'idea-abc')?.idea_revision).toBe(2);
  });

  it('returns null for an unknown idea_id or a stale revision', () => {
    expect(findIdeaForExport(ideas, 'idea-nope')).toBeNull();
    expect(findIdeaForExport(ideas, 'idea-abc', 3)).toBeNull();
  });
});

describe('serializeIdeaJson', () => {
  it('round-trips the full stored record', () => {
    expect(JSON.parse(serializeIdeaJson(IDEA))).toEqual(IDEA);
  });
});

describe('renderIdeaMarkdown', () => {
  it('renders the name as title and the revision', () => {
    const md = renderIdeaMarkdown(IDEA);
    expect(md).toContain('# GLP-1 SafeSwitch Navigator');
    expect(md).toContain('revision 2');
  });

  it('renders every present field with human labels', () => {
    const md = renderIdeaMarkdown(IDEA);
    expect(md).toContain('## Headline');
    expect(md).toContain('Taper off GLP-1 without the rebound');
    expect(md).toContain('## Market fit score');
    expect(md).toContain('0.82');
    expect(md).toContain('## Core features');
    expect(md).toContain('- Taper plans');
    expect(md).toContain('- Rebound alerts');
    expect(md).toContain('## Validation');
    expect(md).toContain('"verdict": "promising"');
  });

  it('skips null, empty-array, and empty-object fields', () => {
    const md = renderIdeaMarkdown(IDEA);
    expect(md).not.toContain('Incumbent parity');
    expect(md).not.toContain('Core features empty');
    expect(md).not.toContain('## Tags');
  });

  it('does not repeat the name fields as sections', () => {
    const md = renderIdeaMarkdown(IDEA);
    expect(md).not.toContain('## Solution name');
  });

  it('falls back to a generic title when no name is stored', () => {
    const md = renderIdeaMarkdown({ idea_id: 'idea-abc', idea_revision: 1 });
    expect(md).toContain('# Candidate export');
  });
});

describe('ideaExportFilename', () => {
  it('builds a header-safe slugged filename with the revision', () => {
    expect(ideaExportFilename(IDEA, 'md')).toBe('nicheiq-idea-glp-1-safeswitch-navigator-r2.md');
    expect(ideaExportFilename(IDEA, 'json')).toBe('nicheiq-idea-glp-1-safeswitch-navigator-r2.json');
  });

  it('falls back to a generic name and strips unsafe characters', () => {
    expect(ideaExportFilename({ idea_revision: 1, solution_name: 'Wei"rd\nName!!' }, 'md')).toBe(
      'nicheiq-idea-wei-rd-name-r1.md',
    );
    expect(ideaExportFilename({ idea_revision: 3 }, 'json')).toBe('nicheiq-idea-candidate-r3.json');
  });
});
