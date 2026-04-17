<script lang="ts">
  import type { DiscoverySlide } from '$lib/data/previewPlaceholders';

  interface Props {
    slide: DiscoverySlide;
    niche?: string;
    jobStatus?: string;
    queuePosition?: number;
    totalQueued?: number;
  }

  let { slide, niche = '', jobStatus = 'RUNNING', queuePosition, totalQueued }: Props = $props();

  const isQueued = $derived(jobStatus === 'QUEUED' || jobStatus === 'PENDING');

  /** Wrap matching substrings in <strong> tags */
  function boldPhrases(text: string, phrases?: string[]): string {
    if (!phrases?.length) return text;
    let result = text;
    for (const phrase of phrases) {
      const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      result = result.replace(new RegExp(escaped, 'g'), `<strong>${phrase}</strong>`);
    }
    return result;
  }
</script>

<div class="slide-content slide-content--{slide.type}">
  {#if slide.type === 'waiting'}
    <!-- Spinner: SVG arc, not generic CSS border-top -->
    <svg class="spinner" viewBox="0 0 44 44" fill="none" aria-hidden="true">
      <circle cx="22" cy="22" r="20" stroke="var(--dg-border)" stroke-width="4" />
      <path
        d="M22 2 A20 20 0 0 1 42 22"
        stroke="var(--dg-accent)"
        stroke-width="4"
        stroke-linecap="round"
      />
    </svg>

    {#if niche}
      <span class="niche-pill">{niche}</span>
    {/if}

    <h1 class="heading heading--waiting">
      {#if isQueued}
        Your niche is<br /><em>queued for research.</em>
      {:else}
        {slide.headingBefore}<br /><em>{slide.headingEmphasis}</em>
      {/if}
    </h1>

    <p class="body body--waiting">
      {#if isQueued}
        We'll start as soon as a slot opens up.
      {:else}
        {@html boldPhrases(slide.body, slide.bodyBoldPhrases)}
      {/if}
    </p>

    {#if isQueued && queuePosition}
      <p class="queue-position">
        Position <span class="queue-num">{queuePosition}</span>
        {#if totalQueued}
          of <span class="queue-num">{totalQueued}</span>
        {/if}
        in queue
      </p>
    {/if}

  {:else if slide.type === 'edge'}
    <div class="accent-label">{slide.accentLabel}</div>
    <h2 class="heading heading--phase">
      {slide.headingBefore}<br /><em>{slide.headingEmphasis}</em>
    </h2>
    <p class="body body--phase">
      {@html boldPhrases(slide.body, slide.bodyBoldPhrases)}
    </p>
    {#if slide.comparePills}
      <div class="compare">
        <div class="pill pill--without"><span class="pill-marker">&mdash;</span> {slide.comparePills.without}</div>
        <div class="pill pill--with"><svg class="pill-check" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M2.5 6l2.5 2.5L9.5 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>{slide.comparePills.withNicheIQ}</div>
      </div>
    {/if}

  {:else}
    <!-- step type -->
    <div class="accent-label">{slide.accentLabel}</div>
    {#if slide.stepSymbol && slide.stepName}
      <div class="step-indicator">{slide.stepSymbol}&ensp;{slide.stepName}</div>
    {/if}
    <h2 class="heading heading--phase">
      {slide.headingBefore}<br /><em>{slide.headingEmphasis}</em>
    </h2>
    <p class="body body--phase">
      {@html boldPhrases(slide.body, slide.bodyBoldPhrases)}
    </p>
    {#if slide.comparePills}
      <div class="compare">
        <div class="pill pill--without"><span class="pill-marker">&mdash;</span> {slide.comparePills.without}</div>
        <div class="pill pill--with"><svg class="pill-check" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M2.5 6l2.5 2.5L9.5 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>{slide.comparePills.withNicheIQ}</div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .slide-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: 100px 40px 60px;
    text-align: center;
  }

  /* ── Spinner (SVG arc) ── */
  .spinner {
    width: 44px;
    height: 44px;
    margin-bottom: 32px;
  }

  .spinner path {
    transform-origin: center;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner path { animation: none; }
  }

  /* ── Niche pill ── */
  .niche-pill {
    background: var(--dg-green-bg);
    color: var(--dg-green-text);
    font-size: 13px;
    font-weight: 600;
    padding: 5px 16px;
    border-radius: 20px;
    margin-bottom: 24px;
    display: inline-block;
  }

  /* ── Headings ── */
  .heading {
    font-family: var(--dg-font-heading);
    font-weight: 700;
    line-height: 1.12;
    color: var(--dg-text);
    margin: 0 0 20px 0;
    text-wrap: balance;
  }

  .heading :global(em) {
    color: var(--dg-accent);
    font-weight: 800;
    font-style: normal;
  }

  .heading--waiting {
    font-size: clamp(30px, 4.5vw, 50px);
    font-weight: 800;
    letter-spacing: -0.04em;
    line-height: 1.18;
  }

  .heading--phase {
    font-size: clamp(34px, 5.5vw, 68px);
    letter-spacing: -0.03em;
    max-width: 680px;
    margin-bottom: 24px;
  }

  /* ── Accent label ── */
  .accent-label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--dg-accent);
    background: rgba(240, 96, 48, 0.1);
    border: 1px solid rgba(240, 96, 48, 0.2);
    padding: 3px 10px;
    border-radius: 20px;
    display: inline-block;
    margin-bottom: 6px;
  }

  /* ── Step indicator ── */
  .step-indicator {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--dg-muted);
    margin-bottom: 28px;
  }

  /* ── Body text ── */
  .body {
    font-size: 16px;
    line-height: 1.75;
    color: var(--dg-muted);
    max-width: 420px;
    margin: 0 auto 36px;
    text-align: left;
    text-wrap: pretty;
  }

  .body :global(strong) {
    color: var(--dg-text);
  }

  .body--waiting {
    margin-bottom: 36px;
    text-align: center;
    max-width: 380px;
  }

  /* ── Queue position ── */
  .queue-position {
    font-size: 14px;
    color: var(--dg-muted);
    font-weight: 500;
  }

  .queue-num {
    font-variant-numeric: tabular-nums;
    color: var(--dg-text);
    font-weight: 600;
  }

  /* ── Compare pills ── */
  .compare {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 680px;
    width: 100%;
  }

  .pill {
    font-size: 13px;
    padding: 7px 18px;
    border-radius: 20px;
    font-weight: 500;
    line-height: 1.5;
    text-align: left;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .pill--without {
    background: var(--dg-bg2);
    color: var(--dg-muted);
  }

  .pill-marker {
    color: var(--dg-muted);
    opacity: 0.5;
  }

  .pill--with {
    background: var(--dg-green-bg);
    color: var(--dg-green-text);
    font-weight: 600;
  }

  .pill-check {
    width: 12px;
    height: 12px;
    flex-shrink: 0;
  }

  /* ── Responsive ── */
  @media (max-width: 600px) {
    .slide-content {
      padding: 88px 24px 52px;
    }
  }
</style>
