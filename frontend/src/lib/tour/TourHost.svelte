<script lang="ts">
  import { onDestroy, tick } from "svelte";
  import { beforeNavigate } from "$app/navigation";
  import { page } from "$app/state";
  import { chatPanel, type ChatWindowState } from "$lib/stores/chatPanel.svelte";
  import TourInvitation from "./TourInvitation.svelte";
  import { TOUR_CHAPTERS, TOUR_MIN_VIEWPORT } from "./chapters";
  import {
    skipIfAnchorGone,
    refreshTour,
    startTour,
    stopTour,
    type TourOutcome,
  } from "./tourController";
  import { tourLauncher } from "./tourLauncher.svelte";
  import { tourProgress } from "./tourProgress.svelte";

  /**
   * Mounts one tutorial chapter on one surface.
   *
   * Offers the chapter's invitation on first visit, runs the tour on accept, and records
   * the outcome. Everything about WHEN is decided here; the chapter file owns WHAT.
   */
  interface Props {
    /** Key into TOUR_CHAPTERS. */
    chapter: string;
    /** The admin decision-tools grant. The tutorial exists only for those users. */
    enabled: boolean;
    /** Page data has landed and the surface has settled. Chapter-specific. */
    ready: boolean;
    /**
     * A transient state is competing for attention (a banner, an open overlay, a
     * pending mutation). The invitation waits rather than stacking on top of it.
     */
    deferred?: boolean;
    /** The surface is unusable for the tour's premise — read-only, conflicted, errored. */
    suppressed?: boolean;
    /** Runs before the tour starts; used to switch the compare view for the fit step. */
    onBeforeStart?: () => void | Promise<void>;
    /** Runs after it ends, however it ended — the counterpart that restores whatever
     *  `onBeforeStart` changed, so the page is left as the user had it. */
    onAfterEnd?: () => void;
    /** A value that, when it changes, means the page reflowed under a running tour. */
    reflowKey?: unknown;
  }

  let {
    chapter,
    enabled,
    ready,
    deferred = false,
    suppressed = false,
    onBeforeStart,
    onAfterEnd,
    reflowKey,
  }: Props = $props();

  const definition = $derived(TOUR_CHAPTERS[chapter]);

  let inviteVisible = $state(false);
  let running = $state(false);
  /** Restored after the tour ends — see the chatPanel note in `run()`. */
  let priorChatState: ChatWindowState | null = null;
  /** Plain `let`, not `$state`: a write-only guard read inside the same effect that
   *  writes it would re-trigger that effect. */
  let inviteSettled = false;
  let inviteTimer: ReturnType<typeof setTimeout> | null = null;

  const wideEnough = $derived.by(() => {
    void reflowKey;
    if (typeof window === "undefined") return false;
    return window.matchMedia(`(min-width: ${TOUR_MIN_VIEWPORT}px)`).matches;
  });

  const mayOffer = $derived(
    enabled
    && !suppressed
    && !deferred
    && ready
    && wideEnough
    && Boolean(definition)
    && tourProgress.loaded
    && tourProgress.offersChapter(chapter),
  );

  /** Resume point when a chapter was left part-way through. */
  const resumeStep = $derived.by(() => {
    const state = tourProgress.progress.chapters[chapter];
    return state?.status === "in_progress" ? (state.step ?? 0) : 0;
  });

  // Load progress once, but only for users who can actually see the tutorial.
  $effect(() => {
    if (!enabled) return;
    void tourProgress.load();
  });

  // The invitation waits for the surface to settle. The delay covers the entrance
  // transitions that run for a frame or two after data lands — measuring the popover
  // against a mid-transition rect puts it visibly askew.
  $effect(() => {
    if (!mayOffer || running || inviteSettled) {
      if (!mayOffer && inviteTimer) {
        clearTimeout(inviteTimer);
        inviteTimer = null;
        inviteVisible = false;
      }
      return;
    }
    if (inviteTimer) return;
    inviteTimer = setTimeout(() => {
      inviteTimer = null;
      inviteVisible = true;
    }, 600);
  });

  // A running tour must re-measure when the page reflows beneath it, and must not leave
  // a spotlight over an element that has since been removed.
  $effect(() => {
    void reflowKey;
    if (!running) return;
    void tick().then(() => {
      skipIfAnchorGone();
      refreshTour();
    });
  });

  // The surface stopped supporting the tour's premise mid-run (status changed, a
  // shortlist conflict landed). Stop rather than spotlight an inert subtree.
  $effect(() => {
    if (running && suppressed) stopTour({ reason: "navigation" });
  });

  async function run(startAt = 0) {
    if (!definition) return;
    inviteVisible = false;
    inviteSettled = true;

    // The analyst window defaults to `docked` for every user, occupying the bottom-right
    // corner — exactly where the shortlist-dock and commit-strip popovers land. Closing
    // it is what the workbench itself does when it needs the corner; restore afterwards.
    priorChatState = chatPanel.state;
    if (chatPanel.isOpen) chatPanel.close();

    await onBeforeStart?.();
    await tick();

    running = true;
    await startTour(definition.steps, {
      startAt,
      onOutcome: ({ status, step }: TourOutcome) => {
        running = false;
        restoreChat();
        onAfterEnd?.();
        void tourProgress.record(chapter, status, status === "in_progress" ? step : undefined);
      },
    });
  }

  function restoreChat() {
    if (!priorChatState) return;
    if (priorChatState === "docked") chatPanel.dock();
    else if (priorChatState === "expanded") chatPanel.expand();
    priorChatState = null;
  }

  function decline() {
    inviteVisible = false;
    inviteSettled = true;
    void tourProgress.record(chapter, "dismissed");
  }

  // A manual restart ignores whether the chapter was already settled, and always starts
  // from the beginning — the user asked to see it again, not to resume.
  onDestroy(tourLauncher.register(() => void run(0)));

  // Leaving the surface ends the chapter as still-in-progress, so it re-offers later
  // rather than being marked declined. A same-route replaceState (the compare view
  // switch) must NOT trip this.
  beforeNavigate(({ to }) => {
    if (!running) return;
    if (to?.url.pathname === page.url.pathname) return;
    stopTour({ reason: "navigation" });
  });

  onDestroy(() => {
    if (inviteTimer) clearTimeout(inviteTimer);
    // driver.js portals to <body>; an un-destroyed tour outlives this component.
    stopTour({ reason: "navigation" });
    restoreChat();
    onAfterEnd?.();
  });
</script>

{#if inviteVisible && definition}
  <TourInvitation
    heading={definition.invitation.heading}
    body={resumeStep > 0
      ? `Pick up where you left off, at step ${resumeStep + 1} of ${definition.steps.length}.`
      : definition.invitation.body}
    onAccept={() => void run(resumeStep)}
    onDecline={decline}
  />
{/if}
