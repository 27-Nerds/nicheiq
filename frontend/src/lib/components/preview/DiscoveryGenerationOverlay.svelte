<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { cubicOut, cubicIn, cubicInOut } from 'svelte/easing';
  import { beforeNavigate } from '$app/navigation';
  import { portal } from '$lib/actions/portal';
  import { DISCOVERY_FULLPAGE_SLIDES, type DiscoverySlide } from '$lib/data/previewPlaceholders';
  import DiscoverySlideContent from './DiscoverySlideContent.svelte';

  interface Props {
    niche: string;
    jobStatus: string;
    currentStage?: number;
    progressPercent: number;
    stagesCompleted: number;
    totalStages: number;
    currentStageName: string;
    queuePosition?: number;
    totalQueued?: number;
    onCancel: () => void;
    cancelling: boolean;
    cancelError?: string;
  }

  let {
    niche,
    jobStatus,
    currentStage,
    progressPercent,
    stagesCompleted,
    totalStages,
    currentStageName,
    queuePosition,
    totalQueued,
    onCancel,
    cancelling,
    cancelError = '',
  }: Props = $props();

  const slides = DISCOVERY_FULLPAGE_SLIDES;
  const totalSlides = slides.length;

  // ── Slide state ──
  let currentSlide = $state(initSlideIndex());
  let direction = $state<'forward' | 'backward'>('forward');
  let isHovered = $state(false);
  let hasInteracted = $state(false);
  let useInstantTransition = $state(false);

  // Track last stage-sync to avoid re-triggering
  let lastSyncedStage = $state<number | undefined>(undefined);

  function initSlideIndex(): number {
    if (currentStage == null) return 0;
    // Find the last slide whose relatedStage <= currentStage
    let best = 0;
    for (let i = slides.length - 1; i >= 0; i--) {
      if (slides[i].relatedStage != null && slides[i].relatedStage! <= currentStage!) {
        best = i;
        break;
      }
    }
    return best;
  }

  // ── Auto-advance timer ──
  $effect(() => {
    if (isHovered) return;

    const durationMs = slides[currentSlide]?.duration ?? 6_000;
    const id = setInterval(() => {
      useInstantTransition = false;
      direction = 'forward';
      currentSlide = (currentSlide + 1) % totalSlides;
    }, durationMs);

    return () => clearInterval(id);
  });

  // ── Stage-sync: SSE stage changes jump to matching slide ──
  $effect(() => {
    if (currentStage == null) return;
    if (currentStage === lastSyncedStage) return;

    const matchIndex = slides.findIndex((s) => s.relatedStage === currentStage);
    if (matchIndex >= 0) {
      lastSyncedStage = currentStage;
      useInstantTransition = false;
      direction = matchIndex > currentSlide ? 'forward' : 'backward';
      currentSlide = matchIndex;
    }
  });

  // ── Body scroll lock (follows CategorySheet.svelte pattern) ──
  $effect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  });

  // Safety net: restore scroll on SvelteKit navigation
  beforeNavigate(() => {
    document.body.style.overflow = '';
  });

  // ── Navigation ──
  function goToSlide(index: number, instant = false) {
    useInstantTransition = instant;
    direction = index > currentSlide ? 'forward' : 'backward';
    currentSlide = index;
    hasInteracted = true;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowLeft') {
      goToSlide((currentSlide - 1 + totalSlides) % totalSlides, true);
    } else if (e.key === 'ArrowRight') {
      goToSlide((currentSlide + 1) % totalSlides, true);
    } else if (e.key === 'Escape') {
      onCancel();
    }
  }

  // ── Derived ──
  const activeSlide = $derived(slides[currentSlide]);
  const slideBg = $derived(currentSlide % 2 === 0 ? 'var(--dg-bg)' : 'var(--dg-bg2)');
  const isRunning = $derived(jobStatus === 'RUNNING');

  // Fly transition params
  const flyDuration = $derived(useInstantTransition ? 0 : 250);
  const flyX = $derived(direction === 'forward' ? 20 : -20);
</script>

<div
  class="overlay"
  use:portal
  transition:fade={{ duration: 300, easing: cubicOut }}
  role="dialog"
  aria-label="Research in progress"
  aria-modal="true"
  tabindex="-1"
  onkeydown={handleKeydown}
  onmouseenter={() => (isHovered = true)}
  onmouseleave={() => (isHovered = false)}
>
  <!-- ═══ HEADER ═══ -->
  <header class="overlay-header">
    <div class="logo">Niche<span class="logo-accent">IQ</span></div>
    <div class="header-right">
      <span class="status-dot"></span>
      <span class="status-label">Research in progress</span>
      {#if cancelError}
        <span class="cancel-error">{cancelError}</span>
      {/if}
      <button
        class="cancel-btn"
        onclick={onCancel}
        disabled={cancelling}
        aria-label={cancelling ? 'Cancelling...' : 'Cancel research'}
      >
        {cancelling ? 'Cancelling...' : 'Cancel'}
      </button>
    </div>
  </header>

  <!-- ═══ PROGRESS BAR ═══ -->
  {#if isRunning}
    <div class="progress-track">
      <div class="progress-fill" style:width="{progressPercent ?? 0}%"></div>
    </div>
    <p class="progress-label">
      Stage {stagesCompleted} of {totalStages}{#if currentStageName}: {currentStageName}{/if}
    </p>
  {/if}

  <!-- ═══ SLIDE VIEWPORT ═══ -->
  <div class="slide-viewport" style:background={slideBg}>
    {#key currentSlide}
      <div
        class="slide-pane"
        in:fly={{ x: flyX, duration: flyDuration, easing: cubicInOut }}
        out:fade={{ duration: flyDuration > 0 ? 150 : 0 }}
        style:background={slideBg}
      >
        <DiscoverySlideContent
          slide={activeSlide}
          {niche}
          {jobStatus}
          {queuePosition}
          {totalQueued}
        />
      </div>
    {/key}
  </div>

  <!-- ═══ BOTTOM CONTROLS ═══ -->
  <div class="bottom-controls">
    <div class="slide-dots" role="tablist" aria-label="Slide navigation">
      {#each slides as _, i}
        <button
          class="slide-dot"
          class:active={i === currentSlide}
          role="tab"
          aria-selected={i === currentSlide}
          aria-label="Go to slide {i + 1}"
          onclick={() => goToSlide(i)}
        ></button>
      {/each}
    </div>
    <span class="slide-counter">{currentSlide + 1} / {totalSlides}</span>
  </div>


</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    overflow: hidden;

    /* Scoped palette — derived from app design tokens */
    --dg-bg: var(--color-bg-base, #FAFAFA);
    --dg-bg2: var(--color-bg-surface, #F5F5F5);
    --dg-text: var(--color-text-primary, #18181B);
    --dg-muted: var(--color-text-muted, #71717A);
    --dg-accent: var(--color-accent, #F06030);
    --dg-green-bg: var(--color-success-subtle, rgba(34, 197, 94, 0.08));
    --dg-green-text: var(--color-success-dark, #16A34A);
    --dg-border: var(--color-border, rgba(0, 0, 0, 0.07));
    --dg-font-heading: var(--font-display, "Plus Jakarta Sans", system-ui, sans-serif);

    background: var(--dg-bg);
    background-image: radial-gradient(circle at 1px 1px, var(--dg-border) 1px, transparent 0);
    background-size: 24px 24px;
    color: var(--dg-text);
    font-family: var(--font-body, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  /* ── HEADER ── */
  .overlay-header {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 40px;
    background: rgba(250, 250, 250, 0.88);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    flex-shrink: 0;
  }

  .logo {
    font-family: var(--dg-font-heading);
    font-size: 20px;
    font-weight: 700;
    font-synthesis: none;
  }

  .logo-accent {
    color: var(--dg-accent);
    font-style: italic;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 500;
    color: var(--dg-muted);
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--dg-accent);
    animation: pulse-once 1.6s ease-in-out 1 forwards;
    flex-shrink: 0;
  }

  @keyframes pulse-once {
    0% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.3; transform: scale(0.75); }
    100% { opacity: 1; transform: scale(1); }
  }

  @media (prefers-reduced-motion: reduce) {
    .status-dot { animation: none; }
  }

  .status-label {
    white-space: nowrap;
  }

  .cancel-error {
    color: #dc2626;
    font-size: 11px;
    margin-left: 8px;
  }

  .cancel-btn {
    margin-left: 16px;
    padding: 6px 14px;
    border: 1px solid var(--dg-border);
    border-radius: 6px;
    background: transparent;
    color: var(--dg-muted);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
  }

  .cancel-btn:hover {
    background: rgba(0, 0, 0, 0.04);
    color: var(--dg-text);
    border-color: rgba(0, 0, 0, 0.15);
  }

  .cancel-btn:active {
    transform: scale(0.97);
  }

  .cancel-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── PROGRESS BAR ── */
  .progress-track {
    height: 3px;
    background: var(--dg-border);
    flex-shrink: 0;
  }

  .progress-fill {
    height: 100%;
    background: var(--dg-accent);
    transition: width 100ms linear;
  }

  .progress-label {
    font-family: var(--font-mono, "JetBrains Mono", ui-monospace, monospace);
    font-size: 11px;
    color: var(--dg-muted);
    padding: 6px 40px;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  /* ── SLIDE VIEWPORT ── */
  .slide-viewport {
    flex: 1;
    position: relative;
    overflow: hidden;
    min-height: 0;
  }

  .slide-pane {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* ── BOTTOM CONTROLS ── */
  .bottom-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 40px;
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    background: var(--dg-bg);
    flex-shrink: 0;
    position: relative;
    z-index: 2;
  }

  .slide-dots {
    display: flex;
    gap: 8px;
  }

  .slide-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: none;
    background: var(--dg-border);
    cursor: pointer;
    padding: 0;
    position: relative;
    transition: background-color 150ms ease;
  }

  /* Expanded hit target via pseudo-element */
  .slide-dot::before {
    content: '';
    position: absolute;
    inset: -12px;
  }

  .slide-dot:hover {
    background: var(--dg-muted);
  }

  .slide-dot.active {
    background: var(--dg-accent);
  }

  .slide-dot:active {
    transform: scale(0.97);
  }

  .slide-dot:focus-visible {
    outline: 2px solid var(--dg-accent);
    outline-offset: 4px;
  }

  .slide-counter {
    font-family: var(--font-mono, "JetBrains Mono", ui-monospace, monospace);
    font-size: 11px;
    color: var(--dg-muted);
    letter-spacing: 0.05em;
    font-variant-numeric: tabular-nums;
  }

  /* ── RESPONSIVE ── */
  @media (max-width: 600px) {
    .overlay-header {
      padding: 16px 24px;
    }

    .progress-label {
      padding: 6px 24px;
    }

    .bottom-controls {
      padding: 16px 24px;
    }
  }
</style>
