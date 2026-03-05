<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import CategoryBadge from "$lib/components/catalog/CategoryBadge.svelte";
  import { opportunityVariant } from "$lib/utils/catalog-utils";
  import { MousePointerClick, ChevronDown, MessageSquareQuote } from "lucide-svelte";
  import { fade, slide } from "svelte/transition";

  interface Props {
    painPoint: any | null;
    totalCount?: number;
    categoryName?: string;
  }

  let { painPoint, totalCount = 0, categoryName = "" }: Props = $props();

  let showAllQuotes = $state(false);

  // Reset quote toggle when pain point changes
  $effect(() => {
    if (painPoint) {
      showAllQuotes = false;
    }
  });

  const extraQuotes = $derived(
    painPoint?.representativeQuotes?.length > 1
      ? painPoint.representativeQuotes.slice(1)
      : []
  );

  /** Strip common markdown syntax so quotes render as clean plain text */
  function stripMarkdown(text: string): string {
    return text
      .replace(/#{1,6}\s+/g, '')             // headings
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // [text](url) → text
      .replace(/\*\*([^*]+)\*\*/g, '$1')     // **bold** → bold
      .replace(/\*([^*]+)\*/g, '$1')         // *italic* → italic
      .replace(/__([^_]+)__/g, '$1')         // __bold__ → bold
      .replace(/_([^_]+)_/g, '$1')           // _italic_ → italic
      .replace(/~~([^~]+)~~/g, '$1')         // ~~strike~~ → strike
      .replace(/`([^`]+)`/g, '$1')           // `code` → code
      .trim();
  }

  const mentionCount = $derived(painPoint?.mentionCount ?? 0);
</script>

{#if painPoint}
  <div class="p-5" transition:fade={{ duration: 150 }}>
    <!-- Header -->
    <div class="mb-4">
      <h2 class="text-xl font-bold text-text-primary leading-tight">{painPoint.title}</h2>
      <div class="flex items-center gap-2 mt-2 flex-wrap">
        {#if painPoint.isFeatured}
          <Badge variant="accent">Featured</Badge>
        {/if}
        {#if painPoint.opportunityLevel}
          <Badge variant={opportunityVariant(painPoint.opportunityLevel)}>
            {painPoint.opportunityLevel} opportunity
          </Badge>
        {/if}
        {#if painPoint.category}
          <CategoryBadge category={painPoint.category} type="pain-points" light />
        {/if}
      </div>
    </div>

    <!-- Score strip — compact horizontal row -->
    <div class="bg-bg-surface border border-border rounded-xl px-4 py-3 mb-4">
      <div class="flex items-center justify-center gap-8">
        <div class="flex flex-col items-center gap-1">
          <ProgressRing
            value={painPoint.severityScore ?? 0}
            size={56}
            flat={true}
            animate={true}
            showTooltip={true}
            showValue={true}
            color="auto"
            label="Severity"
            description="How severe this pain point is for affected users"
          />
          <span class="mono-label">Severity</span>
        </div>
        <div class="flex flex-col items-center gap-1">
          <ProgressRing
            value={painPoint.willingnessToPayScore ?? 0}
            size={56}
            flat={true}
            animate={true}
            showTooltip={true}
            showValue={true}
            color="auto"
            label="Willingness to Pay"
            description="How willing users are to pay for a solution"
          />
          <span class="mono-label">WTP</span>
        </div>
        <div class="flex flex-col items-center gap-1">
          <div class="mentions-ring" style="width: 56px; height: 56px;">
            <span class="mentions-value">{mentionCount}</span>
          </div>
          <span class="mono-label">Mentions</span>
        </div>
      </div>
    </div>

    <!-- Description -->
    <div class="mb-4">
      <span class="mono-label mb-1.5 block">Description</span>
      <p class="text-text-secondary text-sm leading-relaxed whitespace-pre-line">{painPoint.description}</p>
    </div>

    <!-- Representative Quotes -->
    {#if painPoint.representativeQuotes && painPoint.representativeQuotes.length > 0}
      <div class="mb-4">
        <span class="mono-label mb-1.5 block">Evidence</span>
        <div class="quote-card">
          <p class="quote-card-text">{stripMarkdown(painPoint.representativeQuotes[0])}</p>
        </div>

        {#if extraQuotes.length > 0}
          {#if showAllQuotes}
            {#each extraQuotes as quote}
              <div class="quote-card" transition:slide={{ duration: 200 }}>
                <p class="quote-card-text">{stripMarkdown(quote)}</p>
              </div>
            {/each}
          {/if}
          <button
            type="button"
            class="quote-toggle"
            onclick={() => (showAllQuotes = !showAllQuotes)}
          >
            <MessageSquareQuote class="w-3.5 h-3.5" />
            <span>{showAllQuotes ? "Hide" : `Show ${extraQuotes.length} more`} quote{extraQuotes.length !== 1 ? "s" : ""}</span>
            <ChevronDown class="w-3.5 h-3.5 transition-transform duration-200 {showAllQuotes ? 'rotate-180' : ''}" />
          </button>
        {/if}
      </div>
    {/if}

    <!-- Metadata row: Platforms + Categories -->
    {#if (painPoint.sourcePlatforms?.length > 0) || (painPoint.categories?.length > 0)}
      <div class="flex flex-wrap gap-6 mb-4">
        {#if painPoint.sourcePlatforms?.length > 0}
          <div>
            <span class="mono-label mb-1.5 block">Platforms</span>
            <div class="flex flex-wrap gap-1.5">
              {#each painPoint.sourcePlatforms as platform}
                <Badge variant="info" size="sm">{platform}</Badge>
              {/each}
            </div>
          </div>
        {/if}
        {#if painPoint.categories?.length > 0}
          <div>
            <span class="mono-label mb-1.5 block">Categories</span>
            <div class="flex flex-wrap gap-1.5">
              {#each painPoint.categories as cat}
                <Badge variant="info" size="sm">{cat}</Badge>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Research Context -->
    {#if painPoint.sourceNiche}
      <details class="group">
        <summary class="flex items-center gap-2 cursor-pointer text-sm text-text-muted hover:text-text-secondary transition-colors py-2 select-none">
          <span class="transition-transform group-open:rotate-90">&#9654;</span>
          Original Research Context
        </summary>
        <div class="bg-bg-elevated/50 border border-border rounded-xl p-4 mt-2">
          <span class="text-sm text-text-secondary">{painPoint.sourceNiche}</span>
        </div>
      </details>
    {/if}
  </div>
{:else}
  <!-- Empty state -->
  <div class="flex flex-col items-center justify-center h-full min-h-[300px] p-8 text-center">
    <MousePointerClick class="w-8 h-8 text-text-muted opacity-30 mb-3" />
    <p class="text-sm text-text-muted font-medium">
      {totalCount} pain point{totalCount !== 1 ? "s" : ""} in {categoryName || "all categories"}
    </p>
    <p class="text-xs text-text-muted mt-1">
      Select one to explore severity, evidence, and market signals
    </p>
  </div>
{/if}

<style>
  /* Circular container for mentions count — matches ProgressRing visual weight */
  .mentions-ring {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 4px solid var(--color-border);
    background: var(--color-bg-elevated);
  }

  .mentions-value {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1;
  }

  /* Quote expand toggle with clear affordance */
  .quote-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    margin-top: 0.5rem;
    padding: 0.375rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: color 150ms ease, border-color 150ms ease;
  }

  .quote-toggle:hover {
    color: var(--color-text-secondary);
    border-color: var(--color-text-muted);
  }
</style>
