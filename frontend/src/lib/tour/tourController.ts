import type { Driver, DriveStep } from 'driver.js';
import { tourState } from './tourState.svelte';
import type { TutorialChapterStatus } from '$lib/types/tutorial';

/**
 * driver.js wrapper. Everything driver.js does NOT do for us lives here:
 *
 * - `driver.css` ships no `prefers-reduced-motion` guard, so animation and smooth
 *   scrolling are switched off here rather than in CSS.
 * - driver.js binds its reposition listener with `window.addEventListener('scroll', fn)`
 *   — no capture — so scrolling inside an overlay body never reaches it and the spotlight
 *   goes stale. A capture-phase listener calling the public `refresh()` fixes it.
 * - driver.js portals its overlay and popover to `<body>`. `isolateModalBackground`
 *   snapshots `document.body.children` when an overlay opens and marks everything else
 *   `inert`, which would kill the tour. Its documented escape hatch is `data-modal-exempt`.
 *
 * The library itself is dynamically imported so its ~8 kB never lands in the initial
 * bundle for the majority of users who are not taking a tour.
 */

export type TourStep = DriveStep;

/** Reported when a chapter ends, so the caller can persist the outcome. */
export type TourOutcome = { status: TutorialChapterStatus; step: number };

/**
 * Why a tour ended. This is the difference between "the user said no" and "the user
 * walked away" — collapsing them would mark a chapter settled and it would never offer
 * itself again, for someone who merely reloaded the page.
 */
type StopReason = 'dismissed' | 'navigation';

let instance: Driver | null = null;
let completed = false;
let stopReason: StopReason = 'dismissed';
let onOutcome: ((outcome: TourOutcome) => void) | null = null;

function refresh() {
  instance?.refresh();
}

/** driver.js recreates the popover per step, so re-tag on every render. */
function markExempt() {
  document
    .querySelectorAll('.driver-overlay, .driver-popover')
    .forEach((element) => element.setAttribute('data-modal-exempt', ''));
}

export function tourIsActive(): boolean {
  return instance !== null;
}

/** Re-measure the spotlight. Call when the page reflows under a running tour. */
export function refreshTour(): void {
  refresh();
}

/**
 * Advance past the current step if its anchor has vanished.
 *
 * driver.js only honours `skipMissingElement` when it TRANSITIONS to a step, never for
 * the step already showing — so a shortlist edit that removes the highlighted element
 * leaves a spotlight over empty space until the user clicks Next.
 */
export function skipIfAnchorGone(): void {
  if (!instance) return;
  const selector = instance.getActiveStep()?.element;
  if (typeof selector !== 'string') return;
  if (document.querySelector(selector)) return;
  if (instance.hasNextStep()) instance.moveNext();
  else stopTour({ reason: 'navigation' });
}

export async function startTour(
  steps: TourStep[],
  options: { onOutcome?: (outcome: TourOutcome) => void; startAt?: number } = {},
): Promise<void> {
  if (typeof window === 'undefined' || steps.length === 0) return;
  // Restarting from the header while a tour runs should replace it, not stack a second.
  stopTour({ silent: true });

  const [{ driver }] = await Promise.all([
    import('driver.js'),
    import('driver.js/dist/driver.css'),
  ]);

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  completed = false;
  stopReason = 'dismissed';
  onOutcome = options.onOutcome ?? null;

  instance = driver({
    steps,
    animate: !reducedMotion,
    smoothScroll: !reducedMotion,
    allowKeyboardControl: true,
    showProgress: steps.length > 1,
    popoverClass: 'niq-tour',
    // Config level, NOT per-step: driver resolves `doneBtnText` from the config when it
    // renders the final step, so a per-step override leaves the last button reading
    // "Next" and the tour never looks finished.
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: 'Done',
    // A target that never mounts must not strand the run. Both are 1.8.0 features.
    waitForElement: 2000,
    skipMissingElement: true,
    onPopoverRender: markExempt,
    // driver.js has its own scroll-into-view, but on this app's layout (body is
    // `overflow-y: auto` while <html> is the actual scrolling element) it does not fire
    // reliably, leaving the popover pinned to the bottom of the screen pointing at a
    // target hundreds of pixels below the fold. Scrolling here — BEFORE driver measures
    // — makes placement deterministic. Instant, not smooth: driver reads the rect
    // synchronously right after this, so a smooth scroll would still measure the old
    // position.
    onHighlightStarted: (element) => {
      if (!element) return;
      const box = element.getBoundingClientRect();
      const fullyVisible = box.top >= 0 && box.bottom <= window.innerHeight;
      if (fullyVisible) return;
      element.scrollIntoView({ behavior: 'auto', block: 'center', inline: 'nearest' });
    },
    onDoneClick: () => {
      completed = true;
      instance?.destroy();
    },
    onDestroyed: () => {
      const step = instance?.getActiveIndex() ?? 0;
      const report = onOutcome;
      const status: TutorialChapterStatus = completed
        ? 'completed'
        : stopReason === 'navigation'
          ? 'in_progress'
          : 'dismissed';
      // Null the instance BEFORE reporting: stopTour() re-enters through destroy().
      teardown();
      report?.({ status, step });
    },
  });

  window.addEventListener('scroll', refresh, true);
  window.addEventListener('resize', refresh);
  tourState.active = true;
  // `drive(index)` resumes a chapter the user left part-way through.
  instance.drive(options.startAt ?? 0);
  markExempt();
}

function teardown() {
  window.removeEventListener('scroll', refresh, true);
  window.removeEventListener('resize', refresh);
  tourState.active = false;
  instance = null;
  onOutcome = null;
  stopReason = 'dismissed';
}

/**
 * Ends the tour. Safe to call when none is running, and safe to call from `onDestroy`.
 *
 * `reason: 'navigation'` records the chapter as still in progress so it re-offers later —
 * use it for unmount, route change, and any programmatic abort. The default ('dismissed')
 * is for the user actively declining.
 *
 * `silent` suppresses the outcome callback entirely, for the restart case where the
 * replacement tour's outcome is the one that matters.
 */
export function stopTour(options: { silent?: boolean; reason?: StopReason } = {}): void {
  const active = instance;
  if (!active) return;
  if (options.silent) onOutcome = null;
  if (options.reason) stopReason = options.reason;
  // onDestroyed runs teardown(); this is just the trigger.
  active.destroy();
}
