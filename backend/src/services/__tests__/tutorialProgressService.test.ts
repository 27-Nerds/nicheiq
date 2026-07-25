import { describe, expect, it } from 'vitest';
import {
  TutorialChapterPatchSchema,
  parseTutorialProgress,
} from '../tutorialProgressService.js';

describe('parseTutorialProgress', () => {
  it('treats null and non-objects as nothing seen', () => {
    for (const raw of [null, undefined, 'x', 3, [], true] as never[]) {
      expect(parseTutorialProgress(raw)).toEqual({ version: 1, chapters: {} });
    }
  });

  it('reads a well-formed blob', () => {
    expect(parseTutorialProgress({
      version: 1,
      chapters: {
        'job-shortlist': { status: 'completed', at: '2026-07-25T00:00:00.000Z' },
        compare: { status: 'in_progress', step: 2, at: '2026-07-25T00:00:01.000Z' },
      },
    })).toEqual({
      version: 1,
      chapters: {
        'job-shortlist': { status: 'completed', at: '2026-07-25T00:00:00.000Z' },
        compare: { status: 'in_progress', step: 2, at: '2026-07-25T00:00:01.000Z' },
      },
    });
  });

  it('drops unusable entries instead of throwing — a corrupt row must not break the page', () => {
    const parsed = parseTutorialProgress({
      chapters: {
        good: { status: 'completed', at: 'now' },
        'Bad-Key': { status: 'completed', at: 'now' },
        badStatus: { status: 'exploded', at: 'now' },
        notAnObject: 'completed',
        nested: null,
      },
    });
    expect(Object.keys(parsed.chapters)).toEqual(['good']);
  });

  it('defaults a missing timestamp rather than dropping the chapter', () => {
    const parsed = parseTutorialProgress({ chapters: { good: { status: 'dismissed' } } });
    expect(parsed.chapters.good.status).toBe('dismissed');
    expect(parsed.chapters.good.at).toBe(new Date(0).toISOString());
  });

  it('ignores a non-integer step', () => {
    const parsed = parseTutorialProgress({
      chapters: { good: { status: 'in_progress', step: 1.5, at: 'now' } },
    });
    expect(parsed.chapters.good.step).toBeUndefined();
  });
});

describe('TutorialChapterPatchSchema', () => {
  it('accepts a kebab-case chapter with a known status', () => {
    expect(TutorialChapterPatchSchema.parse({
      chapter: 'job-shortlist',
      status: 'completed',
    })).toEqual({ chapter: 'job-shortlist', status: 'completed' });
  });

  it('rejects chapter ids outside the allowed key space', () => {
    for (const chapter of ['Job', 'job_shortlist', '1job', 'job shortlist', '', 'a'.repeat(65)]) {
      expect(TutorialChapterPatchSchema.safeParse({ chapter, status: 'completed' }).success)
        .toBe(false);
    }
  });

  it('rejects an unknown status and an out-of-range step', () => {
    expect(TutorialChapterPatchSchema.safeParse({ chapter: 'ok', status: 'finished' }).success)
      .toBe(false);
    expect(TutorialChapterPatchSchema.safeParse({ chapter: 'ok', status: 'in_progress', step: -1 }).success)
      .toBe(false);
    expect(TutorialChapterPatchSchema.safeParse({ chapter: 'ok', status: 'in_progress', step: 101 }).success)
      .toBe(false);
  });
});
