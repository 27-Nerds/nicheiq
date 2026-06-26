<script lang="ts">
  import { fade, fly } from "svelte/transition";
  import { portal } from "$lib/actions/portal";
  import { SvelteSet } from "svelte/reactivity";
  import Badge from "$lib/components/ui/Badge.svelte";
  import { originalityMetric } from "$lib/utils/solution-utils";
  import {
    X,
    Trash2,
    ChevronDown,
    Star,
  } from "lucide-svelte";

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
  let moveDropdownOpen = $state(false);

  const selectedCount = $derived(selectedPainPoints.size + selectedIdeas.size);
  const moveTargets = $derived(allCategories.filter((c) => c.id !== categoryId));

  // Lock body scroll when open
  $effect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = "";
      };
    }
  });

  // Fetch data when opened
  $effect(() => {
    if (open && categoryId) {
      fetchItems();
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      if (moveDropdownOpen) {
        moveDropdownOpen = false;
      } else {
        close();
      }
    }
  }

  function close() {
    open = false;
    selectedPainPoints = new SvelteSet();
    selectedIdeas = new SvelteSet();
    painPoints = [];
    ideas = [];
    moveDropdownOpen = false;
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
    moveDropdownOpen = false;
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

<svelte:window onkeydown={open ? handleKeydown : undefined} />

{#if open}
  <div use:portal>
    <!-- Backdrop -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      transition:fade={{ duration: 150 }}
      onclick={close}
      onkeydown={(e) => e.stopPropagation()}
    >
      <!-- Modal -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Manage category items"
        tabindex="-1"
        class="bg-bg-surface border border-border rounded-xl w-full max-w-3xl max-h-[80vh] flex flex-col"
        transition:fly={{ y: 20, duration: 200 }}
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => e.stopPropagation()}
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
          <div>
            <h2 class="text-lg font-semibold text-text-primary">Manage Items</h2>
            <p class="text-sm text-text-muted">{categoryName}</p>
          </div>
          <button onclick={close} class="p-1.5 rounded-lg hover:bg-bg-elevated text-text-muted hover:text-text-primary">
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- Toolbar (visible when items selected) -->
        {#if selectedCount > 0}
          <div class="flex items-center gap-3 px-6 py-2.5 bg-accent/5 border-b border-accent/20 flex-shrink-0">
            <span class="text-sm font-medium text-accent">{selectedCount} selected</span>
            <div class="flex items-center gap-2 ml-auto">
              <!-- Move dropdown -->
              <div class="relative">
                <button
                  class="btn-secondary text-xs flex items-center gap-1"
                  disabled={bulkInProgress || moveTargets.length === 0}
                  onclick={() => (moveDropdownOpen = !moveDropdownOpen)}
                >
                  Move to...
                  <ChevronDown class="w-3 h-3" />
                </button>
                {#if moveDropdownOpen}
                  <div class="absolute right-0 top-full mt-1 z-10 bg-bg-surface border border-border rounded-lg max-h-48 overflow-y-auto min-w-48">
                    {#each moveTargets as target}
                      <button
                        class="w-full text-left px-3 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary"
                        onclick={() => bulkMove(target.id)}
                      >
                        {target.name}
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
              <button
                class="btn-secondary text-xs text-error hover:bg-error/10"
                disabled={bulkInProgress}
                onclick={bulkDepublish}
              >
                <Trash2 class="w-3 h-3 mr-1 inline" />
                Depublish
              </button>
            </div>
          </div>
        {/if}

        <!-- Content -->
        <div class="flex-1 overflow-y-auto px-6 py-4">
          {#if loading}
            <div class="flex items-center justify-center py-12 text-text-muted text-sm">Loading...</div>
          {:else if painPoints.length === 0 && ideas.length === 0}
            <div class="flex items-center justify-center py-12 text-text-muted text-sm italic">No items in this category yet.</div>
          {:else}
            <!-- Pain Points section -->
            {#if painPoints.length > 0}
              <div class="mb-6">
                <div class="flex items-center gap-2 mb-3">
                  <input
                    type="checkbox"
                    checked={selectedPainPoints.size === painPoints.length}
                    onchange={toggleAllPainPoints}
                    class="rounded border-border"
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
                      />
                      <span class="text-sm text-text-primary flex-1 truncate">{pp.title}</span>
                      {#if pp.id === effectiveFreePreviewPainPointId}
                        <Badge variant="success" size="sm">Free preview</Badge>
                      {/if}
                      <Badge variant="default" size="sm">Sev {formatScore(pp.severityScore)}</Badge>
                      <Badge variant="warning" size="sm">WTP {formatScore(pp.commercialIntentScore)}</Badge>
                      <button
                        class="p-1 rounded hover:bg-accent/10 transition-opacity flex-shrink-0 {pp.id === effectiveFreePreviewPainPointId ? 'text-accent' : 'text-text-muted opacity-0 group-hover:opacity-100'}"
                        title={pp.id === effectiveFreePreviewPainPointId
                          ? "Free preview — click to clear (sub-niche becomes fully gated)"
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
              <hr class="border-border mb-6" />
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
                      />
                      <span class="text-sm text-text-primary flex-1 truncate">{idea.solutionName}</span>
                      {#if idea.id === effectiveFreePreviewIdeaId}
                        <Badge variant="success" size="sm">Free preview</Badge>
                      {/if}
                      <Badge variant="success" size="sm">Fit {formatScore(idea.marketFitScore)}</Badge>
                      <Badge variant="info" size="sm">{orig.short ?? "Orig"} {formatScore(orig.value)}</Badge>
                      <button
                        class="p-1 rounded hover:bg-accent/10 transition-opacity flex-shrink-0 {idea.id === effectiveFreePreviewIdeaId ? 'text-accent' : 'text-text-muted opacity-0 group-hover:opacity-100'}"
                        title={idea.id === effectiveFreePreviewIdeaId
                          ? "Free preview — click to clear (sub-niche becomes fully gated)"
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
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-between px-6 py-3 border-t border-border flex-shrink-0">
          <button class="text-sm text-text-secondary hover:text-text-primary" onclick={close}>Close</button>
          <span class="text-xs text-text-muted">
            {painPoints.length} pain points, {ideas.length} ideas
          </span>
        </div>
      </div>
    </div>
  </div>
{/if}
