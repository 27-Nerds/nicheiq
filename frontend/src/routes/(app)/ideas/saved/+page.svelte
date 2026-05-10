<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import { untrack } from "svelte";
  import type {
    SavedIdeaItem,
    SavedPainPointItem,
  } from "$lib/types/saved";
  import StatStrip, {
    type Stat,
  } from "$lib/components/catalog/seo/StatStrip.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";
  import { CategoryBreadcrumbs } from "$lib/components/catalog/seo";
  import SavedIdeaCard from "./SavedIdeaCard.svelte";
  import SavedPainTable from "./SavedPainTable.svelte";
  import UndoToast from "./UndoToast.svelte";
  import { formatDistanceToNow } from "./formatRelative";

  let { data } = $props();

  // Local copies of the server-provided lists so optimistic mutations don't
  // need a full SvelteKit round-trip. invalidateAll() resyncs after toast
  // timeout so the server stays the source of truth. untrack avoids the
  // "captures only initial value of `data`" warning — the $effect below is
  // responsible for keeping these in sync with subsequent loader runs.
  let ideas = $state<SavedIdeaItem[]>(untrack(() => data.ideas));
  let painPoints = $state<SavedPainPointItem[]>(untrack(() => data.painPoints));
  let counts = $state(untrack(() => data.counts));

  // Re-sync local state when the loader returns fresh data (e.g. after a
  // filter change navigation).
  $effect(() => {
    ideas = data.ideas;
    painPoints = data.painPoints;
    counts = data.counts;
  });

  type PendingUndo =
    | { kind: "idea"; item: SavedIdeaItem; index: number }
    | { kind: "painPoint"; item: SavedPainPointItem; index: number };

  let pendingUndo = $state<PendingUndo | null>(null);

  // Has-notes filter chip state (URL-synced).
  const hasNotesActive = $derived(data.filters.hasNotes);

  function toggleHasNotesFilter() {
    const params = new URLSearchParams(page.url.searchParams);
    if (hasNotesActive) params.delete("hasNotes");
    else params.set("hasNotes", "1");
    const qs = params.toString();
    goto(`/ideas/saved${qs ? "?" + qs : ""}`, {
      replaceState: true,
      keepFocus: true,
      noScroll: true,
    });
  }

  // Most-recent save across both lists — drives the "Last added" StatStrip
  // tile so the docket has a chronological anchor. Backend returns saves
  // newest-first per type (saves.ts:189-202, :303-316), so [0] of each
  // local array is the recent end. Compare the two to pick the freshest.
  const lastAddedIso = $derived.by<string | null>(() => {
    const ts = [ideas[0]?.createdAt, painPoints[0]?.createdAt].filter(
      (t): t is string => typeof t === "string" && t.length > 0,
    );
    if (ts.length === 0) return null;
    return ts.sort().reverse()[0];
  });
  const lastAddedRelative = $derived(
    lastAddedIso ? formatDistanceToNow(lastAddedIso) : null,
  );

  // Stat strip composition. First cell is the total (emphasized via
  // StatStrip's existing `emphasis` prop — first column 1.4fr + bg-1 tint).
  // Fourth tile shows the relative time of the most recent save — turns the
  // strip from a static count into a docket-activity signal.
  const stats = $derived<Stat[]>([
    { value: counts.ideas + counts.painPoints, label: "Total saved" },
    { value: counts.ideas, label: "Ideas" },
    { value: counts.painPoints, label: "Pain points" },
    { value: lastAddedRelative ?? "—", label: "Last added" },
  ]);

  // Section visibility — render the section frame whenever there's saved
  // content OR a visible empty list. Section is only fully hidden when the
  // unfiltered global count is zero AND the local list is empty (i.e. the
  // user has truly nothing saved of that type). This guarantees the
  // designed empty block renders in the filtered-empty case (?hasNotes=1
  // with no notes on saved items).
  const ideasEmpty = $derived(ideas.length === 0);
  const painsEmpty = $derived(painPoints.length === 0);
  const showIdeas = $derived(!ideasEmpty || counts.ideas > 0);
  const showPains = $derived(!painsEmpty || counts.painPoints > 0);
  const num1 = $derived(showIdeas ? 1 : 0);
  const num2 = $derived(showPains ? num1 + 1 : num1);

  // ============================================
  // Optimistic mutations
  // ============================================

  async function unsaveIdea(item: SavedIdeaItem) {
    const idx = ideas.findIndex((i) => i.id === item.id);
    if (idx === -1) return;
    ideas = ideas.filter((i) => i.id !== item.id);
    counts = { ...counts, ideas: counts.ideas - 1 };
    pendingUndo = { kind: "idea", item, index: idx };
  }

  async function unsavePainPoint(item: SavedPainPointItem) {
    const idx = painPoints.findIndex((p) => p.id === item.id);
    if (idx === -1) return;
    painPoints = painPoints.filter((p) => p.id !== item.id);
    counts = { ...counts, painPoints: counts.painPoints - 1 };
    pendingUndo = { kind: "painPoint", item, index: idx };
  }

  function undoLast() {
    if (!pendingUndo) return;
    if (pendingUndo.kind === "idea") {
      const restored = [...ideas];
      restored.splice(pendingUndo.index, 0, pendingUndo.item);
      ideas = restored;
      counts = { ...counts, ideas: counts.ideas + 1 };
    } else {
      const restored = [...painPoints];
      restored.splice(pendingUndo.index, 0, pendingUndo.item);
      painPoints = restored;
      counts = { ...counts, painPoints: counts.painPoints + 1 };
    }
    pendingUndo = null;
  }

  async function commitUnsave() {
    if (!pendingUndo) return;
    const u = pendingUndo;
    pendingUndo = null;
    try {
      const path =
        u.kind === "idea"
          ? `/api/saves/ideas/${u.item.idea.id}`
          : `/api/saves/pain-points/${u.item.painPoint.id}`;
      const res = await fetch(path, {
        method: "DELETE",
        credentials: "same-origin",
      });
      if (!res.ok && res.status !== 404) throw new Error(`Delete failed: ${res.status}`);
    } catch (err) {
      console.error("Unsave commit failed:", err);
      // Resync from server so the user sees the true state.
      await invalidateAll();
    }
  }

  async function patchIdeaNotes(item: SavedIdeaItem, notes: string | null) {
    // Optimistic local update.
    ideas = ideas.map((i) => (i.id === item.id ? { ...i, notes } : i));
    try {
      const res = await fetch(`/api/saves/ideas/${item.idea.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ notes }),
      });
      if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
    } catch (err) {
      console.error("Note save failed:", err);
      await invalidateAll();
    }
  }

  async function patchPainNotes(item: SavedPainPointItem, notes: string | null) {
    painPoints = painPoints.map((p) =>
      p.id === item.id ? { ...p, notes } : p,
    );
    try {
      const res = await fetch(`/api/saves/pain-points/${item.painPoint.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ notes }),
      });
      if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
    } catch (err) {
      console.error("Note save failed:", err);
      await invalidateAll();
    }
  }
</script>

<svelte:head>
  <title>Saved · NicheIQ</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="saved-page">
  <CategoryBreadcrumbs
    trail={[
      { label: "Home", href: "/" },
      { label: "Catalog", href: "/ideas" },
      { label: "Saved" },
    ]}
  />

  <header class="hero">
    <span class="eyebrow">SAVED · YOUR DOCKET</span>
    <h1>Your research docket.</h1>
    <p class="lede">
      Ideas and pain points you've kept for later validation. Each entry stays
      here until you remove it.
    </p>
    <div class="strip-wrap">
      <StatStrip {stats} emphasis />
    </div>
    <!-- Filter row — single chip in v1; expand to verdict/sort chips later. -->
    <div class="filter-row" aria-label="Filter saved items">
      <button
        type="button"
        class="chip"
        class:active={hasNotesActive}
        onclick={toggleHasNotesFilter}
        aria-pressed={hasNotesActive}
      >
        Has notes
      </button>
    </div>
  </header>

  {#if showIdeas}
    <SectionDivider
      num={num1}
      label="Ideas"
      metaText={`${counts.ideas} saved`}
    />
    {#if !ideasEmpty}
      <ul class="cards-grid">
        {#each ideas as item, i (item.id)}
          <li style="--i: {Math.min(i, 5)}">
            <SavedIdeaCard
              {item}
              onUnsave={unsaveIdea}
              onNotesChange={patchIdeaNotes}
            />
          </li>
        {/each}
      </ul>
    {:else}
      <aside class="docket-empty" role="status" aria-live="polite">
        <span class="docket-empty-num" aria-hidden="true">00</span>
        <h3>{hasNotesActive ? "No saved ideas with notes." : "No ideas saved yet."}</h3>
        <p>
          {hasNotesActive
            ? "Add a note to a saved idea to make it visible here."
            : "Bookmark ideas from the catalog to keep them here for review."}
        </p>
        {#if hasNotesActive}
          <button type="button" class="docket-empty-cta" onclick={toggleHasNotesFilter}>
            Show all saves →
          </button>
        {:else}
          <a class="docket-empty-cta" href="/ideas">Browse the catalog →</a>
        {/if}
      </aside>
    {/if}
  {/if}

  {#if showPains}
    <SectionDivider
      num={num2}
      label="Pain points"
      metaText={`${counts.painPoints} saved`}
    />
    {#if !painsEmpty}
      <SavedPainTable
        items={painPoints}
        onUnsave={unsavePainPoint}
        onNotesChange={patchPainNotes}
      />
    {:else}
      <aside class="docket-empty" role="status" aria-live="polite">
        <span class="docket-empty-num" aria-hidden="true">00</span>
        <h3>{hasNotesActive ? "No saved pain points with notes." : "No pain points saved yet."}</h3>
        <p>
          {hasNotesActive
            ? "Add a note to a saved pain point to make it visible here."
            : "Bookmark pain points from the catalog to keep them here for review."}
        </p>
        {#if hasNotesActive}
          <button type="button" class="docket-empty-cta" onclick={toggleHasNotesFilter}>
            Show all saves →
          </button>
        {:else}
          <a class="docket-empty-cta" href="/ideas">Browse the catalog →</a>
        {/if}
      </aside>
    {/if}
  {/if}
</div>

{#if pendingUndo}
  <UndoToast
    message={pendingUndo.kind === "idea"
      ? `Removed "${pendingUndo.item.idea.headline ?? pendingUndo.item.idea.solutionName}"`
      : `Removed "${pendingUndo.item.painPoint.title}"`}
    onUndo={undoLast}
    onTimeout={commitUnsave}
  />
{/if}

<style>
  .saved-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
  }

  .hero {
    padding: 32px 0 28px;
    border-bottom: 1px solid var(--color-border);
    margin-bottom: 24px;
  }
  .eyebrow {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--color-accent);
    margin-bottom: 14px;
  }
  h1 {
    font-size: 32px;
    font-weight: 600;
    line-height: 1.15;
    letter-spacing: -0.025em;
    color: var(--color-text-primary);
    max-width: 640px;
    text-wrap: balance;
    margin: 0 0 0.625rem;
  }
  .lede {
    font-size: 0.9375rem;
    line-height: 1.65;
    color: var(--color-text-secondary);
    max-width: 56ch;
    margin: 0 0 22px;
    text-wrap: pretty;
  }
  .strip-wrap {
    margin-bottom: 18px;
  }

  .filter-row {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 11px;
    border-radius: 6px;
    font-size: 12px;
    color: var(--color-text-secondary);
    font-weight: 500;
    border: 1px solid var(--color-border);
    background: var(--color-surface, #fff);
    cursor: pointer;
    font-family: inherit;
    transition:
      color 0.12s ease,
      border-color 0.12s ease,
      background 0.12s ease;
  }
  .chip:hover {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .chip.active {
    background: var(--color-text-primary);
    color: var(--color-surface, #fff);
    border-color: var(--color-text-primary);
  }

  .cards-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: 1fr;
    list-style: none;
    padding: 0;
    margin: 0 0 24px;
    /* Drives the per-card folio number rendered inside SavedIdeaCard
       (`<span class="folio">::before { content: counter(folio, decimal-leading-zero); }`).
       Auto-renumbers on optimistic remove + undo without any JS. */
    counter-reset: folio;
  }
  @media (min-width: 768px) {
    .cards-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  @media (min-width: 1024px) {
    .cards-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  /* Designed empty block — replaces the older single-line
     "00 ideas saved." placeholder. Reads as a deliberate empty-state
     artifact rather than a missing-data row. */
  .docket-empty {
    border: 1px dashed var(--color-border-emphasis);
    border-radius: 8px;
    padding: 2.5rem 2rem;
    margin: 1.5rem 0 2.5rem;
    text-align: center;
  }
  .docket-empty-num {
    display: block;
    font-family: var(--font-mono);
    font-size: 2.25rem;
    font-weight: 500;
    letter-spacing: -0.02em;
    color: var(--color-text-muted);
    font-feature-settings: "tnum";
    margin-bottom: 0.5rem;
  }
  .docket-empty h3 {
    font-family: var(--font-display);
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 0.375rem;
  }
  .docket-empty p {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    max-width: 36ch;
    margin: 0 auto 1rem;
  }
  .docket-empty-cta {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-accent);
    letter-spacing: 0.04em;
    text-decoration: none;
    border: 0;
    border-bottom: 1px solid currentColor;
    padding: 0 0 1px;
    background: transparent;
    cursor: pointer;
  }
  .docket-empty-cta:hover {
    color: var(--color-accent-hover, var(--color-accent));
  }
  .docket-empty-cta:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 2px;
  }
</style>
