<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { recordPublicExperimentEvent } from '$lib/api';
  import type { PublicExperimentEventType } from '$lib/types/selectionExperiment';

  let { data } = $props();
  let ctaRegion = $state<HTMLElement | null>(null);
  let exposureRecorded = $state(false);
  let disclosed = $state(false);
  let submitting = $state(false);
  let trackingError = $state('');

  const artifact = $derived(data.test?.artifact);

  onMount(() => {
    if (!data.test || !ctaRegion) return;

    if (!('IntersectionObserver' in window)) {
      void recordExposure();
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.6)) {
        void recordExposure();
        observer.disconnect();
      }
    }, { threshold: 0.6 });
    observer.observe(ctaRegion);
    return () => observer.disconnect();
  });

  async function emit(type: PublicExperimentEventType) {
    if (!data.test) return;
    await recordPublicExperimentEvent(data.publicToken, {
      eventId: crypto.randomUUID(),
      viewToken: data.test.viewToken,
      type,
      occurredAt: new Date().toISOString(),
    });
  }

  async function recordExposure() {
    if (exposureRecorded) return;
    try {
      await emit('STIMULUS_EXPOSED');
      exposureRecorded = true;
    } catch {
      trackingError = 'Response tracking is temporarily unavailable.';
    }
  }

  async function showInterest() {
    if (submitting || disclosed) return;
    submitting = true;
    trackingError = '';
    try {
      await recordExposure();
      await emit('CTA_CLICKED');
    } catch {
      trackingError = 'Your response could not be recorded, but no account or payment was created.';
    } finally {
      disclosed = true;
      submitting = false;
      await tick();
      void emit('FAKE_DOOR_DISCLOSED').catch(() => undefined);
    }
  }
</script>

<svelte:head>
  <title>{artifact ? `${artifact.headline} · Concept test` : 'Concept test unavailable'}</title>
  <meta name="description" content={artifact?.promise ?? 'This concept test is no longer collecting responses.'} />
  <meta name="robots" content="noindex, nofollow" />
  <meta name="referrer" content="no-referrer" />
</svelte:head>

<main class="test-shell">
  <header class="test-header">
    <a href="/" aria-label="NicheIQ home">
      <img src="/niche-logo-beta.svg" alt="NicheIQ" />
    </a>
    <span>Concept preview</span>
  </header>

  {#if !artifact}
    <section class="unavailable" aria-labelledby="unavailable-title">
      <p class="eyebrow">Test closed</p>
      <h1 id="unavailable-title">This concept is no longer collecting responses.</h1>
      <p>The researcher may have reached the planned stopping point or closed the test.</p>
    </section>
  {:else}
    <article class="offer" aria-labelledby="offer-title">
      <p class="eyebrow">A product concept for feedback</p>
      <h1 id="offer-title">{artifact.headline}</h1>
      <p class="promise">{artifact.promise}</p>

      <div class="action-region" bind:this={ctaRegion}>
        {#if disclosed}
          <section class="disclosure" aria-live="polite">
            <p class="eyebrow">Interest recorded</p>
            <h2>{artifact.disclosure.title}</h2>
            <p>{artifact.disclosure.body}</p>
          </section>
        {:else}
          <button type="button" onclick={() => void showInterest()} disabled={submitting}>
            {submitting ? 'Recording…' : artifact.ctaLabel}
          </button>
          <p class="action-note">No signup or payment is required.</p>
        {/if}
        {#if trackingError}<p class="tracking-error" role="alert">{trackingError}</p>{/if}
      </div>
    </article>
  {/if}

  <footer>
    <span>Independent concept research</span>
    <a href="/privacy">Privacy</a>
  </footer>
</main>

<style>
  :global(body) {
    margin: 0;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
  }
  .test-shell {
    width: min(100% - 2rem, 72rem);
    min-height: 100dvh;
    margin: 0 auto;
    display: grid;
    grid-template-rows: auto 1fr auto;
  }
  .test-header, footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1.25rem 0;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--color-text-muted);
  }
  .test-header img { width: 8.5rem; height: auto; }
  .offer, .unavailable {
    align-self: center;
    max-width: 52rem;
    padding: clamp(3rem, 8vw, 7rem) 0 clamp(4rem, 10vw, 8rem);
  }
  .eyebrow {
    margin: 0 0 1rem;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 750;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  h1 {
    max-width: 16ch;
    margin: 0;
    font-size: clamp(2.8rem, 7vw, 6.6rem);
    line-height: 0.96;
    letter-spacing: -0.055em;
    text-wrap: balance;
  }
  .promise, .unavailable > p:last-child {
    max-width: 58ch;
    margin: 1.8rem 0 0;
    font-size: clamp(1.05rem, 2vw, 1.35rem);
    line-height: 1.65;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }
  .action-region {
    margin-top: clamp(2.5rem, 6vw, 4.5rem);
    padding-top: 1.5rem;
    border-top: 1px solid var(--color-border);
  }
  button {
    min-height: 3.35rem;
    padding: 0 1.5rem;
    border: 1px solid var(--color-text-primary);
    border-radius: 0.7rem;
    background: var(--color-text-primary);
    color: var(--color-bg-primary);
    font: inherit;
    font-weight: 750;
    cursor: pointer;
    transition: transform 160ms ease, opacity 160ms ease;
  }
  button:hover:not(:disabled) { transform: translateY(-1px); }
  button:active:not(:disabled) { transform: translateY(1px); }
  button:focus-visible, a:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 3px; }
  button:disabled { opacity: 0.6; cursor: wait; }
  .action-note, .tracking-error {
    margin: 0.75rem 0 0;
    font-size: 0.78rem;
    color: var(--color-text-muted);
  }
  .tracking-error { color: var(--color-error); }
  .disclosure {
    max-width: 46rem;
    padding-left: 1.25rem;
    border-left: 3px solid var(--color-border-emphasis);
  }
  .disclosure h2 { margin: 0; font-size: clamp(1.35rem, 3vw, 2rem); letter-spacing: -0.025em; }
  .disclosure > p:last-child { margin: 0.8rem 0 0; line-height: 1.65; color: var(--color-text-secondary); }
  footer { border-top: 1px solid var(--color-border); }
  footer a { color: inherit; }
  @media (max-width: 600px) {
    .test-shell { width: min(100% - 1.4rem, 72rem); }
    .test-header { padding-top: 0.9rem; }
    .test-header img { width: 7.25rem; }
    .offer, .unavailable { padding-top: 2.5rem; }
    h1 { font-size: clamp(2.5rem, 14vw, 4.4rem); }
    button { width: 100%; }
  }
</style>
