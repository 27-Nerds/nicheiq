import { z } from 'zod';
import { Prisma } from '@prisma/client';
import { prisma } from './db.js';

/**
 * First-run tutorial progress.
 *
 * Stored as one JSON blob on User, but written ONE CHAPTER AT A TIME through
 * `recordTutorialChapter` — read-modify-write of the whole map would let two open tabs
 * (the job page and a selection sub-page, which is the normal case here) silently
 * discard each other's progress.
 */

export const TUTORIAL_PROGRESS_VERSION = 1;

/** `completed` = ran to the end. `dismissed` = declined the invitation or bailed out. */
export const TutorialChapterStatusSchema = z.enum(['completed', 'dismissed', 'in_progress']);

export const TutorialChapterIdSchema = z
  .string()
  .min(1)
  .max(64)
  // Chapter ids are authored in the frontend and echoed straight back into the JSON
  // blob, so constrain the key space rather than storing arbitrary client strings.
  .regex(/^[a-z][a-z0-9-]*$/, 'Chapter id must be lowercase kebab-case');

export const TutorialChapterPatchSchema = z.object({
  chapter: TutorialChapterIdSchema,
  status: TutorialChapterStatusSchema,
  /** Last step reached — only meaningful for `in_progress`. */
  step: z.number().int().min(0).max(100).optional(),
});

export type TutorialChapterPatch = z.infer<typeof TutorialChapterPatchSchema>;

export interface TutorialChapterState {
  status: z.infer<typeof TutorialChapterStatusSchema>;
  step?: number;
  at: string;
}

export interface TutorialProgress {
  version: number;
  chapters: Record<string, TutorialChapterState>;
}

const EMPTY: TutorialProgress = { version: TUTORIAL_PROGRESS_VERSION, chapters: {} };

/**
 * Tolerant read. Anything unrecognised (legacy shape, hand-edited row, null) degrades to
 * "nothing seen yet" rather than throwing — a corrupt blob must never break the job page.
 */
export function parseTutorialProgress(raw: Prisma.JsonValue | null | undefined): TutorialProgress {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ...EMPTY, chapters: {} };
  const record = raw as Record<string, unknown>;
  const chapters = record.chapters;
  if (!chapters || typeof chapters !== 'object' || Array.isArray(chapters)) {
    return { ...EMPTY, chapters: {} };
  }
  const parsed: Record<string, TutorialChapterState> = {};
  for (const [key, value] of Object.entries(chapters as Record<string, unknown>)) {
    if (!TutorialChapterIdSchema.safeParse(key).success) continue;
    if (!value || typeof value !== 'object' || Array.isArray(value)) continue;
    const entry = value as Record<string, unknown>;
    const status = TutorialChapterStatusSchema.safeParse(entry.status);
    if (!status.success) continue;
    parsed[key] = {
      status: status.data,
      ...(typeof entry.step === 'number' && Number.isInteger(entry.step) ? { step: entry.step } : {}),
      at: typeof entry.at === 'string' ? entry.at : new Date(0).toISOString(),
    };
  }
  return { version: TUTORIAL_PROGRESS_VERSION, chapters: parsed };
}

export async function getTutorialProgress(userId: string): Promise<TutorialProgress> {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { tutorialProgress: true },
  });
  return parseTutorialProgress(user?.tutorialProgress);
}

/**
 * Merge one chapter into the stored map, in a single statement so a concurrent tab
 * cannot clobber a chapter a read-modify-write in JS would have dropped.
 *
 * Built from `||` (shallow object merge), NOT `jsonb_set`: `jsonb_set` with
 * create_missing=true only creates the LAST key of the path, so on the very first write
 * — when there is no `chapters` object yet — a `{chapters, <id>}` path silently returns
 * the row unchanged. `||` creates each level.
 *
 * `jsonb_typeof` guards a corrupt row: `||` errors on a scalar or array, so anything
 * that isn't an object is replaced wholesale rather than throwing.
 */
export async function recordTutorialChapter(
  userId: string,
  patch: TutorialChapterPatch,
): Promise<TutorialProgress> {
  const entry: TutorialChapterState = {
    status: patch.status,
    ...(patch.step !== undefined ? { step: patch.step } : {}),
    at: new Date().toISOString(),
  };

  const rows = await prisma.$queryRaw<{ tutorialProgress: Prisma.JsonValue }[]>`
    UPDATE "User"
    SET "tutorialProgress" =
      CASE
        WHEN jsonb_typeof("tutorialProgress") = 'object' THEN "tutorialProgress"
        ELSE '{}'::jsonb
      END
      || jsonb_build_object('version', ${TUTORIAL_PROGRESS_VERSION}::int)
      || jsonb_build_object(
        'chapters',
        CASE
          WHEN jsonb_typeof("tutorialProgress" -> 'chapters') = 'object'
            THEN "tutorialProgress" -> 'chapters'
          ELSE '{}'::jsonb
        END
        || jsonb_build_object(${patch.chapter}::text, ${JSON.stringify(entry)}::jsonb)
      )
    WHERE "id" = ${userId}
    RETURNING "tutorialProgress"
  `;

  if (rows.length === 0) {
    const notFound = new Error('User not found') as Error & { code?: string };
    notFound.code = 'P2025';
    throw notFound;
  }
  return parseTutorialProgress(rows[0].tutorialProgress);
}
