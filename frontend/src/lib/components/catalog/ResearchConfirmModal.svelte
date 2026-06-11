<script lang="ts">
  import { portal } from "$lib/actions/portal";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import { Sparkles, Loader2, Check } from "lucide-svelte";

  type Kind = "pain" | "remix" | "deep_idea";

  let {
    open = $bindable(false),
    kind,
    subject,
    cost,
    balance,
    loading = false,
    error = "",
    crossNiches = [],
    onConfirm,
  }: {
    open?: boolean;
    kind: Kind;
    subject: string;
    cost: number;
    balance: number;
    loading?: boolean;
    error?: string;
    /** Distinct source niches of the selected pains (remix); advisory shown at >=2. */
    crossNiches?: string[];
    onConfirm: () => void;
  } = $props();

  let modalEl = $state<HTMLDivElement | null>(null);
  let primaryEl = $state<HTMLButtonElement | null>(null);
  let triggerEl: HTMLElement | null = null;

  const shortfall = $derived(Math.max(0, cost - balance));
  const affordable = $derived(shortfall === 0);
  const stageName = $derived(kind === "deep_idea" ? "deep_research" : "discovery");
  const ledgerLabel = $derived(kind === "deep_idea" ? "DEEP RESEARCH" : "DISCOVERY");
  const kicker = $derived(
    kind === "deep_idea" ? "DEEP-RESEARCH ORDER" : kind === "remix" ? "REMIX ORDER" : "RESEARCH ORDER",
  );

  const deliverables = $derived(
    kind === "deep_idea"
      ? [
          "Market sizing — TAM / SAM / SOM",
          "SEO & keyword opportunity",
          "Pricing & competitive landscape",
          "Go / no-go verdict",
        ]
      : [
          "Solution candidates ideated for this pain",
          "Pick the best to take into deep research",
          "Grounded in real community discussions",
        ],
  );

  const titleId = "research-confirm-title";

  function close() {
    if (loading) return;
    open = false;
    triggerEl?.focus();
  }

  function getCredits() {
    // Hand off to the global top-up modal — close THIS modal first so two modals
    // never share the body scroll-lock simultaneously.
    open = false;
    creditTopUp.show({ balance, required: cost, stageName });
  }

  function onBackdrop(e: MouseEvent) {
    if (e.target === e.currentTarget) close();
  }

  function getFocusable(): HTMLElement[] {
    if (!modalEl) return [];
    return Array.from(
      modalEl.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      ),
    );
  }

  function onKeydown(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === "Escape") {
      close();
      return;
    }
    if (e.key === "Tab") {
      const f = getFocusable();
      if (f.length === 0) return;
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  // Focus the primary action on open; lock background scroll while open.
  $effect(() => {
    if (open && modalEl) {
      triggerEl = document.activeElement as HTMLElement;
      primaryEl?.focus();
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = "";
      };
    }
  });
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    use:portal
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    onclick={onBackdrop}
    role="dialog"
    aria-modal="true"
    aria-labelledby={titleId}
    tabindex="-1"
  >
    <div class="absolute inset-0 bg-black/50 backdrop-blur-sm rc-fade"></div>

    <!-- Panel: research order ticket -->
    <div bind:this={modalEl} class="rc-panel relative w-full max-w-md rounded-lg overflow-hidden">
      <!-- accent top-rail -->
      <div class="h-[3px] w-full bg-accent"></div>

      <div class="p-6">
        <p class="font-mono text-[10px] tracking-[0.12em] uppercase text-accent font-semibold">
          {kicker}
        </p>
        <h2 id={titleId} class="font-display font-semibold tracking-tight text-text-primary text-lg mt-1 leading-snug">
          {subject}
        </h2>

        <!-- deliverables -->
        <ul class="mt-4 space-y-1.5">
          {#each deliverables as d, i}
            <li class="rc-deliverable flex items-start gap-2 text-[13px] text-text-secondary" style="--i: {i}">
              <Check size={14} class="text-accent shrink-0 mt-0.5" />
              <span>{d}</span>
            </li>
          {/each}
        </ul>

        <!-- cross-niche advisory (remix spanning multiple niches) -->
        {#if crossNiches.length >= 2}
          <div class="mt-4 pt-3 border-t border-dashed border-border-emphasis">
            <p class="font-mono text-[10px] tracking-[0.12em] uppercase text-text-muted font-semibold">
              Cross-niche
            </p>
            <p class="mt-1 text-[12px] text-text-muted leading-snug">
              Spanning: {crossNiches.join(" · ")}{#if crossNiches.length >= 3}.
                Mixing three or more niches widens the brief — expect broader, less
                focused candidates.{/if}
            </p>
          </div>
        {/if}

        <!-- cost ledger -->
        <div class="mt-5 pt-4 border-t border-dashed border-border-emphasis font-mono text-[13px] tabular-nums">
          <div class="flex items-center justify-between">
            <span class="text-text-muted tracking-wide">{ledgerLabel}</span>
            <span class="rc-cost text-accent font-bold">— {cost} cr</span>
          </div>
          <div class="flex items-center justify-between mt-1 text-[12px]" class:text-error={!affordable} class:text-text-muted={affordable}>
            <span>Balance</span>
            <span>
              {balance} → {Math.max(0, balance - cost)}
              {#if !affordable}
                <span class="ml-2 rounded px-1.5 py-0.5 text-[11px] font-semibold bg-error/10 text-error">
                  Short by {shortfall} cr
                </span>
              {/if}
            </span>
          </div>
        </div>

        {#if error}
          <p class="mt-3 text-[13px] text-error" role="alert">{error}</p>
        {/if}

        <!-- actions -->
        <div class="mt-6 flex items-center justify-end gap-2">
          <button type="button" class="rc-ghost" onclick={close} disabled={loading}>Cancel</button>
          {#if affordable}
            <button bind:this={primaryEl} type="button" class="rc-primary" onclick={onConfirm} disabled={loading} aria-busy={loading}>
              {#if loading}
                <Loader2 size={15} class="rc-spin" /> <span>Starting…</span>
              {:else}
                <Sparkles size={15} /> <span>Authorize · {cost} credits</span>
              {/if}
            </button>
          {:else}
            <button bind:this={primaryEl} type="button" class="rc-primary" onclick={getCredits}>
              <Sparkles size={15} /> <span>Get {shortfall} more credits</span>
            </button>
          {/if}
        </div>
        {#if !affordable}
          <p class="mt-2 text-right text-[12px] text-text-muted">You're {shortfall} credits away from this report.</p>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .rc-panel {
    background: var(--color-bg-elevated, #fff);
    border: 1px solid var(--color-border);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.18),
      0 1px 2px rgba(154, 52, 18, 0.18),
      0 12px 32px rgba(154, 52, 18, 0.12),
      0 4px 12px rgba(0, 0, 0, 0.08);
    animation: rc-rise 180ms ease-out;
  }
  .rc-cost {
    display: inline-block;
    animation: rc-settle 220ms ease-out 60ms both;
  }
  .rc-deliverable {
    animation: rc-fade-up 220ms ease-out both;
    animation-delay: calc(var(--i) * 45ms + 80ms);
  }
  .rc-primary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 16px;
    border-radius: 6px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--color-surface, #fff);
    background: var(--color-accent);
    border: 1px solid transparent;
    cursor: pointer;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.18),
      0 1px 2px rgba(154, 52, 18, 0.18),
      0 6px 14px rgba(154, 52, 18, 0.1);
  }
  .rc-primary:hover:not(:disabled) {
    background: var(--color-accent-hover, var(--color-accent-dark));
  }
  .rc-primary:active:not(:disabled) {
    transform: scale(0.98);
  }
  .rc-primary:disabled {
    opacity: 0.7;
    cursor: progress;
  }
  .rc-primary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .rc-ghost {
    padding: 9px 14px;
    border-radius: 6px;
    font-size: 13.5px;
    font-weight: 500;
    color: var(--color-text-secondary);
    background: transparent;
    border: 1px solid var(--color-border-emphasis);
    cursor: pointer;
  }
  .rc-ghost:hover:not(:disabled) {
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
  }
  :global(.rc-spin) {
    animation: rc-spin 0.8s linear infinite;
  }
  @keyframes rc-spin {
    to { transform: rotate(360deg); }
  }
  @keyframes rc-rise {
    from { opacity: 0; transform: translateY(8px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes rc-fade { from { opacity: 0; } to { opacity: 1; } }
  .rc-fade { animation: rc-fade 150ms ease-out; }
  @keyframes rc-settle {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes rc-fade-up {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @media (prefers-reduced-motion: reduce) {
    .rc-panel, .rc-cost, .rc-deliverable, .rc-fade, :global(.rc-spin) {
      animation: none;
    }
  }
</style>
