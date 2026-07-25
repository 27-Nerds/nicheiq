<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import ConfirmGate from "$lib/components/ui/ConfirmGate.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import { originalityMetric } from "$lib/utils/solution-utils";
  import { Trash2, Star } from "lucide-svelte";

  interface PainPointItem {
    id: string;
    title: string;
    severityScore: number;
    commercialIntentScore: number;
    isFreePreview: boolean;
  }

  interface IdeaItem {
    id: string;
    solutionName: string;
    marketFitScore: number | null;
    noveltyScore: number | null;
    obviousnessScore: number | null;
    isFreePreview: boolean;
  }

  interface Props {
    open: boolean;
    categoryId: string;
    categoryName: string;
    allCategories: { id: string; name: string }[];
    onMutated: () => void;
  }

  let {
    open = $bindable(),
    categoryId,
    categoryName,
    allCategories,
    onMutated,
  }: Props = $props();

  let painPoints = $state<PainPointItem[]>([]);
  let ideas = $state<IdeaItem[]>([]);
  // The single free-preview (publicly visible) item per type — the admin pin, or null
  // when none is set (the sub-niche is then fully gated). Returned by the backend.
  let effectiveFreePreviewIdeaId = $state<string | null>(null);
  let effectiveFreePreviewPainPointId = $state<string | null>(null);
  let loading = $state(false);
  let selectedPainPoints = $state(new SvelteSet<string>());
  let selectedIdeas = $state(new SvelteSet<string>());
  let bulkInProgress = $state(false);

  const selectedCount = $derived(selectedPainPoints.size + selectedIdeas.size);
  const moveTargets = $derived(allCategories.filter((c) => c.id !== categoryId));
  const footerMessage = $derived(
    selectedCount > 0
      ? `${selectedCount} selected`
      : `${painPoints.length} pain points · ${ideas.length} ideas`,
  );

  // Fetch data when opened
  $effect(() => {
    if (open && categoryId) {
      fetchItems();
    }
  });

  function close() {
    open = false;
    selectedPainPoints = new SvelteSet();
    selectedIdeas = new SvelteSet();
    painPoints = [];
    ideas = [];
  }

  async function fetchItems() {
    loading = true;
    try {
      const [ppRes, ideasRes] = await Promise.all([
        fetch(`/api/admin/catalog/categories/${categoryId}/pain-points`),
        fetch(`/api/admin/catalog/categories/${categoryId}/ideas`),
      ]);
      if (ppRes.ok) {
        const data = await ppRes.json();
        painPoints = data.painPoints ?? [];
        effectiveFreePreviewPainPointId = data.effectiveFreePreviewPainPointId ?? null;
      }
      if (ideasRes.ok) {
        const data = await ideasRes.json();
        ideas = data.ideas ?? [];
        effectiveFreePreviewIdeaId = data.effectiveFreePreviewIdeaId ?? null;
      }
    } catch (err) {
      console.error("Failed to fetch category items:", err);
    } finally {
      loading = false;
    }
  }

  // Set (or clear) the free-preview idea/pain for this category. The backend enforces
  // the single-free-preview invariant (clears any other pin in the category); we refetch
  // so the highlight + effective pick reflect the new state. Clearing leaves the sub-niche
  // fully gated (no free item).
  async function setFreePreview(type: "idea" | "pain-point", id: string, value: boolean) {
    const path =
      type === "idea"
        ? `/api/admin/catalog/ideas/${id}`
        : `/api/admin/catalog/pain-points/${id}`;
    const res = await fetch(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isFreePreview: value }),
    });
    if (res.ok) {
      await fetchItems();
      onMutated();
    }
  }

  async function depublishSingleIdea(id: string) {
    const res = await fetch(`/api/admin/catalog/ideas/${id}`, { method: "DELETE" });
    if (res.ok) {
      ideas = ideas.filter((i) => i.id !== id);
      selectedIdeas.delete(id);
      onMutated();
    }
  }

  async function depublishSinglePainPoint(id: string) {
    const res = await fetch(`/api/admin/catalog/pain-points/${id}`, { method: "DELETE" });
    if (res.ok) {
      painPoints = painPoints.filter((p) => p.id !== id);
      selectedPainPoints.delete(id);
      onMutated();
    }
  }

  async function bulkDepublish() {
    bulkInProgress = true;
    const ops: Promise<Response>[] = [];

    for (const id of selectedPainPoints) {
      ops.push(fetch(`/api/admin/catalog/pain-points/${id}`, { method: "DELETE" }));
    }
    for (const id of selectedIdeas) {
      ops.push(fetch(`/api/admin/catalog/ideas/${id}`, { method: "DELETE" }));
    }

    const results = await Promise.allSettled(ops);
    const failed = results.filter((r) => r.status === "rejected" || (r.status === "fulfilled" && !r.value.ok)).length;

    // Optimistic removal
    painPoints = painPoints.filter((p) => !selectedPainPoints.has(p.id));
    ideas = ideas.filter((i) => !selectedIdeas.has(i.id));
    selectedPainPoints = new SvelteSet();
    selectedIdeas = new SvelteSet();
    bulkInProgress = false;

    if (failed > 0) {
      console.error(`${failed} depublish operations failed`);
    }
    onMutated();
  }

  async function bulkMove(targetCategoryId: string) {
    bulkInProgress = true;
    const ops: Promise<Response>[] = [];

    for (const id of selectedPainPoints) {
      ops.push(
        fetch(`/api/admin/catalog/pain-points/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ categoryId: targetCategoryId }),
        }),
      );
    }
    for (const id of selectedIdeas) {
      ops.push(
        fetch(`/api/admin/catalog/ideas/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ categoryId: targetCategoryId }),
        }),
      );
    }

    const results = await Promise.allSettled(ops);
    const failed = results.filter((r) => r.status === "rejected" || (r.status === "fulfilled" && !r.value.ok)).length;

    // Optimistic removal from current view
    painPoints = painPoints.filter((p) => !selectedPainPoints.has(p.id));
    ideas = ideas.filter((i) => !selectedIdeas.has(i.id));
    selectedPainPoints = new SvelteSet();
    selectedIdeas = new SvelteSet();
    bulkInProgress = false;

    if (failed > 0) {
      console.error(`${failed} move operations failed`);
    }
    onMutated();
  }

  function handleMoveChange(event: Event) {
    const select = event.currentTarget as HTMLSelectElement;
    const target = select.value;
    select.value = "";
    if (target) bulkMove(target);
  }

  function toggleAllPainPoints() {
    if (selectedPainPoints.size === painPoints.length) {
      selectedPainPoints = new SvelteSet();
    } else {
      selectedPainPoints = new SvelteSet(painPoints.map((p) => p.id));
    }
  }

  function toggleAllIdeas() {
    if (selectedIdeas.size === ideas.length) {
      selectedIdeas = new SvelteSet();
    } else {
      selectedIdeas = new SvelteSet(ideas.map((i) => i.id));
    }
  }

  function formatScore(val: number | null | undefined): string {
    if (val == null) return "—";
    return (val * 10).toFixed(1);
  }
</script>

<FormOverlay
  {open}
  eyebrow="Catalog admin"
  title={categoryName}
  description="Depublish items, move them between categories, or pin the free preview."
  {footerMessage}
  onRequestClose={close}
>
  {#if loading}
    <div class="flex items-center justify-center py-12 text-text-muted text-sm">Loading…</div>
  {:else if painPoints.length === 0 && ideas.length === 0}
    <EmptyState
      title="No items in this category yet."
      description="Published pain points and ideas will show up here."
    />
  {:else}
    <!-- Pain Points section -->
    {#if painPoints.length > 0}
      <div>
        <div class="flex items-center gap-2 mb-3">
          <input
            type="checkbox"
            checked={selectedPainPoints.size === painPoints.length}
            onchange={toggleAllPainPoints}
            class="rounded border-border"
            aria-label="Select all pain points"
          />
          <h3 class="text-sm font-semibold text-text-secondary">Pain Points ({painPoints.length})</h3>
        </div>
        <div class="space-y-1">
          {#each painPoints as pp}
            <div class="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-bg-elevated group">
              <input
                type="checkbox"
                checked={selectedPainPoints.has(pp.id)}
                onchange={() => {
                  if (selectedPainPoints.has(pp.id)) selectedPainPoints.delete(pp.id);
                  else selectedPainPoints.add(pp.id);
                }}
                class="rounded border-border flex-shrink-0"
                aria-label={`Select ${pp.title}`}
              />
              <span class="text-sm text-text-primary flex-1 truncate">{pp.title}</span>
              {#if pp.id === effectiveFreePreviewPainPointId}
                <Badge variant="success" size="sm">Free preview</Badge>
              {/if}
              <Badge variant="default" size="sm">Sev {formatScore(pp.severityScore)}</Badge>
              <Badge variant="warning" size="sm">CI {formatScore(pp.commercialIntentScore)}</Badge>
              <button
                class="p-1 rounded hover:bg-accent/10 transition-opacity flex-shrink-0 {pp.id === effectiveFreePreviewPainPointId ? 'text-accent' : 'text-text-muted opacity-0 group-hover:opacity-100'}"
                title={pp.id === effectiveFreePreviewPainPointId
                  ? "Free preview: click to clear (sub-niche becomes fully gated)"
                  : "Set as the free preview"}
                onclick={() => setFreePreview("pain-point", pp.id, !pp.isFreePreview)}
              >
                <Star class="w-3.5 h-3.5" fill={pp.id === effectiveFreePreviewPainPointId ? "currentColor" : "none"} />
              </button>
              <button
                class="p-1 rounded hover:bg-error/10 text-text-muted hover:text-error opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                title="Depublish"
                onclick={() => depublishSinglePainPoint(pp.id)}
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Divider -->
    {#if painPoints.length > 0 && ideas.length > 0}
      <hr class="border-border" />
    {/if}

    <!-- Ideas section -->
    {#if ideas.length > 0}
      <div>
        <div class="flex items-center gap-2 mb-3">
          <input
            type="checkbox"
            checked={selectedIdeas.size === ideas.length}
            onchange={toggleAllIdeas}
            class="rounded border-border"
            aria-label="Select all ideas"
          />
          <h3 class="text-sm font-semibold text-text-secondary">Ideas ({ideas.length})</h3>
        </div>
        <div class="space-y-1">
          {#each ideas as idea}
            {@const orig = originalityMetric({ obviousness_score: idea.obviousnessScore, novelty_score: idea.noveltyScore })}
            <div class="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-bg-elevated group">
              <input
                type="checkbox"
                checked={selectedIdeas.has(idea.id)}
                onchange={() => {
                  if (selectedIdeas.has(idea.id)) selectedIdeas.delete(idea.id);
                  else selectedIdeas.add(idea.id);
                }}
                class="rounded border-border flex-shrink-0"
                aria-label={`Select ${idea.solutionName}`}
              />
              <span class="text-sm text-text-primary flex-1 truncate">{idea.solutionName}</span>
              {#if idea.id === effectiveFreePreviewIdeaId}
                <Badge variant="success" size="sm">Free preview</Badge>
              {/if}
              <Badge variant="success" size="sm">Fit {formatScore(idea.marketFitScore)}</Badge>
              <Badge variant="info" size="sm">{orig.short ?? "Distinct"} {formatScore(orig.value)}</Badge>
              <button
                class="p-1 rounded hover:bg-accent/10 transition-opacity flex-shrink-0 {idea.id === effectiveFreePreviewIdeaId ? 'text-accent' : 'text-text-muted opacity-0 group-hover:opacity-100'}"
                title={idea.id === effectiveFreePreviewIdeaId
                  ? "Free preview: click to clear (sub-niche becomes fully gated)"
                  : "Set as the free preview"}
                onclick={() => setFreePreview("idea", idea.id, !idea.isFreePreview)}
              >
                <Star class="w-3.5 h-3.5" fill={idea.id === effectiveFreePreviewIdeaId ? "currentColor" : "none"} />
              </button>
              <button
                class="p-1 rounded hover:bg-error/10 text-text-muted hover:text-error opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                title="Depublish"
                onclick={() => depublishSingleIdea(idea.id)}
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" onclick={close}>Close</button>
  {/snippet}
  {#snippet footer()}
    {#if selectedCount > 0}
      <div class="bulk-actions">
        <label class="sr-only" for="category-items-move">Move selected items to category</label>
        <select
          id="category-items-move"
          class="bulk-move"
          disabled={bulkInProgress || moveTargets.length === 0}
          onchange={handleMoveChange}
        >
          <option value="" selected>Move to…</option>
          {#each moveTargets as target}
            <option value={target.id}>{target.name}</option>
          {/each}
        </select>
        <ConfirmGate
          label="Depublish"
          confirmLabel={`Depublish ${selectedCount}`}
          variant="free"
          consequence="REMOVED FROM PUBLIC CATALOG"
          busy={bulkInProgress}
          onConfirm={bulkDepublish}
        />
      </div>
    {/if}
  {/snippet}
</FormOverlay>

<style>
  .bulk-actions {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .bulk-move {
    min-height: 2.1rem;
    padding: 0 0.65rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 600;
    cursor: pointer;
  }

  .bulk-move:hover:not(:disabled) {
    border-color: var(--color-input-border-hover);
    color: var(--color-text-primary);
  }

  .bulk-move:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .bulk-move:disabled {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }
</style>
