<script lang="ts">
  import type { ComponentType } from "svelte";
  import {
    AlertTriangle,
    CheckCircle,
    Coins,
    Download,
    ExternalLink,
    Loader2,
    Lock,
    RotateCw,
  } from "lucide-svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import { page } from "$app/state";

  interface Props {
    label: string;
    icon?: ComponentType;
    status: 'locked' | 'pending' | 'running' | 'completed' | 'failed';
    creditCost?: number;
    canAfford?: boolean;
    priceAvailable?: boolean;
    priceUnavailableMessage?: string;
    asset?: { url: string } | null;
    generating?: boolean;
    refundedAmount?: number | null;
    error?: string;
    notice?: string;
    onGenerate: () => Promise<void>;
  }

  let {
    label,
    icon: Icon,
    status,
    creditCost = 0,
    canAfford = true,
    priceAvailable = true,
    priceUnavailableMessage = "Current price unavailable. Refresh to try again.",
    asset = null,
    generating = false,
    refundedAmount = null,
    error: errorMsg = "",
    notice = "",
    onGenerate,
  }: Props = $props();

  let confirmPending = $state(false);
  const canPurchase = $derived(status === 'pending' || status === 'failed');
  const purchaseVerb = $derived(status === 'failed' ? 'Retry' : 'Generate');
  const creditLabel = $derived(`${creditCost} ${creditCost === 1 ? 'credit' : 'credits'}`);
  const confirmationTitleId = $derived(
    `deliverable-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-confirmation`,
  );
  const priceReasonId = $derived(
    `deliverable-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-price-unavailable`,
  );

  $effect(() => {
    if (!canPurchase) confirmPending = false;
  });
</script>

<div
  class="dr-row"
  class:dr-row--completed={status === 'completed'}
  class:dr-row--running={status === 'running'}
  class:dr-row--failed={status === 'failed'}
  class:dr-row--locked={status === 'locked'}
>
  <!-- Indicator -->
  <div class="dr-indicator"
    class:dr-indicator--completed={status === 'completed'}
    class:dr-indicator--running={status === 'running'}
    class:dr-indicator--failed={status === 'failed'}
    class:dr-indicator--locked={status === 'locked'}
    class:dr-indicator--pending={status === 'pending'}
  >
    {#if status === 'completed'}
      <CheckCircle class="dr-indicator-icon dr-indicator-icon--success" />
    {:else if status === 'running'}
      <Loader2 class="dr-indicator-icon dr-indicator-icon--info dr-spin" />
    {:else if status === 'failed'}
      <AlertTriangle class="dr-indicator-icon dr-indicator-icon--error" />
    {:else if status === 'locked'}
      <Lock class="dr-indicator-icon dr-indicator-icon--muted" />
    {:else if Icon}
      <Icon class="dr-indicator-icon dr-indicator-icon--accent" />
    {/if}
  </div>

  <!-- Label + hint -->
  <div class="dr-label-col">
    <span class="dr-label"
      class:dr-label--primary={status === 'completed'}
      class:dr-label--info={status === 'running'}
      class:dr-label--muted={status === 'locked'}
    >{label}</span>
    {#if status === 'locked'}
      <span class="dr-hint">Unlocks when research completes</span>
    {:else if status === 'running'}
      <span class="dr-hint dr-hint--info">Generating your page...</span>
    {:else if canPurchase}
      <span class="dr-hint">Responsive waitlist page · preview and downloadable HTML for self-hosting</span>
      {#if status === 'failed' && refundedAmount !== null}
        <span class="dr-hint dr-hint--refund">
          {refundedAmount} {refundedAmount === 1 ? 'credit was' : 'credits were'} returned from the failed attempt.
        </span>
      {/if}
      {#if !priceAvailable}
        <span id={priceReasonId} class="dr-hint dr-hint--warning">{priceUnavailableMessage}</span>
      {/if}
    {/if}
  </div>

  <!-- Actions -->
  <div class="dr-actions">
    {#if status === 'completed' && asset}
      <Button href={asset.url} target="_blank" rel="noopener noreferrer" icon={ExternalLink} label="View" class="btn-secondary btn-sm" />
      <Button href="{asset.url}?download=true" icon={Download} label="Download" class="btn-tertiary btn-sm" />
    {:else if status === 'running' || generating}
      <span class="dr-generating">
        <Loader2 class="dr-spinner" />
        Generating...
      </span>
    {:else if canPurchase}
      {#if !priceAvailable}
        <button
          disabled
          aria-describedby={priceReasonId}
          title={priceUnavailableMessage}
          class="btn-secondary btn-sm"
        >
          {purchaseVerb} unavailable
        </button>
      {:else if !canAfford && creditCost > 0}
        <!-- Insufficient credits strip — opens top-up modal -->
        <div class="dr-credit-warning">
          <AlertTriangle class="dr-credit-warning-icon" />
          <span>Insufficient credits</span>
          <button onclick={() => creditTopUp.show({ balance: (page.data.creditBalance as number) ?? 0, required: creditCost, stageName: label.toLowerCase() })} class="btn-tertiary btn-sm">Add credits</button>
        </div>
      {:else if confirmPending}
        <span class="dr-confirm-open">Review purchase below</span>
      {:else}
        <button onclick={() => { confirmPending = true; }} class="btn-secondary btn-sm">
          {#if status === 'failed'}<RotateCw class="w-4 h-4" />{:else if Icon}<Icon class="w-4 h-4" />{/if}
          {purchaseVerb} · {creditLabel}
        </button>
      {/if}
    {:else if status === 'locked'}
      <span class="dr-locked-text">Available after analysis</span>
    {/if}
  </div>
</div>

{#if canPurchase && confirmPending}
  <section class="dr-purchase-confirmation" aria-labelledby={confirmationTitleId}>
    <Coins class="dr-confirm-coins-icon" aria-hidden="true" />
    <div class="dr-confirm-copy">
      <h4 id={confirmationTitleId}>{status === 'failed' ? 'Retry landing page generation?' : 'Generate a waitlist landing page?'}</h4>
      <p>Creates one responsive, SEO-informed HTML page from this report. Preview or download it when ready; NicheIQ does not publish or host it.</p>
      <ul>
        <li>One generated version per completed research run.</li>
        <li>If generation fails before delivery, eligible credits are returned automatically.</li>
      </ul>
    </div>
    <div class="dr-confirm-actions">
      <Button
        onclick={async () => { confirmPending = false; await onGenerate(); }}
        label={`${purchaseVerb} page · ${creditLabel}`}
        class="btn-primary btn-sm"
      />
      <Button onclick={() => { confirmPending = false; }} label="Cancel" class="btn-secondary btn-sm" />
    </div>
  </section>
{/if}

{#if errorMsg}
  <div class="dr-error-strip">
    <AlertTriangle class="dr-error-strip-icon" />
    <span>{errorMsg}</span>
  </div>
{/if}

{#if notice}
  <div class="dr-notice-strip" role="status">
    <CheckCircle class="dr-notice-strip-icon" aria-hidden="true" />
    <span>{notice}</span>
  </div>
{/if}

<style>
  /* ── Row ── */
  .dr-row {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.625rem 0.75rem;
    border-radius: 0.5rem;
    transition: background 0.2s ease, opacity 0.2s ease;
    position: relative;
    flex-wrap: wrap;
  }

  .dr-row--completed {
    background: rgba(34, 197, 94, 0.04);
  }

  .dr-row--running {
    background: linear-gradient(
      90deg,
      rgba(59, 130, 246, 0.04) 0%,
      rgba(59, 130, 246, 0.08) 50%,
      rgba(59, 130, 246, 0.04) 100%
    );
    background-size: 200% 100%;
    animation: dr-shimmer 2.5s ease-in-out infinite;
  }

  .dr-row--failed {
    background: rgba(239, 68, 68, 0.04);
  }

  .dr-row--locked {
    opacity: 0.55;
  }

  @keyframes dr-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @media (prefers-reduced-motion: reduce) {
    .dr-row--running {
      animation: none;
      background: rgba(59, 130, 246, 0.06);
    }
    .dr-purchase-confirmation {
      animation: none;
    }
  }

  /* ── Indicator box ── */
  .dr-indicator {
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .dr-indicator--completed {
    background: rgba(34, 197, 94, 0.12);
  }
  .dr-indicator--running {
    background: rgba(59, 130, 246, 0.12);
  }
  .dr-indicator--failed {
    background: rgba(239, 68, 68, 0.12);
  }
  .dr-indicator--locked {
    background: var(--color-bg-surface);
  }
  .dr-indicator--pending {
    background: rgba(229, 90, 40, 0.08);
  }

  :global(.dr-indicator-icon) {
    width: 0.9375rem;
    height: 0.9375rem;
  }
  :global(.dr-indicator-icon--success) { color: var(--color-success); }
  :global(.dr-indicator-icon--info) { color: var(--color-info); }
  :global(.dr-indicator-icon--error) { color: var(--color-error); }
  :global(.dr-indicator-icon--muted) { color: var(--color-text-muted); }
  :global(.dr-indicator-icon--accent) { color: var(--color-accent); }

  :global(.dr-spin) {
    animation: dr-spin-anim 1s linear infinite;
  }
  @keyframes dr-spin-anim {
    to { transform: rotate(360deg); }
  }

  /* ── Label column ── */
  .dr-label-col {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    min-width: 0;
  }

  .dr-label {
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.75rem; /* align with indicator height */
    color: var(--color-text-secondary);
  }
  .dr-label--primary { color: var(--color-text-primary); }
  .dr-label--info { color: var(--color-info); }
  .dr-label--muted { color: var(--color-text-muted); }

  .dr-hint {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    line-height: 1.3;
  }
  .dr-hint--info { color: var(--color-info); }
  .dr-hint--warning { color: var(--color-warning); }
  .dr-hint--refund { color: var(--color-success-text); }

  /* ── Actions column ── */
  .dr-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.625rem;
    flex-shrink: 0;
    line-height: 1.75rem; /* vertical center with indicator */
  }

  /* Generating state */
  .dr-generating {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-info);
  }
  :global(.dr-spinner) {
    width: 0.875rem;
    height: 0.875rem;
    animation: dr-spin-anim 1s linear infinite;
  }

  /* Locked text */
  .dr-locked-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  /* ── Credit warning strip (replaces button) ── */
  .dr-credit-warning {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-warning);
    background: rgba(245, 158, 11, 0.08);
    padding: 0.3125rem 0.75rem;
    border-radius: 0.375rem;
  }
  :global(.dr-credit-warning-icon) {
    width: 0.8125rem;
    height: 0.8125rem;
    flex-shrink: 0;
  }

  /* ── Paid confirmation ── */
  .dr-confirm-open {
    color: var(--color-text-muted);
    font-size: 0.75rem;
  }
  .dr-purchase-confirmation {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 0.75rem;
    align-items: start;
    margin: 0.25rem 0 0 calc(1.75rem + 0.75rem);
    padding: 0.75rem;
    border: 1px solid var(--color-border-accent);
    border-radius: 0.5rem;
    background: var(--color-accent-subtle);
    animation: dr-confirm-enter 0.2s ease-out;
  }
  :global(.dr-confirm-coins-icon) {
    width: 0.8125rem;
    height: 0.8125rem;
    color: var(--color-accent);
    flex-shrink: 0;
  }
  .dr-confirm-copy h4 {
    margin: 0;
    color: var(--color-text-primary);
    font-size: 0.875rem;
    line-height: 1.3;
  }
  .dr-confirm-copy p,
  .dr-confirm-copy ul {
    margin: 0.25rem 0 0;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.45;
  }
  .dr-confirm-copy ul {
    padding-left: 1rem;
  }
  .dr-confirm-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-variant-numeric: tabular-nums;
  }

  @keyframes dr-confirm-enter {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* ── Error strip ── */
  .dr-error-strip {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    margin-top: 0.25rem;
    margin-left: calc(1.75rem + 0.75rem); /* indicator width + gap */
    font-size: 0.8125rem;
    color: var(--color-error);
    background: rgba(239, 68, 68, 0.06);
    padding: 0.3125rem 0.625rem;
    border-radius: 0.375rem;
  }
  :global(.dr-error-strip-icon) {
    width: 0.8125rem;
    height: 0.8125rem;
    flex-shrink: 0;
  }
  .dr-notice-strip {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    margin-top: 0.25rem;
    margin-left: calc(1.75rem + 0.75rem);
    padding: 0.3125rem 0.625rem;
    border-radius: 0.375rem;
    background: var(--color-success-subtle);
    color: var(--color-success-text);
    font-size: 0.8125rem;
  }
  :global(.dr-notice-strip-icon) {
    width: 0.8125rem;
    height: 0.8125rem;
    flex-shrink: 0;
  }

  /* ── Responsive: stack actions on mobile ── */
  @media (max-width: 480px) {
    .dr-actions {
      margin-left: 0;
      width: 100%;
      padding-left: calc(1.75rem + 0.75rem);
    }
    .dr-purchase-confirmation {
      grid-template-columns: auto minmax(0, 1fr);
      margin-left: 0;
    }
    .dr-confirm-actions {
      grid-column: 1 / -1;
      padding-left: calc(0.8125rem + 0.75rem);
      flex-wrap: wrap;
    }
  }
</style>
