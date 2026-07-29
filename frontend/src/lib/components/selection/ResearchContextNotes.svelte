<script lang="ts">
  import type { MarketReality } from "$lib/types/report";

  interface Props {
    shapeLine?: string | null;
    coverageNotes: string[];
    userAdjustments: string[];
    marketReality?: MarketReality | null;
  }

  let { shapeLine = null, coverageNotes, userAdjustments, marketReality = null }: Props = $props();

  // Native <details> popovers have no built-in Escape/outside-click
  // dismissal; track every open disclosure so both can close it (N2).
  let openDisclosures = $state<HTMLDetailsElement[]>([]);

  function trackDisclosure(node: HTMLDetailsElement) {
    openDisclosures.push(node);
    return {
      destroy() {
        openDisclosures = openDisclosures.filter((el) => el !== node);
      },
    };
  }

  function closeOpenDisclosures() {
    for (const el of openDisclosures) {
      if (el.open) el.open = false;
    }
  }

  function handleWindowClick(event: MouseEvent) {
    for (const el of openDisclosures) {
      if (el.open && !el.contains(event.target as Node)) el.open = false;
    }
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") closeOpenDisclosures();
  }

  $effect(() => {
    window.addEventListener("click", handleWindowClick);
    window.addEventListener("keydown", handleWindowKeydown);
    return () => {
      window.removeEventListener("click", handleWindowClick);
      window.removeEventListener("keydown", handleWindowKeydown);
    };
  });
</script>

<div class="context-notes" data-annotation-anchor="shortlist-context">
  {#if shapeLine}
    <div class="shape-line">
      <span class="shape-label">Opportunity shape</span>
      <span>{shapeLine}</span>
    </div>
  {/if}
  <div class="context-disclosures">
    {#if userAdjustments.length}
      <details class="coverage-disclosure" use:trackDisclosure>
        <summary>
          <span>User adjustments</span>
          <strong>{userAdjustments.length}</strong>
        </summary>
        <ul role="list">
          {#each userAdjustments as note}
            {#if note?.trim()}<li>{note}</li>{/if}
          {/each}
        </ul>
      </details>
    {/if}
    {#if coverageNotes.length}
      <details class="coverage-disclosure" use:trackDisclosure>
        <summary>
          <span>Data caveats</span>
          <strong>{coverageNotes.length}</strong>
        </summary>
        <ul role="list">
          {#each coverageNotes as note}
            {#if note?.trim()}<li>{note}</li>{/if}
          {/each}
        </ul>
      </details>
    {/if}
    {#if marketReality?.incumbents?.length}
      <details class="coverage-disclosure market-reality-disclosure" use:trackDisclosure>
        <summary>
          <span>Market reality</span>
          <strong>{marketReality.incumbents.length}</strong>
        </summary>
        <div class="market-reality-body">
          <table class="market-reality-table">
            <caption class="sr-only">Market reality: comparable tools and where they fall short</caption>
            <thead>
              <tr><th scope="col">Tool</th><th scope="col">Pricing</th><th scope="col">Focus</th><th scope="col">Weak at</th></tr>
            </thead>
            <tbody>
              {#each marketReality.incumbents as incumbent}
                <tr>
                  <td>{incumbent.name}</td>
                  <td>{incumbent.pricing ?? "--"}</td>
                  <td>{incumbent.focus ?? "--"}</td>
                  <td>{incumbent.gap ?? "--"}</td>
                </tr>
              {/each}
            </tbody>
          </table>
          {#if marketReality.wallet?.wallet_class || marketReality.wallet?.evidence}
            <p class="market-reality-wallet">
              <span class="market-reality-wallet-label">Niche spend</span>
              {#if marketReality.wallet.wallet_class}<strong>{marketReality.wallet.wallet_class}</strong>{/if}
              {#if marketReality.wallet.evidence}
                {marketReality.wallet.wallet_class ? ": " : ""}{marketReality.wallet.evidence}
              {/if}
            </p>
          {/if}
        </div>
      </details>
    {/if}
  </div>
</div>

<style>
  .context-notes {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem 1rem;
    padding: 0.02rem 0.05rem 0.18rem;
  }
  .shape-line {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    flex: 1 1 24rem;
    align-items: baseline;
    min-width: 0;
    margin: 0;
    gap: 0.62rem;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.42;
  }
  .shape-label {
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0;
    text-transform: none;
    white-space: nowrap;
  }
  /* Positioned so it — not the individual trigger — is the panels' containing
     block. Only the LAST trigger's right edge coincides with the group's; anchoring
     a 42rem panel to `right: 0` of the FIRST trigger pushed its left edge off-screen
     (silently cropped by .job-page-shell's `overflow-x: clip`). */
  .context-disclosures {
    position: relative;
    display: flex;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.4rem;
    margin-left: auto;
  }
  .coverage-disclosure {
    flex-shrink: 0;
    min-width: 11rem;
  }
  .market-reality-disclosure { min-width: 12.5rem; }
  .coverage-disclosure summary {
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.55rem;
    width: 100%;
    padding: 0.34rem 0.54rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    background: transparent;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0;
    list-style: none;
    text-transform: none;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default);
  }
  .coverage-disclosure summary::-webkit-details-marker { display: none; }
  .coverage-disclosure summary:hover {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
  }
  .coverage-disclosure summary:active {
    transform: scale(0.98);
  }
  .coverage-disclosure summary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .coverage-disclosure summary strong {
    display: grid;
    min-width: 1.2rem;
    height: 1.2rem;
    padding: 0 0.25rem;
    place-items: center;
    border-radius: 999px;
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: 0.625rem;
  }
  .coverage-disclosure[open] summary {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }
  .coverage-disclosure ul,
  .market-reality-body {
    position: absolute;
    right: 0;
    z-index: 3;
    display: grid;
    gap: 0.58rem;
    width: min(42rem, 72vw);
    margin: 0.45rem 0 0;
    padding: 0.85rem 0.95rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 1rem;
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-lg);
  }
  .coverage-disclosure li {
    margin: 0;
    padding-left: 0.7rem;
    border-left: 1px solid var(--color-border-emphasis);
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.42;
    list-style: none;
  }
  .market-reality-body {
    gap: 0.6rem;
    width: min(46rem, 76vw);
    overflow-x: auto;
  }
  .market-reality-table {
    width: 100%;
    min-width: 28rem;
    border-collapse: collapse;
  }
  .market-reality-table th {
    padding: 0.28rem 0.5rem;
    border-bottom: 1px solid var(--color-border-emphasis);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.06em;
    text-align: left;
    text-transform: uppercase;
  }
  .market-reality-table td {
    padding: 0.4rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.4;
    vertical-align: top;
  }
  .market-reality-table tr:last-child td { border-bottom: 0; }
  .market-reality-table td:first-child {
    color: var(--color-text-primary);
    font-weight: 700;
    white-space: nowrap;
  }
  .market-reality-wallet {
    margin: 0;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
    color: var(--color-text-muted);
    font-size: 0.75rem;
    line-height: 1.42;
  }
  .market-reality-wallet-label {
    margin-right: 0.35rem;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .market-reality-wallet strong { color: var(--color-text-secondary); }

  @media (max-width: 859px) {
    .context-notes {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 0.55rem;
    }
    .shape-line {
      grid-template-columns: 1fr;
      gap: 0.2rem;
    }
    .context-disclosures {
      width: 100%;
      flex-direction: column;
    }
    .coverage-disclosure,
    .market-reality-disclosure {
      width: 100%;
      min-width: 0;
    }
    .coverage-disclosure ul,
    .market-reality-body {
      position: static;
      width: 100%;
    }
    .market-reality-table { min-width: 0; }
    .market-reality-table td:first-child { white-space: normal; }
  }

  @media (prefers-reduced-motion: reduce) {
    .coverage-disclosure summary:active {
      transform: none;
    }
  }
</style>
