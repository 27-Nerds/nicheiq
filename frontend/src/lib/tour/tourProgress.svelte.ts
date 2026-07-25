import {
  EMPTY_TUTORIAL_PROGRESS,
  chapterIsSettled,
  type TutorialChapterStatus,
  type TutorialProgress,
} from '$lib/types/tutorial';

/**
 * Which tutorial chapters this user has seen.
 *
 * Server-backed (see `/api/tutorial-progress`) rather than localStorage, so the tutorial
 * doesn't re-offer itself on every new browser. Fetched once per page load, lazily — it
 * is only needed on the job and selection surfaces.
 *
 * FAILS CLOSED on a fetch error: an unreachable backend means we do NOT know whether the
 * user has seen a chapter, and re-showing a tutorial someone already dismissed is worse
 * than not showing one. `offersChapter()` returns false until a load succeeds.
 */

let _progress = $state<TutorialProgress | null>(null);
let _loaded = $state(false);
let _inFlight: Promise<void> | null = null;

async function fetchProgress(): Promise<void> {
  try {
    const response = await fetch('/api/tutorial-progress');
    if (!response.ok) return;
    _progress = (await response.json()) as TutorialProgress;
  } catch {
    // Offline or backend down — stay unloaded, so nothing is offered.
  } finally {
    _loaded = true;
    _inFlight = null;
  }
}

export const tourProgress = {
  get loaded() {
    return _loaded;
  },
  get progress() {
    return _progress ?? EMPTY_TUTORIAL_PROGRESS;
  },

  /** Idempotent: concurrent callers share one request. */
  load(): Promise<void> {
    if (_loaded) return Promise.resolve();
    _inFlight ??= fetchProgress();
    return _inFlight;
  },

  /**
   * Whether a chapter's invitation may be offered automatically. False while unloaded,
   * and false once the user has completed or explicitly declined it. A manual restart
   * from the page header bypasses this entirely.
   */
  offersChapter(chapterId: string): boolean {
    if (!_loaded || !_progress) return false;
    return !chapterIsSettled(_progress, chapterId);
  },

  /**
   * Persist a chapter outcome. Optimistic: the local copy updates immediately so the
   * invitation cannot flash back while the request is in flight, and a failed write is
   * swallowed — the worst case is the chapter offers itself again next session.
   */
  async record(chapterId: string, status: TutorialChapterStatus, step?: number): Promise<void> {
    const previous = _progress;
    _progress = {
      version: previous?.version ?? EMPTY_TUTORIAL_PROGRESS.version,
      chapters: {
        ...(previous?.chapters ?? {}),
        [chapterId]: { status, ...(step !== undefined ? { step } : {}), at: new Date().toISOString() },
      },
    };
    try {
      await fetch('/api/tutorial-progress', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: chapterId, status, ...(step !== undefined ? { step } : {}) }),
      });
    } catch {
      // Keep the optimistic local state; it self-heals on the next successful load.
    }
  },
};
