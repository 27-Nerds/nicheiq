<script lang="ts">
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

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

  const shortfall = $derived(Math.max(0, cost - balance));
  const affordable = $derived(shortfall === 0);
  const stageName = $derived(kind === "deep_idea" ? "deep_research" : "discovery");
  const kicker = $derived(
    kind === "deep_idea" ? "DEEP-RESEARCH ORDER" : kind === "remix" ? "REMIX ORDER" : "RESEARCH ORDER",
  );

  const deliverables = $derived(
    kind === "deep_idea"
      ? [
          "Market sizing: TAM / SAM / SOM",
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

  function requestClose() {
    if (loading) return;
    open = false;
  }

  function getCredits() {
    // Hand off to the global top-up modal — close THIS modal first so two modals
    // never share the body scroll-lock simultaneously.
    open = false;
    creditTopUp.show({ balance, required: cost, stageName });
  }
</script>

<FormOverlay {open} eyebrow={kicker} title={subject} onRequestClose={requestClose}>
  <div class="order-receipt">
    <ul class="order-list">
      {#each deliverables as d}
        <li>{d}</li>
      {/each}
    </ul>
    <hr class="order-rule" />
    <p class="order-total record-line">
      <span>Total</span>
      <span class:is-short={!affordable}>
        {cost} credits · balance {balance} → {Math.max(0, balance - cost)}
      </span>
    </p>
    {#if !affordable}
      <p class="order-short record-line">Short by {shortfall} credits</p>
    {/if}
  </div>

  {#if crossNiches.length >= 2}
    <div class="cross-niche">
      <p class="cross-niche-label">Cross-niche</p>
      <p class="cross-niche-body">
        Spanning: {crossNiches.join(" · ")}{#if crossNiches.length >= 3}.
          Mixing three or more niches widens the brief: expect broader, less
          focused candidates.{/if}
      </p>
    </div>
  {/if}

  {#if error}
    <p class="order-error" role="alert">{error}</p>
  {/if}

  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" onclick={requestClose} disabled={loading}>
      Cancel
    </button>
  {/snippet}
  {#snippet footer()}
    {#if affordable}
      <SubmitButton
        type="button"
        onclick={onConfirm}
        {loading}
        loadingText="Starting…"
        label={`Authorize · ${cost} credits`}
        class=""
      />
    {:else}
      <SubmitButton
        type="button"
        onclick={getCredits}
        loadingText=""
        label={`Get ${shortfall} more credits`}
        class=""
      />
    {/if}
  {/snippet}
</FormOverlay>

<style>
  .order-receipt {
    display: grid;
    gap: 0.55rem;
    padding: 0.85rem 0.9rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .order-list {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .order-list li {
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .order-rule {
    margin: 0.15rem 0;
    border: 0;
    border-top: 1px solid var(--color-border);
  }

  .order-total {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin: 0;
    color: var(--color-text-primary);
  }

  .order-total .is-short {
    color: var(--color-error-text);
  }

  .order-short {
    margin: 0;
    color: var(--color-error-text);
  }

  .cross-niche {
    display: grid;
    gap: 0.3rem;
  }

  .cross-niche-label {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .cross-niche-body {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.45;
  }

  .order-error {
    margin: 0;
    color: var(--color-error-text);
    font-size: var(--text-13);
    line-height: 1.45;
  }
</style>
