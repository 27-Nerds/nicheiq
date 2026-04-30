<script lang="ts">
  import { untrack } from "svelte";
  import { invalidateAll } from "$app/navigation";
  import Badge from "$lib/components/ui/Badge.svelte";
  import { groupCategories } from "$lib/utils/catalog-utils";
  import { SvelteSet, SvelteMap } from "svelte/reactivity";
  import CategoryItemsModal from "./CategoryItemsModal.svelte";
  import {
    ChevronRight,
    ChevronDown,
    Plus,
    Pencil,
    Trash2,
    FolderOpen,
    Loader2,
    Sparkles,
    X,
    Lightbulb,
    Check,
    Search,
    Eye,
    FileText,
  } from "lucide-svelte";

  let { categories }: {
    categories: any[];
  } = $props();

  // ============================================
  // Categories tab state
  // ============================================

  let showCreateForm = $state(false);
  let editingId = $state<string | null>(null);
  let saving = $state(false);
  let deletingId = $state<string | null>(null);
  let catErrorMsg = $state("");

  let newName = $state("");
  let newDescription = $state("");
  let newParentId = $state("");
  let newSortOrder = $state(0);

  let editName = $state("");
  let editDescription = $state("");
  let editParentId = $state("");
  let editSortOrder = $state(0);

  const topLevelCategories = $derived(
    (categories || []).filter((c: any) => !c.parentId),
  );

  // ============================================
  // Category Items Modal state
  // ============================================

  let itemsModalOpen = $state(false);
  let itemsModalCategoryId = $state("");
  let itemsModalCategoryName = $state("");

  const allChildCategories = $derived.by(() => {
    const result: { id: string; name: string }[] = [];
    for (const cat of categories || []) {
      if (cat.children) {
        for (const child of cat.children) {
          result.push({ id: child.id, name: `${cat.name} > ${child.name}` });
        }
      }
    }
    return result;
  });

  function openItemsModal(childId: string, parentName: string, childName: string) {
    itemsModalCategoryId = childId;
    itemsModalCategoryName = `${parentName} > ${childName}`;
    itemsModalOpen = true;
  }

  // ============================================
  // Search + Filter state
  // ============================================

  let searchQuery = $state("");
  let debouncedQuery = $state("");

  $effect(() => {
    const q = searchQuery;
    if (q === "") {
      debouncedQuery = "";
      return;
    }
    const timer = setTimeout(() => { debouncedQuery = q; }, 200);
    return () => clearTimeout(timer);
  });

  let statusFilter = $state<"all" | "empty" | "in_progress" | "done">("all");
  let expandedParents = new SvelteSet<string>();
  let expandedSuperGroups = new SvelteSet<string>();

  // Default all super-groups to expanded on first render
  $effect(() => {
    if (expandedSuperGroups.size === 0 && categories?.length > 0) {
      const groups = groupCategories(categories);
      for (const sg of groups) {
        expandedSuperGroups.add(sg.name);
      }
    }
  });

  // ============================================
  // Helper functions
  // ============================================

  function childHasPainPoints(child: any): boolean {
    return (child._count?.painPoints ?? 0) > 0;
  }

  function childHasIdeas(child: any): boolean {
    return (child._count?.ideas ?? 0) > 0;
  }

  function childIsComplete(child: any): boolean {
    return childHasPainPoints(child) && childHasIdeas(child);
  }

  function childStatus(child: any): "empty" | "in_progress" | "done" {
    if (childIsComplete(child)) return "done";
    if (childHasPainPoints(child) || childHasIdeas(child)) return "in_progress";
    return "empty";
  }

  function parentStats(parent: any): { total: number; done: number; inProgress: number; empty: number } {
    const children = parent.children || [];
    let done = 0, inProgress = 0, empty = 0;
    for (const c of children) {
      const s = childStatus(c);
      if (s === "done") done++;
      else if (s === "in_progress") inProgress++;
      else empty++;
    }
    return { total: children.length, done, inProgress, empty };
  }

  // ============================================
  // Derived values
  // ============================================

  const globalStats = $derived.by(() => {
    let empty = 0, inProgress = 0, done = 0, total = 0;
    for (const parent of categories || []) {
      for (const child of parent.children || []) {
        total++;
        const s = childStatus(child);
        if (s === "done") done++;
        else if (s === "in_progress") inProgress++;
        else empty++;
      }
    }
    return { total, empty, inProgress, done };
  });

  const filteredGroups = $derived.by(() => {
    const query = debouncedQuery.toLowerCase().trim();
    const hasFilter = query !== "" || statusFilter !== "all";

    const superGroups = groupCategories(categories || []);

    return superGroups.map((sg) => {
      const filteredParents = sg.categories
        .map((parent: any) => {
          const children = parent.children || [];
          const filteredChildren = children.filter((child: any) => {
            if (statusFilter !== "all" && childStatus(child) !== statusFilter) return false;
            if (query) {
              const parentMatch = parent.name.toLowerCase().includes(query);
              const childNameMatch = child.name.toLowerCase().includes(query);
              const childDescMatch = (child.description || "").toLowerCase().includes(query);
              if (!parentMatch && !childNameMatch && !childDescMatch) return false;
            }
            return true;
          });

          const parentNameMatches = query && parent.name.toLowerCase().includes(query);
          const visibleChildren = parentNameMatches && statusFilter === "all"
            ? children
            : filteredChildren;

          return { ...parent, children: visibleChildren, _hasFilterMatch: hasFilter && visibleChildren.length > 0 };
        })
        .filter((parent: any) => parent.children.length > 0);

      return {
        name: sg.name,
        parents: filteredParents,
        _hasFilterMatch: hasFilter && filteredParents.length > 0,
      };
    }).filter((sg) => sg.parents.length > 0);
  });

  const filteredChildCount = $derived.by(() => {
    let count = 0;
    for (const sg of filteredGroups) {
      for (const p of sg.parents) {
        count += (p.children || []).length;
      }
    }
    return count;
  });

  const isFiltering = $derived(debouncedQuery.trim() !== "" || statusFilter !== "all");

  function toggleParent(id: string) {
    if (expandedParents.has(id)) expandedParents.delete(id);
    else expandedParents.add(id);
  }

  function isParentExpanded(parentId: string, hasFilterMatch: boolean): boolean {
    if (isFiltering && hasFilterMatch) return true;
    return expandedParents.has(parentId);
  }

  function toggleSuperGroup(name: string) {
    if (expandedSuperGroups.has(name)) expandedSuperGroups.delete(name);
    else expandedSuperGroups.add(name);
  }

  function isSuperGroupExpanded(name: string, hasFilterMatch: boolean): boolean {
    if (isFiltering && hasFilterMatch) return true;
    // Auto-expand if any child within this group is generating
    if (generatingPainPointsFor.size > 0 || generatingIdeasFor.size > 0) {
      for (const parent of categories || []) {
        if ((parent.superGroup?.name || "Other") !== name) continue;
        for (const child of parent.children || []) {
          if (generatingPainPointsFor.has(child.id) || generatingIdeasFor.has(child.id)) return true;
        }
      }
    }
    return expandedSuperGroups.has(name);
  }

  function superGroupStats(sgName: string): { total: number; done: number; inProgress: number; empty: number } {
    let done = 0, inProgress = 0, empty = 0;
    for (const parent of categories || []) {
      if ((parent.superGroup?.name || "Other") !== sgName) continue;
      for (const child of parent.children || []) {
        const s = childStatus(child);
        if (s === "done") done++;
        else if (s === "in_progress") inProgress++;
        else empty++;
      }
    }
    return { total: done + inProgress + empty, done, inProgress, empty };
  }

  // ============================================
  // Catalog Generation state
  // ============================================

  let generatingPainPointsFor = new SvelteSet<string>();
  let generatingIdeasFor = new SvelteSet<string>();
  let pendingIdeaChain = new SvelteSet<string>();
  let ppProgressMsgs = new SvelteMap<string, string>();
  let ideasProgressMsgs = new SvelteMap<string, string>();
  let ppJobIds = new Map<string, string>();       // categoryId → jobId
  let ideasJobIds = new Map<string, string>();     // categoryId → jobId
  let genToast = $state("");
  let genToastTimeout: ReturnType<typeof setTimeout> | null = null;

  // EventSource refs for cleanup (per category)
  let painPointEventSources = new Map<string, EventSource>();
  let ideasEventSources = new Map<string, EventSource>();

  // Cleanup on component destroy
  $effect(() => {
    return () => {
      for (const es of painPointEventSources.values()) es.close();
      for (const es of ideasEventSources.values()) es.close();
    };
  });

  // One-shot guard: NOT $state so it doesn't trigger reactivity.
  // After first meaningful run, the effect has no deps and becomes inert.
  let autoResumeAttempted = false;

  // Auto-resume active jobs on mount
  $effect(() => {
    if (autoResumeAttempted) return;
    if (!categories?.length) return;
    autoResumeAttempted = true;

    for (const parent of categories) {
      for (const child of parent.children ?? []) {
        for (const job of child.activeJobs ?? []) {
          if (job.jobMode === "catalog_pain_points"
              && !untrack(() => generatingPainPointsFor.has(child.id))) {
            generatingPainPointsFor.add(child.id);
            ppProgressMsgs.set(child.id, "Resuming...");
            expandedParents.add(parent.id);
            subscribeToPainPointJob(job.id, child.id);
          }
          if (job.jobMode === "catalog_ideas"
              && !untrack(() => generatingIdeasFor.has(child.id))) {
            generatingIdeasFor.add(child.id);
            ideasProgressMsgs.set(child.id, "Resuming...");
            expandedParents.add(parent.id);
            subscribeToIdeasJob(job.id, child.id);
          }
        }
      }
    }
  });

  // Idea generation modal state
  let showIdeaModal = $state(false);
  let ideaModalCategoryId = $state("");
  let ideaModalCategoryName = $state("");
  let ideaModalPainPoints = $state<any[]>([]);
  let ideaModalLoading = $state(false);
  let ideaModalSelected = new SvelteSet<string>();

  // ============================================
  // Category CRUD
  // ============================================

  async function createCategory() {
    saving = true;
    catErrorMsg = "";
    try {
      const body: Record<string, unknown> = {
        name: newName,
        sortOrder: newSortOrder,
      };
      if (newDescription) body.description = newDescription;
      if (newParentId) body.parentId = newParentId;

      const res = await fetch("/api/admin/catalog/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok) {
        catErrorMsg = result.error || "Failed to create category";
        return;
      }
      newName = "";
      newDescription = "";
      newParentId = "";
      newSortOrder = 0;
      showCreateForm = false;
      await invalidateAll();
    } finally {
      saving = false;
    }
  }

  function startEdit(cat: any) {
    editingId = cat.id;
    editName = cat.name;
    editDescription = cat.description || "";
    editParentId = cat.parentId || "";
    editSortOrder = cat.sortOrder;
  }

  async function saveEdit() {
    if (!editingId) return;
    saving = true;
    catErrorMsg = "";
    try {
      const body: Record<string, unknown> = {
        name: editName,
        sortOrder: editSortOrder,
        description: editDescription || null,
      };
      if (editParentId !== undefined) {
        body.parentId = editParentId || null;
      }

      const res = await fetch(`/api/admin/catalog/categories/${editingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok) {
        catErrorMsg = result.error || "Failed to update category";
        return;
      }
      editingId = null;
      await invalidateAll();
    } finally {
      saving = false;
    }
  }

  async function deleteCategory(id: string) {
    if (!confirm("Delete this category? This cannot be undone.")) return;
    deletingId = id;
    catErrorMsg = "";
    try {
      const res = await fetch(`/api/admin/catalog/categories/${id}`, {
        method: "DELETE",
      });
      const result = await res.json();
      if (!res.ok) {
        catErrorMsg = result.error || "Failed to delete category";
        return;
      }
      await invalidateAll();
    } finally {
      deletingId = null;
    }
  }

  // ============================================
  // Generation functions
  // ============================================

  function showToast(msg: string) {
    genToast = msg;
    if (genToastTimeout) clearTimeout(genToastTimeout);
    genToastTimeout = setTimeout(() => { genToast = ""; }, 5000);
  }

  function subscribeToPainPointJob(jobId: string, categoryId: string) {
    painPointEventSources.get(categoryId)?.close();
    const evtSource = new EventSource(`/api/jobs/${jobId}/events`);
    painPointEventSources.set(categoryId, evtSource);
    ppJobIds.set(categoryId, jobId);

    function cleanup() {
      evtSource.close();
      painPointEventSources.delete(categoryId);
      generatingPainPointsFor.delete(categoryId);
      ppProgressMsgs.delete(categoryId);
      ppJobIds.delete(categoryId);
    }

    evtSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status === "QUEUED" && data.aheadCount !== undefined) {
          ppProgressMsgs.set(categoryId, data.aheadCount > 0
            ? `Queue (${data.aheadCount} ahead)...`
            : "Starting soon...");
        }
        if (data.currentStageName && data.status === "RUNNING") {
          ppProgressMsgs.set(categoryId, `${data.currentStageName}...`);
        }
        if (data.status === "COMPLETED") {
          cleanup();
          if (pendingIdeaChain.has(categoryId)) {
            pendingIdeaChain.delete(categoryId);
            showToast("Pain points generated — now generating ideas...");
            autoGenerateIdeas(categoryId);
          } else {
            showToast("Pain points generated successfully!");
            invalidateAll();
          }
        }
        if (data.status === "FAILED") {
          cleanup();
          pendingIdeaChain.delete(categoryId);
          catErrorMsg = data.errorMessage || "Generation failed";
        }
        if (data.status === "CANCELLED") {
          cleanup();
          pendingIdeaChain.delete(categoryId);
          invalidateAll();
        }
      } catch { /* ignore parse errors */ }
    };

    evtSource.onerror = () => {
      cleanup();
      pendingIdeaChain.delete(categoryId);
      invalidateAll();
    };
  }

  function subscribeToIdeasJob(jobId: string, categoryId: string) {
    ideasEventSources.get(categoryId)?.close();
    const evtSource = new EventSource(`/api/jobs/${jobId}/events`);
    ideasEventSources.set(categoryId, evtSource);
    ideasJobIds.set(categoryId, jobId);

    function cleanup() {
      evtSource.close();
      ideasEventSources.delete(categoryId);
      generatingIdeasFor.delete(categoryId);
      ideasProgressMsgs.delete(categoryId);
      ideasJobIds.delete(categoryId);
    }

    evtSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status === "QUEUED" && data.aheadCount !== undefined) {
          ideasProgressMsgs.set(categoryId, data.aheadCount > 0
            ? `Queue (${data.aheadCount} ahead)...`
            : "Starting soon...");
        }
        if (data.currentStageName && data.status === "RUNNING") {
          ideasProgressMsgs.set(categoryId, `${data.currentStageName}...`);
        }
        if (data.status === "COMPLETED") {
          cleanup();
          showToast("Ideas generated successfully!");
          invalidateAll();
        }
        if (data.status === "FAILED") {
          cleanup();
          catErrorMsg = data.errorMessage || "Idea generation failed";
        }
        if (data.status === "CANCELLED") {
          cleanup();
          invalidateAll();
        }
      } catch { /* ignore parse errors */ }
    };

    evtSource.onerror = () => {
      cleanup();
      invalidateAll();
    };
  }

  async function generatePainPoints(categoryId: string) {
    generatingPainPointsFor.add(categoryId);
    ppProgressMsgs.set(categoryId, "Starting pain point generation...");
    catErrorMsg = "";

    try {
      const res = await fetch(`/api/admin/catalog/categories/${categoryId}/generate-pain-points`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json();
        // 409 = job already active → reconnect instead of showing error
        if (res.status === 409 && err.jobId) {
          ppProgressMsgs.set(categoryId, "Reconnecting...");
          ppJobIds.set(categoryId, err.jobId);
          subscribeToPainPointJob(err.jobId, categoryId);
          return;
        }
        catErrorMsg = err.error || "Failed to start generation";
        generatingPainPointsFor.delete(categoryId);
        ppProgressMsgs.delete(categoryId);
        return;
      }
      const { jobId } = await res.json();
      ppProgressMsgs.set(categoryId, "Analyzing niche...");
      subscribeToPainPointJob(jobId, categoryId);
      if (pendingIdeaChain.has(categoryId)) {
        ppProgressMsgs.set(categoryId, "Generating pain points (then ideas)...");
      }
    } catch {
      catErrorMsg = "Failed to start pain point generation";
      generatingPainPointsFor.delete(categoryId);
      ppProgressMsgs.delete(categoryId);
    }
  }

  async function openIdeaModal(categoryId: string, categoryName: string) {
    ideaModalCategoryId = categoryId;
    ideaModalCategoryName = categoryName;
    ideaModalLoading = true;
    ideaModalPainPoints = [];
    ideaModalSelected.clear();
    showIdeaModal = true;

    try {
      const res = await fetch(`/api/admin/catalog/categories/${categoryId}/pain-points`);
      if (!res.ok) {
        catErrorMsg = "Failed to fetch pain points";
        showIdeaModal = false;
        return;
      }
      const data = await res.json();
      ideaModalPainPoints = data.painPoints || [];
      for (const pp of ideaModalPainPoints) {
        ideaModalSelected.add(pp.id);
      }
    } catch {
      catErrorMsg = "Failed to fetch pain points";
      showIdeaModal = false;
    } finally {
      ideaModalLoading = false;
    }
  }

  function toggleIdeaPpSelection(id: string) {
    if (ideaModalSelected.has(id)) ideaModalSelected.delete(id);
    else ideaModalSelected.add(id);
  }

  function toggleAllIdeaPp() {
    if (ideaModalSelected.size === ideaModalPainPoints.length) {
      ideaModalSelected.clear();
    } else {
      ideaModalSelected.clear();
      for (const pp of ideaModalPainPoints) ideaModalSelected.add(pp.id);
    }
  }

  async function startIdeaGenerationJob(categoryId: string, painPointIds: string[]) {
    generatingIdeasFor.add(categoryId);
    ideasProgressMsgs.set(categoryId, "Starting idea generation...");
    catErrorMsg = "";

    try {
      const res = await fetch(`/api/admin/catalog/categories/${categoryId}/generate-ideas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ painPointIds }),
      });
      if (!res.ok) {
        const err = await res.json();
        if (res.status === 409 && err.jobId) {
          ideasProgressMsgs.set(categoryId, "Reconnecting...");
          ideasJobIds.set(categoryId, err.jobId);
          subscribeToIdeasJob(err.jobId, categoryId);
          return;
        }
        catErrorMsg = err.error || "Failed to start idea generation";
        generatingIdeasFor.delete(categoryId);
        ideasProgressMsgs.delete(categoryId);
        return;
      }
      const { jobId } = await res.json();
      ideasProgressMsgs.set(categoryId, "Generating solution ideas...");
      subscribeToIdeasJob(jobId, categoryId);
    } catch {
      catErrorMsg = "Failed to start idea generation";
      generatingIdeasFor.delete(categoryId);
      ideasProgressMsgs.delete(categoryId);
    }
  }

  async function generateIdeas() {
    if (ideaModalSelected.size === 0) return;
    const catId = ideaModalCategoryId;
    showIdeaModal = false;
    await startIdeaGenerationJob(catId, [...ideaModalSelected]);
  }

  async function autoGenerateIdeas(categoryId: string) {
    ideasProgressMsgs.set(categoryId, "Fetching pain points...");
    try {
      const ppRes = await fetch(`/api/admin/catalog/categories/${categoryId}/pain-points`);
      if (!ppRes.ok) {
        catErrorMsg = "Failed to fetch pain points for idea generation";
        ideasProgressMsgs.delete(categoryId);
        return;
      }
      const ppData = await ppRes.json();
      const painPoints = ppData.painPoints || [];
      if (painPoints.length === 0) {
        catErrorMsg = "No pain points were generated — cannot generate ideas";
        ideasProgressMsgs.delete(categoryId);
        return;
      }
      await startIdeaGenerationJob(categoryId, painPoints.map((pp: any) => pp.id));
    } catch {
      catErrorMsg = "Failed to start idea generation";
      ideasProgressMsgs.delete(categoryId);
    }
  }

  async function cancelPainPointJob(categoryId: string) {
    const jobId = ppJobIds.get(categoryId);
    if (!jobId) return;
    try {
      await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
    } catch { /* best-effort */ }
    painPointEventSources.get(categoryId)?.close();
    painPointEventSources.delete(categoryId);
    generatingPainPointsFor.delete(categoryId);
    pendingIdeaChain.delete(categoryId);
    ppProgressMsgs.delete(categoryId);
    ppJobIds.delete(categoryId);
    invalidateAll();
  }

  async function cancelIdeasJob(categoryId: string) {
    const jobId = ideasJobIds.get(categoryId);
    if (!jobId) return;
    try {
      await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
    } catch { /* best-effort */ }
    ideasEventSources.get(categoryId)?.close();
    ideasEventSources.delete(categoryId);
    generatingIdeasFor.delete(categoryId);
    ideasProgressMsgs.delete(categoryId);
    ideasJobIds.delete(categoryId);
    invalidateAll();
  }
</script>

<div>
  <div class="flex items-center justify-between mb-6">
    <div>
      <p class="text-sm text-text-muted">
        Manage the category hierarchy for ideas and pain points.
      </p>
    </div>
    <button class="btn-primary flex items-center gap-2" onclick={() => (showCreateForm = !showCreateForm)}>
      <Plus class="w-4 h-4" />
      Add Category
    </button>
  </div>

  {#if catErrorMsg}
    <div class="mb-4 px-4 py-2 bg-error/10 border border-error/30 rounded-lg text-sm text-error">
      {catErrorMsg}
    </div>
  {/if}

  <!-- Create Form -->
  {#if showCreateForm}
    <div class="bg-bg-surface border border-border rounded-xl p-4 mb-6">
      <h3 class="text-sm font-semibold text-text-primary mb-3">New Category</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-text-muted mb-1" for="new-name">Name</label>
          <input
            id="new-name"
            type="text"
            bind:value={newName}
            class="w-full px-3 py-2 bg-bg-base border border-border rounded-lg text-sm text-text-primary"
            placeholder="e.g. Marketing"
          />
        </div>
        <div>
          <label class="block text-xs text-text-muted mb-1" for="new-parent">Parent (optional)</label>
          <select
            id="new-parent"
            bind:value={newParentId}
            class="w-full px-3 py-2 bg-bg-base border border-border rounded-lg text-sm text-text-primary"
          >
            <option value="">None (top-level)</option>
            {#each topLevelCategories as cat}
              <option value={cat.id}>{cat.name}</option>
            {/each}
          </select>
        </div>
        <div>
          <label class="block text-xs text-text-muted mb-1" for="new-desc">Description</label>
          <input
            id="new-desc"
            type="text"
            bind:value={newDescription}
            class="w-full px-3 py-2 bg-bg-base border border-border rounded-lg text-sm text-text-primary"
            placeholder="Optional"
          />
        </div>
        <div>
          <label class="block text-xs text-text-muted mb-1" for="new-sort">Sort Order</label>
          <input
            id="new-sort"
            type="number"
            bind:value={newSortOrder}
            class="w-full px-3 py-2 bg-bg-base border border-border rounded-lg text-sm text-text-primary"
            min="0"
            max="1000"
          />
        </div>
      </div>
      <div class="flex gap-2 mt-3">
        <button class="btn-primary text-sm" onclick={createCategory} disabled={saving || !newName}>
          {saving ? "Creating..." : "Create"}
        </button>
        <button
          class="text-sm px-3 py-1.5 text-text-secondary hover:text-text-primary"
          onclick={() => (showCreateForm = false)}
        >
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Search + Filter Toolbar -->
  {#if categories && categories.length > 0}
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <!-- Search input -->
      <div class="relative flex-1 min-w-[200px] max-w-xs">
        <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search categories..."
          class="w-full pl-8 pr-8 py-1.5 bg-bg-base border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted"
        />
        {#if searchQuery}
          <button
            class="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-bg-elevated text-text-muted"
            onclick={() => (searchQuery = "")}
          >
            <X class="w-3.5 h-3.5" />
          </button>
        {/if}
      </div>

      <!-- Status filter chips -->
      <div class="flex items-center gap-1.5">
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-colors {statusFilter === 'all'
            ? 'bg-text-primary text-bg-base border-text-primary'
            : 'bg-bg-base border-border text-text-secondary hover:border-border-hover'}"
          onclick={() => (statusFilter = statusFilter === "all" ? "all" : "all")}
        >
          All {globalStats.total}
        </button>
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-colors {statusFilter === 'empty'
            ? 'bg-text-muted text-bg-base border-text-muted'
            : 'bg-bg-base border-border text-text-muted hover:border-border-hover'}"
          onclick={() => (statusFilter = statusFilter === "empty" ? "all" : "empty")}
        >
          Empty {globalStats.empty}
        </button>
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-colors {statusFilter === 'in_progress'
            ? 'bg-warning text-bg-base border-warning'
            : 'bg-bg-base border-border text-text-secondary hover:border-border-hover'}"
          onclick={() => (statusFilter = statusFilter === "in_progress" ? "all" : "in_progress")}
        >
          In Progress {globalStats.inProgress}
        </button>
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-colors {statusFilter === 'done'
            ? 'bg-success text-bg-base border-success'
            : 'bg-bg-base border-border text-text-secondary hover:border-border-hover'}"
          onclick={() => (statusFilter = statusFilter === "done" ? "all" : "done")}
        >
          Done {globalStats.done}
        </button>
      </div>
    </div>

    {#if isFiltering}
      <p class="text-xs text-text-muted mb-3">
        Showing {filteredChildCount} of {globalStats.total} subcategories
      </p>
    {/if}
  {/if}

  <!-- Category Tree -->
  <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
    {#if !categories || categories.length === 0}
      <div class="p-8 text-center text-text-muted">
        <FolderOpen class="w-8 h-8 mx-auto mb-2 opacity-50" />
        No categories yet. Create your first category above.
      </div>
    {:else if filteredGroups.length === 0}
      <div class="p-8 text-center text-text-muted">
        <Search class="w-6 h-6 mx-auto mb-2 opacity-50" />
        <p class="text-sm">No categories match your filters.</p>
        <button
          class="mt-2 text-xs text-accent hover:underline"
          onclick={() => { searchQuery = ""; statusFilter = "all"; }}
        >
          Clear filters
        </button>
      </div>
    {:else}
      {#each filteredGroups as sg (sg.name)}
        {@const sgStats = superGroupStats(sg.name)}
        {@const sgExpanded = isSuperGroupExpanded(sg.name, sg._hasFilterMatch)}

        <div class="border-b border-border/30 last:border-b-0">
          <!-- Super-group header -->
          <button
            class="flex w-full items-center gap-2 px-4 py-2.5 hover:bg-bg-elevated/50 transition-colors"
            onclick={() => toggleSuperGroup(sg.name)}
          >
            <span class="transition-transform duration-150 {sgExpanded ? 'rotate-90' : ''}">
              <ChevronRight class="w-3.5 h-3.5 text-text-muted" />
            </span>
            <span class="text-xs font-semibold uppercase tracking-wider text-text-muted">{sg.name}</span>

            <!-- Aggregate progress bar -->
            {#if sgStats.total > 0}
              <span class="flex items-center gap-2 ml-auto">
                <span class="w-16 h-1 bg-border flex overflow-hidden">
                  {#if sgStats.done > 0}
                    <span class="bg-success h-full" style="width: {(sgStats.done / sgStats.total) * 100}%"></span>
                  {/if}
                  {#if sgStats.inProgress > 0}
                    <span class="bg-warning h-full" style="width: {(sgStats.inProgress / sgStats.total) * 100}%"></span>
                  {/if}
                </span>
                <span class="text-[10px] text-text-muted">{sgStats.done}/{sgStats.total}</span>
              </span>
            {/if}
          </button>

          {#if sgExpanded}
            <div class="divide-y divide-border/30">
              {#each sg.parents as parent}
                {@const stats = parentStats(parent)}
                {@const expanded = isParentExpanded(parent.id, parent._hasFilterMatch)}
                <!-- Parent -->
                <div class="ml-4 px-4 py-3">
                  {#if editingId === parent.id}
                    <div class="grid grid-cols-1 sm:grid-cols-4 gap-2">
                      <input
                        type="text"
                        bind:value={editName}
                        class="px-2 py-1.5 bg-bg-base border border-border rounded text-sm"
                      />
                      <input
                        type="text"
                        bind:value={editDescription}
                        class="px-2 py-1.5 bg-bg-base border border-border rounded text-sm"
                        placeholder="Description"
                      />
                      <input
                        type="number"
                        bind:value={editSortOrder}
                        class="px-2 py-1.5 bg-bg-base border border-border rounded text-sm"
                        min="0"
                        max="1000"
                      />
                      <div class="flex gap-1">
                        <button class="btn-primary text-xs px-3" onclick={saveEdit} disabled={saving}>Save</button>
                        <button class="text-xs px-2 text-text-muted" onclick={() => (editingId = null)}>Cancel</button>
                      </div>
                    </div>
                  {:else}
                    <div class="flex items-center justify-between">
                      <button
                        class="flex flex-col flex-1 min-w-0 text-left"
                        onclick={() => toggleParent(parent.id)}
                      >
                        <span class="flex items-center gap-2 w-full">
                          <span class="transition-transform duration-150 {expanded ? 'rotate-90' : ''}">
                            <ChevronRight class="w-3.5 h-3.5 text-text-muted" />
                          </span>
                          <span class="text-sm font-medium text-text-primary">{parent.name}</span>
                          <Badge variant={parent.isActive ? "success" : "default"} size="sm">
                            {parent.isActive ? "Active" : "Inactive"}
                          </Badge>

                          <!-- Mini progress bar + summary -->
                          {#if stats.total > 0}
                            <span class="flex items-center gap-2 ml-auto mr-2 flex-shrink-0">
                              <span class="w-20 h-1 bg-border flex overflow-hidden">
                                {#if stats.done > 0}
                                  <span class="bg-success h-full" style="width: {(stats.done / stats.total) * 100}%"></span>
                                {/if}
                                {#if stats.inProgress > 0}
                                  <span class="bg-warning h-full" style="width: {(stats.inProgress / stats.total) * 100}%"></span>
                                {/if}
                              </span>
                              <span class="text-xs {stats.done === stats.total ? 'text-success' : stats.done > 0 ? 'text-text-secondary' : 'text-text-muted'}">
                                {stats.done}/{stats.total} done
                              </span>
                            </span>
                          {/if}
                        </span>
                        {#if parent.description}
                          <span class="text-xs text-text-muted truncate pl-[22px]">{parent.description}</span>
                        {/if}
                      </button>
                      <div class="flex items-center gap-1 flex-shrink-0">
                        <a
                          class="p-1.5 rounded hover:bg-bg-elevated transition-colors {parent.longDescription ? 'text-success' : 'text-text-muted hover:text-accent'}"
                          href="/admin/catalog/{parent.id}/seo"
                          title={parent.longDescription ? 'SEO copy curated' : 'Edit SEO copy'}
                        >
                          <FileText class="w-3.5 h-3.5" />
                        </a>
                        <button
                          class="p-1.5 rounded hover:bg-bg-elevated text-text-muted hover:text-text-primary"
                          onclick={() => startEdit(parent)}
                          title="Edit"
                        >
                          <Pencil class="w-3.5 h-3.5" />
                        </button>
                        <button
                          class="p-1.5 rounded hover:bg-error/10 text-text-muted hover:text-error"
                          onclick={() => deleteCategory(parent.id)}
                          disabled={deletingId === parent.id}
                          title="Delete"
                        >
                          <Trash2 class="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  {/if}

                  <!-- Children (collapsible) -->
                  {#if expanded && parent.children && parent.children.length > 0}
                    <div class="ml-6 mt-2 space-y-1">
                      {#each parent.children as child}
                        {@const status = childStatus(child)}
                        {#if editingId === child.id}
                          <div class="grid grid-cols-1 sm:grid-cols-4 gap-2 pl-4 border-l-2 border-border">
                            <input
                              type="text"
                              bind:value={editName}
                              class="px-2 py-1.5 bg-bg-base border border-border rounded text-sm"
                            />
                            <input
                              type="text"
                              bind:value={editDescription}
                              class="px-2 py-1.5 bg-bg-base border border-border rounded text-sm"
                              placeholder="Description"
                            />
                            <input
                              type="number"
                              bind:value={editSortOrder}
                              class="px-2 py-1.5 bg-bg-base border border-border rounded text-sm"
                              min="0"
                              max="1000"
                            />
                            <div class="flex gap-1">
                              <button class="btn-primary text-xs px-3" onclick={saveEdit} disabled={saving}>Save</button>
                              <button class="text-xs px-2 text-text-muted" onclick={() => (editingId = null)}>Cancel</button>
                            </div>
                          </div>
                        {:else}
                          <div class="flex items-center justify-between pl-4 border-l-2 {status === 'done' ? 'border-success/50' : status === 'in_progress' ? 'border-warning/50' : 'border-border/50'} py-1">
                            <div class="flex items-center gap-2">
                              <ChevronRight class="w-3 h-3 text-text-muted" />
                              <span class="text-sm text-text-secondary">{child.name}</span>
                              {#if child.description}
                                <span class="text-xs text-text-muted">— {child.description}</span>
                              {/if}
                              <!-- Status indicators -->
                              {#if child._count}
                                {@const pp = child._count.painPoints ?? 0}
                                {@const ideas = child._count.ideas ?? 0}
                                {#if pp === 0 && ideas === 0}
                                  <span class="text-xs text-text-muted italic">empty</span>
                                {:else}
                                  <button
                                    class="flex items-center gap-1 hover:bg-bg-elevated/50 rounded px-1 -mx-1 transition-colors cursor-pointer"
                                    title="View & manage items"
                                    onclick={(e) => { e.stopPropagation(); openItemsModal(child.id, parent.name, child.name); }}
                                  >
                                    {#if pp > 0}
                                      <Badge variant="default" size="sm">{pp} pp</Badge>
                                    {:else}
                                      <span class="text-xs text-text-muted">0 pp</span>
                                    {/if}
                                    {#if ideas > 0}
                                      <Badge variant="success" size="sm">{ideas} ideas</Badge>
                                    {:else}
                                      <span class="text-xs text-text-muted">&middot; 0 ideas</span>
                                    {/if}
                                    <Eye class="w-3 h-3 text-text-muted" />
                                  </button>
                                {/if}
                              {/if}
                            </div>
                            <div class="flex items-center gap-1">
                              {#if generatingPainPointsFor.has(child.id)}
                                <span class="text-xs text-accent flex items-center gap-1">
                                  <Loader2 class="w-3 h-3 animate-spin" />
                                  {ppProgressMsgs.get(child.id) ?? ""}
                                  <button
                                    onclick={() => cancelPainPointJob(child.id)}
                                    class="p-0.5 rounded hover:bg-error/10 text-text-muted hover:text-error"
                                    title="Cancel generation"
                                  >
                                    <X class="w-3 h-3" />
                                  </button>
                                </span>
                              {:else}
                                <button
                                  class="p-1 rounded hover:bg-accent/10 text-text-muted hover:text-accent"
                                  onclick={() => generatePainPoints(child.id)}
                                  title="Generate Pain Points"
                                >
                                  <Sparkles class="w-3 h-3" />
                                </button>
                              {/if}
                              {#if generatingIdeasFor.has(child.id)}
                                <span class="text-xs text-accent flex items-center gap-1">
                                  <Loader2 class="w-3 h-3 animate-spin" />
                                  {ideasProgressMsgs.get(child.id) ?? ""}
                                  <button
                                    onclick={() => cancelIdeasJob(child.id)}
                                    class="p-0.5 rounded hover:bg-error/10 text-text-muted hover:text-error"
                                    title="Cancel generation"
                                  >
                                    <X class="w-3 h-3" />
                                  </button>
                                </span>
                              {:else}
                                <button
                                  class="p-1 rounded text-text-muted
                                    {(child._count?.painPoints ?? 0) === 0
                                      ? 'opacity-60 hover:opacity-100 hover:bg-accent/10 hover:text-accent'
                                      : 'hover:bg-accent/10 hover:text-accent'}"
                                  onclick={() => {
                                    if ((child._count?.painPoints ?? 0) === 0) {
                                      pendingIdeaChain.add(child.id);
                                      generatePainPoints(child.id);
                                    } else {
                                      openIdeaModal(child.id, `${parent.name} > ${child.name}`);
                                    }
                                  }}
                                  disabled={generatingPainPointsFor.has(child.id) || generatingIdeasFor.has(child.id)}
                                  title={(child._count?.painPoints ?? 0) === 0
                                    ? 'Generate Pain Points + Ideas'
                                    : 'Generate Ideas from Pain Points'}
                                >
                                  <Lightbulb class="w-3 h-3" />
                                </button>
                              {/if}
                              <a
                                class="p-1 rounded hover:bg-bg-elevated transition-colors {child.longDescription ? 'text-success' : 'text-text-muted hover:text-accent'}"
                                href="/admin/catalog/{child.id}/seo"
                                title={child.longDescription ? 'SEO copy curated' : 'Edit SEO copy'}
                              >
                                <FileText class="w-3 h-3" />
                              </a>
                              <button
                                class="p-1 rounded hover:bg-bg-elevated text-text-muted hover:text-text-primary"
                                onclick={() => startEdit(child)}
                                title="Edit"
                              >
                                <Pencil class="w-3 h-3" />
                              </button>
                              <button
                                class="p-1 rounded hover:bg-error/10 text-text-muted hover:text-error"
                                onclick={() => deleteCategory(child.id)}
                                disabled={deletingId === child.id}
                                title="Delete"
                              >
                                <Trash2 class="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        {/if}
                      {/each}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</div>

<!-- Idea Generation Modal -->
{#if showIdeaModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <div
      class="fixed inset-0 bg-black/40"
      onclick={() => (showIdeaModal = false)}
      role="button"
      tabindex="-1"
      onkeydown={(e) => { if (e.key === "Escape") showIdeaModal = false; }}
    ></div>
    <div class="relative bg-bg-surface border border-border rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col z-50">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-border">
        <div>
          <h3 class="text-lg font-semibold text-text-primary">Generate Ideas</h3>
          <p class="text-sm text-text-muted">{ideaModalCategoryName}</p>
        </div>
        <button class="p-1 rounded hover:bg-bg-elevated" onclick={() => (showIdeaModal = false)}>
          <X class="w-5 h-5 text-text-muted" />
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6">
        {#if ideaModalLoading}
          <div class="flex items-center justify-center py-8">
            <Loader2 class="w-6 h-6 animate-spin text-accent" />
            <span class="ml-2 text-text-muted">Loading pain points...</span>
          </div>
        {:else if ideaModalPainPoints.length === 0}
          <p class="text-text-muted text-center py-8">
            No pain points found for this category. Generate pain points first.
          </p>
        {:else}
          <div class="mb-3 flex items-center justify-between">
            <span class="text-sm text-text-secondary">
              Select pain points to generate ideas from ({ideaModalSelected.size}/{ideaModalPainPoints.length})
            </span>
            <button
              class="text-xs text-accent hover:underline"
              onclick={toggleAllIdeaPp}
            >
              {ideaModalSelected.size === ideaModalPainPoints.length ? "Deselect All" : "Select All"}
            </button>
          </div>
          <div class="space-y-2">
            {#each ideaModalPainPoints as pp}
              <button
                class="w-full text-left p-3 rounded-lg border transition-colors {ideaModalSelected.has(pp.id) ? 'border-accent/50 bg-accent/5' : 'border-border hover:border-border-hover'}"
                onclick={() => toggleIdeaPpSelection(pp.id)}
              >
                <div class="flex items-start gap-3">
                  <div class="mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 {ideaModalSelected.has(pp.id) ? 'bg-accent border-accent' : 'border-border'}">
                    {#if ideaModalSelected.has(pp.id)}
                      <Check class="w-3 h-3 text-white" />
                    {/if}
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="text-sm font-medium text-text-primary">{pp.title}</span>
                      <Badge variant={pp.severityScore >= 0.7 ? 'error' : pp.severityScore >= 0.4 ? 'warning' : 'default'} size="sm">
                        Sev {(pp.severityScore * 100).toFixed(0)}%
                      </Badge>
                      <Badge variant={pp.willingnessToPayScore >= 0.6 ? 'success' : 'default'} size="sm">
                        WTP {(pp.willingnessToPayScore * 100).toFixed(0)}%
                      </Badge>
                      <span class="text-xs text-text-muted">{pp.mentionCount} {pp.mentionCount === 1 ? 'mention' : 'mentions'}</span>
                    </div>
                    <p class="text-xs text-text-muted line-clamp-2">{pp.description}</p>
                  </div>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between px-6 py-4 border-t border-border">
        <button class="text-sm text-text-secondary hover:text-text-primary" onclick={() => (showIdeaModal = false)}>
          Cancel
        </button>
        <button
          class="btn-primary flex items-center gap-2"
          onclick={generateIdeas}
          disabled={ideaModalSelected.size === 0 || generatingIdeasFor.has(ideaModalCategoryId)}
        >
          <Lightbulb class="w-4 h-4" />
          Generate Ideas ({ideaModalSelected.size} pain points)
        </button>
      </div>
    </div>
  </div>
{/if}

<CategoryItemsModal
  bind:open={itemsModalOpen}
  categoryId={itemsModalCategoryId}
  categoryName={itemsModalCategoryName}
  allCategories={allChildCategories}
  onMutated={() => invalidateAll()}
/>

<!-- Generation toast notification -->
{#if genToast}
  <div class="fixed bottom-6 right-6 z-50 bg-success/90 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
    <Check class="w-4 h-4" />
    <span class="text-sm">{genToast}</span>
  </div>
{/if}
