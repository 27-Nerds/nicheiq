<script lang="ts">
  // Guided-research intake (EXPERIMENTAL, admin-gated).
  //
  // What this page is NOT: a chatbot home. The first draft was the canonical AI
  // landing — ambient glow, mono eyebrow with a live dot, display question, lede,
  // rounded field with a circular send glyph, three suggested prompts, a 3-up
  // capability strip. Every one of those is furniture; the stack of them is the tell,
  // and none of it could belong to anything but a generic assistant.
  //
  // What it IS: the brief that opens a research file. The page shows the RECORD the
  // run will fill — the three checkpoints, empty, waiting to be stamped — so the
  // product's actual promise (it stops and asks you before spending) is visible
  // before you commit, and the artifact you'll live in is the artifact you start in.
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import Composer from "$lib/components/chat/Composer.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import type { StageCosts } from "$lib/types/job";

  let input = $state("");
  let submitting = $state(false);
  let error = $state("");
  let composerRef: Composer | undefined = $state();

  // Guided runs charge the S1 (discovery-segment) checkpoint price, not the flat
  // legacy discovery cost. Null = the price is unknown; the run cannot start.
  const guidedCost = $derived.by(() => {
    const s1 = (page.data.stageCosts as StageCosts | undefined)?.guided?.s1;
    return Number.isInteger(s1) && (s1 as number) >= 0 ? (s1 as number) : null;
  });
  const priceUnavailable = $derived(
    Boolean(page.data.billingLoadState?.guidedCostsUnavailable) || guidedCost === null,
  );

  // Deliberately spread across KINDS of subject — a trade, a studio, a back office —
  // so the SET says "name anything", which no single example can.
  const EXAMPLES = [
    "Independent music teachers managing students and scheduling",
    "Indie game studios running community playtests",
    "Freelance bookkeepers chasing late client invoices",
  ];

  // The record this run will fill. Two of the three rows are things the analyst
  // hands BACK to you — that pause is the product, and it is the reason the sentence
  // you type matters.
  const CHECKPOINTS = [
    { name: "Niche checkpoint", note: "I read the framing back to you before searching", yours: true },
    { name: "Evidence", note: "Community threads, ranked by pain", yours: false },
    { name: "Idea selection", note: "Candidates you shortlist for deep research", yours: true },
  ];

  function useExample(text: string) {
    if (submitting) return;
    input = text;
    composerRef?.focus();
  }

  async function start() {
    const text = input.trim();
    if (!text || submitting || priceUnavailable || guidedCost === null) return;
    submitting = true;
    error = "";
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          niche: text,
          chatMode: true,
          entryMode: "idea",
          expectedCost: guidedCost,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        submitting = false;
        if (res.status === 402 && data.code === "INSUFFICIENT_CREDITS") {
          creditTopUp.show({
            balance: data.balance ?? 0,
            required: data.required ?? guidedCost,
            stageName: "guided research",
          });
          return;
        }
        if (res.status === 409 && data.code === "PRICE_CHANGED") {
          await invalidateAll();
          error = "The research price changed. Review the updated cost and start again.";
          return;
        }
        error = data.error || "Couldn't start the research. Try again.";
        return;
      }
      await goto(`/research/${data.id}`);
    } catch {
      submitting = false;
      error = "Couldn't start the research. Try again.";
    }
  }
</script>

<svelte:head>
  <title>New guided research - NicheIQ</title>
</svelte:head>

<div class="intake">
  <PageHeader
    class="research-page-header"
    breadcrumbItems={[{ label: "Dashboard", href: "/dashboard" }]}
    breadcrumbCurrent="New research"
    title="Open a research file"
    subtitle="Give me a niche, an audience, or a problem space. I'll read the framing back before I spend anything."
  />

  <!-- The brief. The analyst's own words, because the analyst is who you're briefing. -->
  <section class="brief" aria-label="Research brief">
    <div class="brief-bezel">
      <div class="brief-core">
        <Composer
          bind:this={composerRef}
          bind:value={input}
          placeholder="Who are they, and what are they struggling with?"
          label="What should we research?"
          busy={submitting}
          disabled={priceUnavailable}
          size="roomy"
          onSubmit={start}
          submitLabel={priceUnavailable
            ? "Pricing unavailable"
            : `Start the run · ${guidedCost} ${guidedCost === 1 ? "credit" : "credits"}`}
          busyLabel="Starting the run…"
          hint=""
        />
      </div>
    </div>

    {#if error}
      <p class="intake-error" role="alert">{error}</p>
    {/if}
    {#if priceUnavailable}
      <p class="intake-error" role="alert">
        Pricing is temporarily unavailable, so the run can't start. Reload the page to try again.
      </p>
    {/if}

    <div class="examples">
      <span class="examples-label">Try a starting point</span>
      <div class="example-list">
        {#each EXAMPLES as example (example)}
          <button type="button" class="example" disabled={submitting} onclick={() => useExample(example)}>
            <span>{example}</span>
          </button>
        {/each}
      </div>
    </div>
  </section>

  <!-- The record, empty. This is the same spine the run will fill, so what you see
       now is what you'll be reading later — and the two stops are visible up front. -->
  <div class="record-bezel">
    <section class="record" aria-label="What this run produces">
      <header class="record-head">
        <h2 class="record-heading">How guided research works</h2>
        <p class="record-copy">The analyst moves the work forward, then hands the judgment back at two checkpoints.</p>
      </header>

      <ol class="checkpoints">
        {#each CHECKPOINTS as cp (cp.name)}
          <li class="checkpoint" class:is-yours={cp.yours}>
            <span class="checkpoint-mark" aria-hidden="true"></span>
            <span class="checkpoint-copy">
              <span class="checkpoint-name">{cp.name}</span>
              <span class="checkpoint-note">{cp.note}</span>
            </span>
            {#if cp.yours}
              <span class="checkpoint-stop">Your review</span>
            {/if}
          </li>
        {/each}
      </ol>
    </section>
  </div>
</div>

<style>
  .intake {
    --research-ink: var(--color-text-primary);
    --research-muted: var(--color-text-muted);
    --research-line: var(--color-border);
    --research-motion: cubic-bezier(0.32, 0.72, 0, 1);
    width: min(56rem, 100%);
    margin: 0 auto;
    padding: 2rem 2.5rem 5rem;
    display: grid;
    align-content: start;
    gap: 1.5rem;
    color: var(--research-ink);
  }

  :global(.research-page-header) {
    margin-bottom: 0;
  }

  .brief {
    display: grid;
    gap: 1rem;
  }
  .brief-bezel {
    border: 1px solid var(--research-line);
    border-radius: 0.875rem;
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
  }
  .brief-core {
    padding: 1rem;
  }
  .brief-core :global(.composer) {
    min-height: 4rem;
    padding: 0.5rem 0.5rem 0.5rem 1rem;
    border: 1px solid var(--color-input-border);
    border-radius: 0.75rem;
    background: var(--color-bg-elevated);
    box-shadow: none;
    transition:
      border-color 180ms ease,
      box-shadow 180ms ease;
  }
  .brief-core :global(.composer.is-focused) {
    border-color: var(--color-accent);
    box-shadow:
      0 0 0 1px var(--color-accent),
      0 0 0 4px color-mix(in srgb, var(--color-accent) 10%, transparent);
  }
  .brief-core :global(.composer textarea) {
    min-height: 2rem;
    font-size: 0.9375rem;
    line-height: 1.5;
  }
  .brief-core :global(.composer textarea::placeholder) {
    color: var(--color-text-muted);
  }
  .brief-core :global(.composer-send--labeled) {
    min-width: 0;
    min-height: 2.875rem;
    padding: 0.32rem 0.38rem 0.32rem 1rem;
    border: 0;
    border-radius: 999px;
    background: var(--color-accent);
    color: var(--color-text-on-accent);
    font-size: 0.8125rem;
    font-weight: 700;
    transition:
      background 180ms ease,
      transform 180ms var(--research-motion);
  }
  .brief-core :global(.composer-send--labeled:hover:not(:disabled)) {
    background: var(--color-accent-dark);
  }
  .brief-core :global(.composer-send--labeled:active:not(:disabled)) {
    transform: scale(0.98);
  }
  .brief-core :global(.composer-send--labeled:disabled) {
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
  }

  .intake-error {
    margin: 0;
    padding: 0.75rem 1rem;
    border-radius: 0.625rem;
    background: color-mix(in srgb, var(--color-error) 7%, transparent);
    font-size: 0.8125rem;
    color: var(--color-error-text);
  }

  .examples {
    display: grid;
    gap: 0.5rem;
  }
  .examples-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--research-muted);
  }
  .example-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .example {
    padding: 0.55rem 0.75rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--research-line);
    border-radius: 0.5rem;
    color: var(--research-muted);
    font-family: var(--font-body);
    font-size: 0.75rem;
    line-height: 1.35;
    text-align: left;
    cursor: pointer;
    transition:
      border-color 180ms ease,
      color 180ms ease,
      transform 180ms var(--research-motion);
  }
  .example:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--color-accent) 55%, var(--research-line));
    color: var(--research-ink);
    transform: translateY(-1px);
  }
  .example:active:not(:disabled) {
    transform: translateY(0) scale(0.99);
  }
  .example:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .example:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 0.3rem;
  }

  .record-bezel {
    border: 1px solid var(--research-line);
    border-radius: 0.875rem;
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
  }
  .record {
    display: grid;
    grid-template-columns: minmax(12rem, 0.68fr) minmax(0, 1.32fr);
    gap: 2rem;
    padding: 1.25rem;
  }
  .record-head {
    align-self: start;
    display: grid;
    gap: 0.5rem;
  }
  .record-heading {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.35;
    color: var(--research-ink);
  }
  .record-copy {
    margin: 0;
    font-size: 0.75rem;
    line-height: 1.55;
    color: var(--research-muted);
    text-wrap: pretty;
  }
  .checkpoints {
    display: grid;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .checkpoint {
    position: relative;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.75rem;
    min-height: 4.25rem;
    padding: 0.5rem 0;
  }
  .checkpoint::before {
    content: "";
    position: absolute;
    left: 0.25rem;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--research-line);
  }
  .checkpoint:first-child::before {
    top: 50%;
  }
  .checkpoint:last-child::before {
    bottom: 50%;
  }
  .checkpoint-mark {
    position: relative;
    z-index: 1;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: var(--radius-full, 9999px);
    background: var(--color-bg-elevated);
    box-shadow: inset 0 0 0 1px #9b938a;
  }
  .checkpoint.is-yours .checkpoint-mark {
    border-radius: 1px;
    transform: rotate(45deg);
    background: color-mix(in srgb, var(--color-accent) 8%, var(--color-bg-elevated));
    box-shadow: inset 0 0 0 1.25px var(--color-accent);
  }
  .checkpoint-copy {
    display: grid;
    gap: 0.32rem;
  }
  .checkpoint-name {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--research-ink);
  }
  .checkpoint-note {
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--research-muted);
    text-wrap: pretty;
  }
  .checkpoint-stop {
    align-self: center;
    padding: 0.35rem 0.5rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-accent) 8%, transparent);
    font-size: 0.5625rem;
    font-weight: 700;
    color: var(--color-accent-dark);
    white-space: nowrap;
  }

  @media (max-width: 1279px) {
    .intake {
      padding: 1rem 1rem 4rem;
    }
  }

  @media (max-width: 719px) {
    .record {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
  }

  @media (max-width: 639px) {
    .brief-core {
      padding: 0.75rem;
    }
    .brief-core :global(.composer) {
      align-items: stretch;
      flex-direction: column;
      min-height: 0;
      padding: 1rem;
    }
    .brief-core :global(.composer-send--labeled) {
      width: 100%;
      justify-content: space-between;
      align-self: stretch;
    }
    .example-list {
      display: grid;
    }
    .example {
      width: 100%;
    }
    .record {
      padding: 1rem;
    }
    .checkpoint {
      grid-template-columns: auto minmax(0, 1fr);
      gap: 0.7rem;
    }
    .checkpoint-stop {
      grid-column: 2;
      justify-self: start;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .example,
    .brief-core :global(.composer),
    .brief-core :global(.composer-send--labeled) {
      transition: none;
    }
    .example:hover:not(:disabled),
    .example:active:not(:disabled),
    .brief-core :global(.composer-send--labeled:active:not(:disabled)) {
      transform: none;
    }
  }
</style>
