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
    goto(`/saved${qs ? "?" + qs : ""}`, {
      replaceState: true,
      keepFocus: true,
      noScroll: true,
    });
  }

  // Stat strip composition. First cell is the total (emphasized via
  // StatStrip's existing `emphasis` prop — first column 1.4fr + bg-1 tint).
  const stats = $derived<Stat[]>([
    { value: counts.ideas + counts.painPoints, label: "Total saved" },
    { value: counts.ideas, label: "Ideas" },
    { value: counts.painPoints, label: "Pain points" },
  ]);

  // Section numbering — derived dynamically so hidden sections don't leave
  // gaps in the count (matches the catalog index pattern).
  const showIdeas = $derived(ideas.length > 0 || counts.ideas === 0);
  const showPains = $derived(painPoints.length > 0 || counts.painPoints === 0);
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
    <h1>Your ideas and pain points<br />— kept for later validation.</h1>
    <div class="strip-wrap">
      <StatStrip {stats} emphasis />
    </div>
    <!-- Filter row — single chip in v1; expand to verdict/sort chips later. -->
    <div class="filter-row">
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
    {#if ideas.length > 0}
      <ul class="cards-grid">
        {#each ideas as item (item.id)}
          <li>
            <SavedIdeaCard
              {item}
              onUnsave={unsaveIdea}
              onNotesChange={patchIdeaNotes}
            />
          </li>
        {/each}
      </ul>
    {:else}
      <p class="empty-state">
        <span class="empty-num">00</span> ideas saved.
        <a href="/ideas">Browse the catalog →</a>
      </p>
    {/if}
  {/if}

  {#if showPains}
    <SectionDivider
      num={num2}
      label="Pain points"
      metaText={`${counts.painPoints} saved`}
    />
    {#if painPoints.length > 0}
      <SavedPainTable
        items={painPoints}
        onUnsave={unsavePainPoint}
        onNotesChange={patchPainNotes}
      />
    {:else}
      <p class="empty-state">
        <span class="empty-num">00</span> pain points saved.
        <a href="/ideas">Browse the catalog →</a>
      </p>
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
    margin: 0 0 22px;
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

  .empty-state {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--color-text-muted);
    text-align: center;
    margin: 3rem 0;
  }
  .empty-num {
    color: var(--color-text-secondary);
    font-weight: 600;
    margin-right: 6px;
  }
  .empty-state a {
    color: var(--color-accent);
    text-decoration: underline;
    text-underline-offset: 2px;
    margin-left: 6px;
  }
</style>
