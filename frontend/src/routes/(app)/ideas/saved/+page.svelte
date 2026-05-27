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
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import SavedIdeaCard from "./SavedIdeaCard.svelte";
  import LockedSavedCard from "./LockedSavedCard.svelte";
  import SavedPainTable from "./SavedPainTable.svelte";
  import DocketEmpty from "./DocketEmpty.svelte";
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

  // Visibility hierarchy:
  //   1. isPageEmpty (truly nothing saved) → page-level <DocketEmpty
  //      scope="page" /> renders, both sections are suppressed.
  //   2. Otherwise both sections always render. Inside each, the inner
  //      branch picks between populated cards, a `discover` empty (the
  //      OTHER type has saves, this one doesn't), or a `filter` empty
  //      (this type has saves globally but the Has-notes filter narrowed
  //      to none).
  // The 4-way AND on isPageEmpty guards against the +page.server.ts:45-65
  // counts fallback — if the counts fetch fails and returns zeros while
  // the list fetches succeed, the local arrays still have rows so the
  // sections render correctly instead of being suppressed.
  const ideasEmpty = $derived(ideas.length === 0);
  const painsEmpty = $derived(painPoints.length === 0);
  const isPageEmpty = $derived(
    ideasEmpty &&
      painsEmpty &&
      counts.ideas === 0 &&
      counts.painPoints === 0,
  );
  const showIdeas = $derived(!isPageEmpty);
  const showPains = $derived(!isPageEmpty);
  const num1 = $derived(showIdeas ? 1 : 0);
  const num2 = $derived(showPains ? 2 : 0);

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
          ? `/api/saves/ideas/${u.item.ideaId}`
          : `/api/saves/pain-points/${u.item.painPointId}`;
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
    // Optimistic local update (only accessible rows carry editable notes).
    ideas = ideas.map((i) => (i.id === item.id && !i.locked ? { ...i, notes } : i));
    try {
      const res = await fetch(`/api/saves/ideas/${item.ideaId}`, {
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
      p.id === item.id && !p.locked ? { ...p, notes } : p,
    );
    try {
      const res = await fetch(`/api/saves/pain-points/${item.painPointId}`, {
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

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

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

  {#if isPageEmpty}
    <DocketEmpty scope="page" />
  {/if}

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
            {#if item.locked}
              <LockedSavedCard
                kind="idea"
                createdAt={item.createdAt}
                onRemove={() => unsaveIdea(item)}
              />
            {:else}
              <SavedIdeaCard
                {item}
                onUnsave={unsaveIdea}
                onNotesChange={patchIdeaNotes}
              />
            {/if}
          </li>
        {/each}
      </ul>
    {:else if counts.ideas === 0}
      <DocketEmpty scope="section" subject="IDEAS" mode="discover" />
    {:else}
      <DocketEmpty
        scope="section"
        subject="IDEAS"
        mode="filter"
        onClearFilter={toggleHasNotesFilter}
      />
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
    {:else if counts.painPoints === 0}
      <DocketEmpty scope="section" subject="PAIN POINTS" mode="discover" />
    {:else}
      <DocketEmpty
        scope="section"
        subject="PAIN POINTS"
        mode="filter"
        onClearFilter={toggleHasNotesFilter}
      />
    {/if}
  {/if}
</div>

{#if pendingUndo}
  <UndoToast
    message={pendingUndo.kind === "idea"
      ? `Removed "${pendingUndo.item.idea?.headline ?? pendingUndo.item.idea?.solutionName ?? "idea"}"`
      : `Removed "${pendingUndo.item.painPoint?.title ?? "pain point"}"`}
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

</style>
