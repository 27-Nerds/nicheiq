/**
 * First-run tutorial state, served by /api/tutorial-progress (session-scoped).
 *
 * Chapters are per-surface: each triggers on that surface's first visit and completes
 * independently, so a reload mid-chapter never strands the user and someone who never
 * opens a sub-page never sees its chapter.
 */

export type TutorialChapterStatus = 'completed' | 'dismissed' | 'in_progress';

export interface TutorialChapterState {
  status: TutorialChapterStatus;
  step?: number;
  at: string;
}

export interface TutorialProgress {
  version: number;
  chapters: Record<string, TutorialChapterState>;
}

export const EMPTY_TUTORIAL_PROGRESS: TutorialProgress = { version: 1, chapters: {} };

/**
 * A chapter is "settled" once the user has completed it or explicitly declined it.
 * Only an unsettled chapter may auto-offer its invitation; a manual restart ignores this.
 */
export function chapterIsSettled(
  progress: TutorialProgress | null,
  chapterId: string,
): boolean {
  const status = progress?.chapters?.[chapterId]?.status;
  return status === 'completed' || status === 'dismissed';
}
