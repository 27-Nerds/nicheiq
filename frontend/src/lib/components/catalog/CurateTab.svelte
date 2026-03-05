<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import Badge from "$lib/components/ui/Badge.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import {
    Pencil,
    Loader2,
    Sparkles,
    X,
    Check,
  } from "lucide-svelte";

  let { data, categories }: {
    data: any;
    categories: any[];
  } = $props();

  // ============================================
  // State
  // ============================================

  let selectedIds = new SvelteSet<string>();
  let categorizing = $state(false);
  let publishing = $state(false);
  let errorMsg = $state("");
  let successMsg = $state("");

  // Per-row category assignments (for manual publish)
  let rowCategories = $state<Record<string, string>>({});
  let rowPublishing = $state<Record<string, boolean>>({});

  // Bulk action bar
  let bulkCategoryId = $state("");

  // Categorization modal state
  let showModal = $state(false);
  let categorizeResult = $state<any>(null);
  let categoryAssignments = $state<Record<string, string>>({});
  let acceptedNewCategories = new SvelteSet<number>();

  // "Categorize All Uncategorized" state
  let categorizingAll = $state(false);
  let categorizeProgress = $state({ current: 0, total: 0 });
  let allFetchedItems = $state<any[]>([]);
  let abortController = $state<AbortController | null>(null);
  let publishProgress = $state({ current: 0, total: 0 });

  // Depublish state
  let depublishing = $state<Record<string, boolean>>({});
  let changingCategory = $state<Record<string, boolean>>({});
  let changingCategorySaving = $state<Record<string, boolean>>({});
  let changingCategoryValue = $state<Record<string, string>>({});
  let confirmDepublish = $state<{ id: string; name: string; type: string } | null>(null);

  const currentType = $derived(data.filters?.type || "ideas");
  const items = $derived(data.itemsData?.items || []);

  const allCategories = $derived.by(() => {
    const flat: Array<{ id: string; name: string; parentName?: string }> = [];
    for (const parent of categories || []) {
      flat.push({ id: parent.id, name: parent.name });
      for (const child of parent.children || []) {
        flat.push({ id: child.id, name: child.name, parentName: parent.name });
      }
    }
    return flat;
  });

  const unpublishedSelectedCount = $derived(
    items.filter(
      (i: any) => selectedIds.has(i.id) && !i.isPublished,
    ).length,
  );

  const publishedSelectedCount = $derived(
    items.filter(
      (i: any) => selectedIds.has(i.id) && i.isPublished && i.publishedRecordId,
    ).length,
  );

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  function formatScore(val: number | undefined | null): string {
    if (val == null) return "\u2014";
    return (val * 100).toFixed(0) + "%";
  }

  function toggleSelection(id: string) {
    if (selectedIds.has(id)) selectedIds.delete(id);
    else selectedIds.add(id);
  }

  function toggleSelectAll() {
    if (selectedIds.size === items.length && items.length > 0) {
      selectedIds.clear();
    } else {
      selectedIds.clear();
      for (const i of items) selectedIds.add(i.id);
    }
  }

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(page.url.searchParams);
    params.set("tab", "curate");
    if (value) params.set(key, value);
    else params.delete(key);
    params.set("page", "1");
    goto(`?${params}`, { replaceState: true, invalidateAll: true });
  }

  function getCategoryName(categoryId: string): string {
    for (const parent of categories || []) {
      if (parent.id === categoryId) return parent.name;
      for (const child of parent.children || []) {
        if (child.id === categoryId) {
          return `${parent.name} > ${child.name}`;
        }
      }
    }
    return "Unknown";
  }

  // ============================================
  // Per-row manual publish
  // ============================================

  async function publishSingle(item: any) {
    const categoryId = rowCategories[item.id];
    if (!categoryId) return;

    rowPublishing = { ...rowPublishing, [item.id]: true };
    errorMsg = "";
    successMsg = "";
    try {
      const endpoint =
        currentType === "ideas"
          ? "/api/admin/catalog/ideas"
          : "/api/admin/catalog/pain-points";

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          categoryId,
          sourceJobId: item.jobId,
          itemIndex: item.itemIndex,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        errorMsg = err.error || "Failed to publish item";
        return;
      }
      const next = { ...rowCategories };
      delete next[item.id];
      rowCategories = next;
      await invalidateAll();
    } catch {
      errorMsg = "Failed to publish item";
    } finally {
      rowPublishing = { ...rowPublishing, [item.id]: false };
    }
  }

  // ============================================
  // Bulk manual publish
  // ============================================

  async function publishSelected() {
    if (!bulkCategoryId) return;

    const unpublishedSelected = items.filter(
      (i: any) => selectedIds.has(i.id) && !i.isPublished,
    );
    if (unpublishedSelected.length === 0) return;

    publishing = true;
    errorMsg = "";
    successMsg = "";
    let published = 0;
    let failed = 0;

    const endpoint =
      currentType === "ideas"
        ? "/api/admin/catalog/ideas"
        : "/api/admin/catalog/pain-points";

    for (const item of unpublishedSelected) {
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            categoryId: bulkCategoryId,
            sourceJobId: item.jobId,
            itemIndex: item.itemIndex,
          }),
        });
        if (res.ok) published++;
        else failed++;
      } catch {
        failed++;
      }
    }

    publishing = false;
    selectedIds.clear();
    bulkCategoryId = "";

    if (failed > 0) {
      errorMsg = `Published ${published}, failed ${failed}`;
    } else if (published > 0) {
      successMsg = `Successfully published ${published} item${published > 1 ? "s" : ""}`;
    }

    await invalidateAll();
  }

  // ============================================
  // Depublish
  // ============================================

  async function depublishSingle(item: any) {
    if (!item.publishedRecordId) return;

    depublishing = { ...depublishing, [item.id]: true };
    errorMsg = "";
    successMsg = "";
    try {
      const endpoint =
        currentType === "ideas"
          ? `/api/admin/catalog/ideas/${item.publishedRecordId}`
          : `/api/admin/catalog/pain-points/${item.publishedRecordId}`;

      const res = await fetch(endpoint, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        errorMsg = err.error || "Failed to depublish item";
        return;
      }
      confirmDepublish = null;
      await invalidateAll();
    } catch {
      errorMsg = "Failed to depublish item";
    } finally {
      depublishing = { ...depublishing, [item.id]: false };
    }
  }

  async function depublishSelected() {
    const publishedSelected = items.filter(
      (i: any) => selectedIds.has(i.id) && i.isPublished && i.publishedRecordId,
    );
    if (publishedSelected.length === 0) return;
    if (!confirm(`Depublish ${publishedSelected.length} item(s)? They will return to Draft state.`)) return;

    publishing = true;
    errorMsg = "";
    successMsg = "";
    let depublished = 0;
    let failed = 0;

    for (const item of publishedSelected) {
      try {
        const endpoint =
          currentType === "ideas"
            ? `/api/admin/catalog/ideas/${item.publishedRecordId}`
            : `/api/admin/catalog/pain-points/${item.publishedRecordId}`;

        const res = await fetch(endpoint, { method: "DELETE" });
        if (res.ok) depublished++;
        else failed++;
      } catch {
        failed++;
      }
    }

    publishing = false;
    selectedIds.clear();

    if (failed > 0) {
      errorMsg = `Depublished ${depublished}, failed ${failed}`;
    } else if (depublished > 0) {
      successMsg = `Successfully depublished ${depublished} item${depublished > 1 ? "s" : ""}`;
    }

    await invalidateAll();
  }

  // ============================================
  // Change category (inline edit)
  // ============================================

  function startChangeCategory(item: any) {
    changingCategory = { ...changingCategory, [item.id]: true };
    changingCategoryValue = { ...changingCategoryValue, [item.id]: item.categoryId || "" };
  }

  function cancelChangeCategory(itemId: string) {
    changingCategory = { ...changingCategory, [itemId]: false };
  }

  async function saveChangeCategory(item: any) {
    const newCategoryId = changingCategoryValue[item.id];
    if (!newCategoryId || !item.publishedRecordId) return;

    changingCategorySaving = { ...changingCategorySaving, [item.id]: true };
    errorMsg = "";
    try {
      const endpoint =
        currentType === "ideas"
          ? `/api/admin/catalog/ideas/${item.publishedRecordId}`
          : `/api/admin/catalog/pain-points/${item.publishedRecordId}`;

      const res = await fetch(endpoint, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ categoryId: newCategoryId }),
      });
      if (!res.ok) {
        const err = await res.json();
        errorMsg = err.error || "Failed to change category";
        return;
      }
      changingCategory = { ...changingCategory, [item.id]: false };
      await invalidateAll();
    } catch {
      errorMsg = "Failed to change category";
    } finally {
      changingCategorySaving = { ...changingCategorySaving, [item.id]: false };
    }
  }

  // ============================================
  // AI Auto-categorize
  // ============================================

  async function autoCategorize() {
    const selected = items.filter((i: any) => selectedIds.has(i.id));
    if (selected.length === 0) return;

    categorizing = true;
    errorMsg = "";
    successMsg = "";
    try {
      const res = await fetch("/api/admin/catalog/categorize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          itemType: currentType === "ideas" ? "idea" : "painPoint",
          items: selected.map((i: any) => ({
            id: i.id,
            name: i.itemName,
            description: i.itemDescription.slice(0, 500),
            niche: i.niche,
          })),
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        errorMsg = err.error || "Categorization failed";
        return;
      }

      categorizeResult = await res.json();
      categoryAssignments = {};
      for (const sug of categorizeResult.suggestions || []) {
        if (sug.suggestedCategoryId) {
          categoryAssignments[sug.itemId] = sug.suggestedCategoryId;
        }
      }
      acceptedNewCategories.clear();
      showModal = true;
    } catch {
      errorMsg = "Categorization request failed";
    } finally {
      categorizing = false;
    }
  }

  // ============================================
  // Categorize All Uncategorized
  // ============================================

  async function categorizeAllUncategorized() {
    categorizingAll = true;
    errorMsg = "";
    successMsg = "";
    allFetchedItems = [];
    const controller = new AbortController();
    abortController = controller;

    try {
      let fetchPage = 1;
      let totalPages = 1;
      const fetched: any[] = [];

      while (fetchPage <= totalPages) {
        if (controller.signal.aborted) break;
        const params = new URLSearchParams({
          type: currentType,
          isPublished: "false",
          limit: "100",
          page: String(fetchPage),
        });
        const res = await fetch(`/api/admin/catalog/items?${params}`);
        if (!res.ok) break;
        const result = await res.json();
        const uncategorized = (result.items || []).filter((i: any) => !i.categoryId);
        fetched.push(...uncategorized);
        totalPages = result.totalPages || 1;
        fetchPage++;
      }

      if (fetched.length === 0) {
        successMsg = "No uncategorized items found";
        return;
      }

      allFetchedItems = fetched;

      const chunkSize = 50;
      const chunks: any[][] = [];
      for (let i = 0; i < fetched.length; i += chunkSize) {
        chunks.push(fetched.slice(i, i + chunkSize));
      }

      categorizeProgress = { current: 0, total: chunks.length };
      const allSuggestions: any[] = [];
      const allProposedNew: any[] = [];
      let warning: string | undefined;

      for (let i = 0; i < chunks.length; i++) {
        if (controller.signal.aborted) {
          warning = `Cancelled after ${i} of ${chunks.length} batches`;
          break;
        }

        categorizeProgress = { current: i + 1, total: chunks.length };
        const chunk = chunks[i];

        try {
          const res = await fetch("/api/admin/catalog/categorize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              itemType: currentType === "ideas" ? "idea" : "painPoint",
              items: chunk.map((item: any) => ({
                id: item.id,
                name: item.itemName,
                description: (item.itemDescription || "").slice(0, 500),
                niche: item.niche,
              })),
            }),
            signal: controller.signal,
          });

          if (res.status === 429) {
            const err = await res.json();
            warning = `Rate limit reached after batch ${i + 1}. ${err.error || ""}`;
            break;
          }

          if (!res.ok) {
            warning = `Batch ${i + 1} failed (HTTP ${res.status})`;
            continue;
          }

          const result = await res.json();
          allSuggestions.push(...(result.suggestions || []));

          for (const p of result.proposedNewCategories || []) {
            if (!allProposedNew.some((e: any) => e.name === p.name && e.parentName === p.parentName)) {
              allProposedNew.push(p);
            }
          }
          if (result.warning) warning = result.warning;
        } catch (err) {
          if (err instanceof DOMException && err.name === "AbortError") {
            warning = `Cancelled after ${i} of ${chunks.length} batches`;
            break;
          }
          warning = `Batch ${i + 1} failed`;
          continue;
        }
      }

      if (allSuggestions.length > 0) {
        categorizeResult = {
          suggestions: allSuggestions,
          proposedNewCategories: allProposedNew,
          warning,
        };
        categoryAssignments = {};
        for (const sug of allSuggestions) {
          if (sug.suggestedCategoryId) {
            categoryAssignments[sug.itemId] = sug.suggestedCategoryId;
          }
        }
        acceptedNewCategories.clear();
        showModal = true;
      } else {
        errorMsg = warning || "No items were categorized";
      }
    } catch {
      errorMsg = "Failed to categorize uncategorized items";
    } finally {
      categorizingAll = false;
      abortController = null;
    }
  }

  function cancelCategorizeAll() {
    abortController?.abort();
  }

  async function acceptNewCategory(index: number, proposed: any) {
    try {
      const parentCat = (categories || []).find(
        (c: any) => c.name === proposed.parentName,
      );
      const body: Record<string, unknown> = {
        name: proposed.name,
        description: proposed.description,
      };
      if (parentCat) body.parentId = parentCat.id;

      const res = await fetch("/api/admin/catalog/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        const newCat = await res.json();
        for (const sug of categorizeResult?.suggestions || []) {
          if (
            sug.suggestedNewCategory?.name === proposed.name &&
            sug.suggestedNewCategory?.parentName === proposed.parentName
          ) {
            categoryAssignments[sug.itemId] = newCat.id;
          }
        }
        acceptedNewCategories.add(index);
        await invalidateAll();
      }
    } catch {
      errorMsg = "Failed to create category";
    }
  }

  async function publishAllFromModal() {
    publishing = true;
    errorMsg = "";
    successMsg = "";
    let published = 0;
    let failed = 0;

    const endpoint =
      currentType === "ideas"
        ? "/api/admin/catalog/ideas"
        : "/api/admin/catalog/pain-points";

    const toPublish = (categorizeResult?.suggestions || []).filter(
      (sug: any) => categoryAssignments[sug.itemId],
    );
    publishProgress = { current: 0, total: toPublish.length };

    for (const sug of toPublish) {
      const categoryId = categoryAssignments[sug.itemId];

      const item =
        allFetchedItems.find((i: any) => i.id === sug.itemId) ||
        items.find((i: any) => i.id === sug.itemId);
      if (!item) {
        failed++;
        publishProgress = { current: published + failed, total: toPublish.length };
        continue;
      }

      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            categoryId,
            sourceJobId: item.jobId,
            itemIndex: item.itemIndex,
          }),
        });
        if (res.ok) published++;
        else failed++;
      } catch {
        failed++;
      }
      publishProgress = { current: published + failed, total: toPublish.length };
    }

    publishing = false;
    showModal = false;
    selectedIds.clear();
    allFetchedItems = [];

    if (failed > 0) {
      errorMsg = `Published ${published}, failed ${failed}`;
    } else if (published > 0) {
      successMsg = `Successfully published ${published} item${published > 1 ? "s" : ""}`;
    }

    await invalidateAll();
  }
</script>

{#if errorMsg}
  <div class="mb-4 px-4 py-2 bg-error/10 border border-error/30 rounded-lg text-sm text-error">
    {errorMsg}
    <button class="ml-2 underline" onclick={() => (errorMsg = "")}>dismiss</button>
  </div>
{/if}
{#if successMsg}
  <div class="mb-4 px-4 py-2 bg-success/10 border border-success/30 rounded-lg text-sm text-success">
    {successMsg}
    <button class="ml-2 underline" onclick={() => (successMsg = "")}>dismiss</button>
  </div>
{/if}

<!-- Filters -->
<div class="flex flex-wrap gap-3 mb-4">
  <!-- Type toggle -->
  <div class="flex rounded-lg border border-border overflow-hidden">
    <button
      class="px-4 py-2 text-sm font-medium transition-colors {currentType === 'ideas'
        ? 'bg-accent text-white'
        : 'bg-bg-surface text-text-secondary hover:bg-bg-elevated'}"
      onclick={() => updateFilter("type", "ideas")}
    >
      Ideas
    </button>
    <button
      class="px-4 py-2 text-sm font-medium transition-colors {currentType === 'painPoints'
        ? 'bg-accent text-white'
        : 'bg-bg-surface text-text-secondary hover:bg-bg-elevated'}"
      onclick={() => updateFilter("type", "painPoints")}
    >
      Pain Points
    </button>
  </div>

  <!-- User filter -->
  <select
    class="px-3 py-2 bg-bg-surface border border-border rounded-lg text-sm text-text-primary"
    value={data.filters?.userId || ""}
    onchange={(e) => updateFilter("userId", (e.target as HTMLSelectElement).value)}
  >
    <option value="">All Users</option>
    {#each data.owners || [] as owner}
      <option value={owner.id}>{owner.name || owner.id}</option>
    {/each}
  </select>

  <!-- Published filter -->
  <select
    class="px-3 py-2 bg-bg-surface border border-border rounded-lg text-sm text-text-primary"
    value={data.filters?.isPublished || ""}
    onchange={(e) => updateFilter("isPublished", (e.target as HTMLSelectElement).value)}
  >
    <option value="">All</option>
    <option value="false">Unpublished</option>
    <option value="true">Published</option>
  </select>

  <!-- Action bar (when items selected) -->
  {#if selectedIds.size > 0}
    <div class="flex items-center gap-3 ml-auto">
      <!-- Bulk manual publish -->
      <select
        class="px-3 py-2 bg-bg-surface border border-border rounded-lg text-sm text-text-primary"
        bind:value={bulkCategoryId}
      >
        <option value="">Category...</option>
        {#each allCategories as cat}
          <option value={cat.id}>
            {cat.parentName ? `${cat.parentName} > ` : ""}{cat.name}
          </option>
        {/each}
      </select>
      <button
        class="btn-primary flex items-center gap-2 text-sm"
        onclick={publishSelected}
        disabled={!bulkCategoryId || publishing || unpublishedSelectedCount === 0}
      >
        {#if publishing}
          <Loader2 class="w-4 h-4 animate-spin" />
        {/if}
        Publish Selected ({unpublishedSelectedCount})
      </button>

      {#if publishedSelectedCount > 0}
        <button
          class="flex items-center gap-2 text-sm px-3 py-1.5 rounded font-medium border border-error/30 text-error hover:bg-error/10 transition-colors"
          onclick={depublishSelected}
          disabled={publishing}
        >
          Depublish Selected ({publishedSelectedCount})
        </button>
      {/if}

      <div class="w-px h-6 bg-border"></div>

      <!-- AI categorize -->
      <button
        class="btn-primary flex items-center gap-2 text-sm"
        onclick={autoCategorize}
        disabled={categorizing || categorizingAll}
      >
        {#if categorizing}
          <Loader2 class="w-4 h-4 animate-spin" />
        {:else}
          <Sparkles class="w-4 h-4" />
        {/if}
        AI Categorize ({selectedIds.size})
      </button>
    </div>
  {:else}
    <!-- Categorize All Uncategorized (when no manual selection) -->
    <div class="flex items-center gap-2 ml-auto">
      {#if categorizingAll}
        <span class="text-sm text-text-muted">
          Categorizing batch {categorizeProgress.current} of {categorizeProgress.total}...
        </span>
        <button
          class="text-sm px-3 py-1.5 rounded border border-error/30 text-error hover:bg-error/10 transition-colors"
          onclick={cancelCategorizeAll}
        >
          Cancel
        </button>
      {:else}
        <button
          class="btn-primary flex items-center gap-2 text-sm"
          onclick={categorizeAllUncategorized}
          disabled={categorizing}
        >
          <Sparkles class="w-4 h-4" />
          Categorize All Uncategorized
        </button>
      {/if}
    </div>
  {/if}
</div>

<!-- Items Table -->
{#if data.itemsData}
  <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-border bg-bg-elevated/50">
            <th class="py-3 px-3 w-10">
              <input
                type="checkbox"
                checked={selectedIds.size === items.length && items.length > 0}
                onchange={toggleSelectAll}
                class="rounded"
              />
            </th>
            <th class="text-left py-3 px-4 text-text-muted font-medium">Name</th>
            <th class="text-left py-3 px-4 text-text-muted font-medium">Niche</th>
            <th class="text-center py-3 px-4 text-text-muted font-medium">
              {currentType === "ideas" ? "Scores" : "Severity/WTP"}
            </th>
            <th class="text-center py-3 px-4 text-text-muted font-medium">
              {currentType === "ideas" ? "Verdict" : "Opportunity"}
            </th>
            <th class="text-center py-3 px-4 text-text-muted font-medium">Status</th>
            <th class="text-left py-3 px-4 text-text-muted font-medium">Category</th>
            <th class="text-center py-3 px-4 text-text-muted font-medium">Action</th>
            <th class="text-left py-3 px-4 text-text-muted font-medium">Date</th>
          </tr>
        </thead>
        <tbody>
          {#each items as item}
            <tr class="border-b border-border/50 hover:bg-bg-elevated/30">
              <td class="py-3 px-3">
                <input
                  type="checkbox"
                  checked={selectedIds.has(item.id)}
                  onchange={() => toggleSelection(item.id)}
                  class="rounded"
                />
              </td>
              <td class="py-3 px-4">
                <div class="font-medium text-text-primary max-w-[220px] truncate" title={item.itemName}>
                  {item.itemName}
                </div>
                {#if item.itemIndex === -1}
                  <span class="text-xs text-accent">Selected solution</span>
                {:else if currentType === "ideas"}
                  <span class="text-xs text-text-muted">Alternative #{item.itemIndex + 1}</span>
                {/if}
              </td>
              <td class="py-3 px-4 text-text-secondary max-w-[160px] truncate" title={item.nicheQuery ? `${item.nicheQuery}\n\n${item.niche}` : item.niche}>
                {item.nicheQuery || item.niche}
              </td>
              <td class="py-3 px-4 text-center text-text-secondary">
                {#if currentType === "ideas" && item.itemScores}
                  <span title="Market Fit">{formatScore(item.itemScores.market_fit)}</span>
                  <span class="text-text-muted mx-0.5">/</span>
                  <span title="Novelty">{formatScore(item.itemScores.novelty)}</span>
                {:else if item.itemScores}
                  <span title="Severity">{formatScore(item.itemScores.severity)}</span>
                  <span class="text-text-muted mx-0.5">/</span>
                  <span title="WTP">{formatScore(item.itemScores.willingness_to_pay)}</span>
                {:else}
                  —
                {/if}
              </td>
              <td class="py-3 px-4 text-center">
                {#if item.verdict}
                  <Badge
                    variant={item.verdict === "GO" || item.verdict === "high"
                      ? "success"
                      : item.verdict === "NO-GO" || item.verdict === "low"
                        ? "error"
                        : "warning"}
                    size="sm"
                  >
                    {item.verdict}
                  </Badge>
                {:else}
                  —
                {/if}
              </td>
              <td class="py-3 px-4 text-center">
                <Badge variant={item.isPublished ? "success" : "default"} size="sm">
                  {item.isPublished ? "Published" : "Draft"}
                </Badge>
              </td>
              <td class="py-3 px-4">
                {#if item.isPublished && item.categoryId}
                  {#if changingCategory[item.id]}
                    <!-- Inline category edit -->
                    <div class="flex items-center gap-1">
                      <select
                        class="w-full px-2 py-1 bg-bg-base border border-border rounded text-xs text-text-primary min-w-[140px]"
                        value={changingCategoryValue[item.id] || ""}
                        onchange={(e) => {
                          changingCategoryValue = {
                            ...changingCategoryValue,
                            [item.id]: (e.target as HTMLSelectElement).value,
                          };
                        }}
                      >
                        {#each allCategories as cat}
                          <option value={cat.id}>
                            {cat.parentName ? `${cat.parentName} > ` : ""}{cat.name}
                          </option>
                        {/each}
                      </select>
                      <button
                        class="p-1 rounded hover:bg-success/10 text-success"
                        onclick={() => saveChangeCategory(item)}
                        disabled={changingCategorySaving[item.id] || !changingCategoryValue[item.id]}
                        title="Save"
                      >
                        {#if changingCategorySaving[item.id]}
                          <Loader2 class="w-3 h-3 animate-spin" />
                        {:else}
                          <Check class="w-3 h-3" />
                        {/if}
                      </button>
                      <button
                        class="p-1 rounded hover:bg-bg-elevated text-text-muted"
                        onclick={() => cancelChangeCategory(item.id)}
                        title="Cancel"
                      >
                        <X class="w-3 h-3" />
                      </button>
                    </div>
                  {:else}
                    <div class="flex items-center gap-1">
                      <span class="text-xs text-text-secondary">{getCategoryName(item.categoryId)}</span>
                      {#if item.publishedRecordId}
                        <button
                          class="p-1 rounded hover:bg-bg-elevated text-text-muted hover:text-text-primary"
                          onclick={() => startChangeCategory(item)}
                          title="Change category"
                        >
                          <Pencil class="w-3 h-3" />
                        </button>
                      {/if}
                    </div>
                  {/if}
                {:else if !item.isPublished}
                  <select
                    class="w-full px-2 py-1 bg-bg-base border border-border rounded text-xs text-text-primary min-w-[140px]"
                    value={rowCategories[item.id] || ""}
                    onchange={(e) => {
                      rowCategories = {
                        ...rowCategories,
                        [item.id]: (e.target as HTMLSelectElement).value,
                      };
                    }}
                  >
                    <option value="">Select...</option>
                    {#each allCategories as cat}
                      <option value={cat.id}>
                        {cat.parentName ? `${cat.parentName} > ` : ""}{cat.name}
                      </option>
                    {/each}
                  </select>
                {:else}
                  <span class="text-xs text-text-muted">—</span>
                {/if}
              </td>
              <td class="py-3 px-4 text-center">
                {#if !item.isPublished}
                  <button
                    class="text-xs px-3 py-1.5 rounded font-medium transition-colors
                      {rowCategories[item.id]
                        ? 'bg-accent text-white hover:bg-accent/90'
                        : 'bg-bg-elevated text-text-muted cursor-not-allowed'}"
                    onclick={() => publishSingle(item)}
                    disabled={!rowCategories[item.id] || rowPublishing[item.id]}
                  >
                    {#if rowPublishing[item.id]}
                      <Loader2 class="w-3 h-3 animate-spin inline" />
                    {:else}
                      Publish
                    {/if}
                  </button>
                {:else if item.publishedRecordId}
                  <button
                    class="text-xs px-3 py-1.5 rounded font-medium transition-colors border border-error/30 text-error hover:bg-error/10"
                    onclick={() => (confirmDepublish = { id: item.id, name: item.itemName, type: currentType })}
                    disabled={depublishing[item.id]}
                  >
                    {#if depublishing[item.id]}
                      <Loader2 class="w-3 h-3 animate-spin inline" />
                    {:else}
                      Depublish
                    {/if}
                  </button>
                {:else}
                  <span class="text-xs text-text-muted">—</span>
                {/if}
              </td>
              <td class="py-3 px-4 text-text-muted text-xs">
                {item.reportGeneratedAt ? formatDate(item.reportGeneratedAt) : "\u2014"}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if items.length === 0}
      <div class="p-8 text-center text-text-muted">No items found. Share some completed reports first.</div>
    {/if}
    <!-- Pagination -->
    {#if data.itemsData.totalPages > 1}
      <div class="flex items-center justify-between px-4 py-3 border-t border-border">
        <span class="text-sm text-text-muted">
          Page {data.itemsData.page} of {data.itemsData.totalPages} ({data.itemsData.total} items)
        </span>
        <div class="flex gap-2">
          {#if data.itemsData.page > 1}
            <a
              href="?{new URLSearchParams({
                ...Object.fromEntries(page.url.searchParams),
                page: String(data.itemsData.page - 1),
              })}"
              class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
            >
              Previous
            </a>
          {/if}
          {#if data.itemsData.page < data.itemsData.totalPages}
            <a
              href="?{new URLSearchParams({
                ...Object.fromEntries(page.url.searchParams),
                page: String(data.itemsData.page + 1),
              })}"
              class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
            >
              Next
            </a>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{:else}
  <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
    <p class="text-text-muted">Failed to load items.</p>
  </div>
{/if}

<!-- Depublish Confirmation Modal -->
{#if confirmDepublish}
  {@const targetItem = items.find((i: any) => i.id === confirmDepublish?.id)}
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <div
      class="fixed inset-0 bg-black/40"
      onclick={() => (confirmDepublish = null)}
      role="button"
      tabindex="-1"
      onkeydown={(e) => { if (e.key === "Escape") confirmDepublish = null; }}
    ></div>
    <div class="relative bg-bg-surface border border-border rounded-xl shadow-xl w-full max-w-md p-6 z-50">
      <h3 class="text-lg font-semibold text-text-primary mb-2">Depublish Item</h3>
      <p class="text-sm text-text-secondary mb-1">
        Are you sure you want to depublish <strong>{confirmDepublish.name}</strong>?
      </p>
      <p class="text-xs text-text-muted mb-4">
        This will remove it from the public catalog and return it to Draft state. It can be re-published later.
      </p>
      <div class="flex justify-end gap-2">
        <button
          class="text-sm px-3 py-1.5 text-text-secondary hover:text-text-primary"
          onclick={() => (confirmDepublish = null)}
        >
          Cancel
        </button>
        <button
          class="text-sm px-4 py-1.5 rounded font-medium bg-error text-white hover:bg-error/90 transition-colors"
          onclick={() => targetItem && depublishSingle(targetItem)}
          disabled={depublishing[confirmDepublish.id]}
        >
          {#if depublishing[confirmDepublish.id]}
            <Loader2 class="w-3 h-3 animate-spin inline mr-1" />
          {/if}
          Depublish
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Categorization Review Modal -->
{#if showModal && categorizeResult}
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <div
      class="fixed inset-0 bg-black/40"
      onclick={() => (showModal = false)}
      role="button"
      tabindex="-1"
      onkeydown={(e) => { if (e.key === "Escape") showModal = false; }}
    ></div>
    <div class="relative bg-bg-surface border border-border rounded-xl shadow-xl w-full max-w-4xl max-h-[80vh] overflow-hidden flex flex-col z-50">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-border">
        <h3 class="text-lg font-semibold text-text-primary">Review Categorization</h3>
        <button class="p-1 rounded hover:bg-bg-elevated" onclick={() => (showModal = false)}>
          <X class="w-5 h-5 text-text-muted" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- Summary line -->
        <div class="px-3 py-2 bg-bg-elevated rounded text-sm text-text-secondary">
          {(categorizeResult.suggestions || []).length} items:
          <span class="text-success font-medium">{(categorizeResult.suggestions || []).filter((s: any) => s.confidence === "high").length} high</span>,
          <span class="text-warning font-medium">{(categorizeResult.suggestions || []).filter((s: any) => s.confidence === "medium").length} medium</span>,
          <span class="text-orange-400 font-medium">{(categorizeResult.suggestions || []).filter((s: any) => s.confidence === "low").length} low</span>
          {#if (categorizeResult.suggestions || []).filter((s: any) => s.confidence === "failed").length > 0},
            <span class="text-error font-medium">{(categorizeResult.suggestions || []).filter((s: any) => s.confidence === "failed").length} failed</span>
          {/if}
        </div>

        {#if categorizeResult.warning}
          <div class="px-3 py-2 bg-warning/10 border border-warning/30 rounded text-sm text-warning">
            {categorizeResult.warning}
          </div>
        {/if}

        <!-- Proposed new categories -->
        {#if categorizeResult.proposedNewCategories?.length > 0}
          <div>
            <h4 class="text-sm font-semibold text-text-primary mb-2">Proposed New Categories</h4>
            <div class="space-y-2">
              {#each categorizeResult.proposedNewCategories as proposed, idx}
                <div class="flex items-center justify-between px-3 py-2 bg-bg-elevated rounded-lg">
                  <div>
                    <span class="text-sm font-medium text-text-primary">{proposed.name}</span>
                    <span class="text-xs text-text-muted ml-2">under {proposed.parentName}</span>
                    {#if proposed.description}
                      <p class="text-xs text-text-muted mt-0.5">{proposed.description}</p>
                    {/if}
                  </div>
                  {#if acceptedNewCategories.has(idx)}
                    <Badge variant="success" size="sm">Created</Badge>
                  {:else}
                    <button
                      class="btn-primary text-xs px-3 py-1"
                      onclick={() => acceptNewCategory(idx, proposed)}
                    >
                      Accept & Create
                    </button>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Item assignments table -->
        <div>
          <h4 class="text-sm font-semibold text-text-primary mb-2">Item Assignments</h4>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-border">
                <th class="text-left py-2 text-text-muted font-medium">Item</th>
                <th class="text-left py-2 text-text-muted font-medium">Category</th>
                <th class="text-center py-2 text-text-muted font-medium">Confidence</th>
                <th class="text-left py-2 text-text-muted font-medium">Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {#each categorizeResult.suggestions || [] as sug}
                {@const item = allFetchedItems.find((i: any) => i.id === sug.itemId) || items.find((i: any) => i.id === sug.itemId)}
                <tr class="border-b border-border/50">
                  <td class="py-2 pr-3 max-w-[180px] truncate text-text-primary" title={item?.itemName}>
                    {item?.itemName || sug.itemId}
                  </td>
                  <td class="py-2 pr-3">
                    <select
                      class="w-full px-2 py-1 bg-bg-base border border-border rounded text-sm"
                      value={categoryAssignments[sug.itemId] || ""}
                      onchange={(e) => {
                        categoryAssignments = {
                          ...categoryAssignments,
                          [sug.itemId]: (e.target as HTMLSelectElement).value,
                        };
                      }}
                    >
                      <option value="">— None —</option>
                      {#each allCategories as cat}
                        <option value={cat.id}>
                          {cat.parentName ? `${cat.parentName} > ` : ""}{cat.name}
                        </option>
                      {/each}
                    </select>
                  </td>
                  <td class="py-2 text-center">
                    <Badge
                      variant={sug.confidence === "high"
                        ? "success"
                        : sug.confidence === "medium"
                          ? "warning"
                          : "error"}
                      size="sm"
                    >
                      {sug.confidence}
                    </Badge>
                  </td>
                  <td class="py-2 text-text-muted text-xs max-w-[200px] truncate" title={sug.reasoning}>
                    {sug.reasoning}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between px-6 py-4 border-t border-border">
        <button class="text-sm text-text-secondary hover:text-text-primary" onclick={() => (showModal = false)}>
          Cancel
        </button>
        <button
          class="btn-primary flex items-center gap-2"
          onclick={publishAllFromModal}
          disabled={publishing || Object.values(categoryAssignments).filter(Boolean).length === 0}
        >
          {#if publishing}
            <Loader2 class="w-4 h-4 animate-spin" />
            Publishing {publishProgress.current}/{publishProgress.total}...
          {:else}
            Publish All ({Object.values(categoryAssignments).filter(Boolean).length})
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
