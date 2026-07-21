<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import {
    Plus,
    Pencil,
    Trash2,
    Loader2,
    X,
    Check,
    Eye,
    EyeOff,
    Star,
    GripVertical,
  } from "lucide-svelte";

  // Featured collections admin UI.
  //
  // One pane:
  //  - Top: list of all collections (active + inactive) with edit/activate/delete.
  //  - Inline editor (CollectionForm-style) for create + update.
  //  - Detail pane (CollectionItemPicker) to manage items inside a collection:
  //    pick a category → pick from its ideas/pain-points → add/remove/reorder.
  //
  // Reuses the existing admin tab patterns (CategoriesTab) — Svelte 5 runes,
  // invalidateAll() on mutation, lucide icons, no external state libs.

  interface CollectionRow {
    id: string;
    slug: string;
    name: string;
    description: string | null;
    tagline: string | null;
    colorAccent: string | null;
    sortOrder: number;
    isActive: boolean;
    createdAt: string;
    updatedAt: string;
    _count: { items: number };
  }

  interface CategoryNode {
    id: string;
    name: string;
    slug: string;
    parentId?: string | null;
    children?: CategoryNode[];
  }

  interface CollectionItem {
    id: string;
    collectionId: string;
    ideaId: string | null;
    painPointId: string | null;
    position: number;
    idea?: { id: string; slug: string | null; solutionName: string; headline: string | null; shortDescription: string | null; category: { id: string; name: string; slug: string } } | null;
    painPoint?: { id: string; slug: string | null; title: string; category: { id: string; name: string; slug: string } } | null;
  }

  interface CollectionDetail extends CollectionRow {
    items: CollectionItem[];
  }

  interface Props {
    collections: CollectionRow[];
    categories: CategoryNode[];
  }

  let { collections, categories }: Props = $props();

  // ============================================
  // Form state — create + edit share the same form, distinguished by editingId.
  // ============================================
  let editingId = $state<string | null>(null);
  let showForm = $state(false);
  let saving = $state(false);
  let errorMsg = $state("");

  let formSlug = $state("");
  let formName = $state("");
  let formDescription = $state("");
  let formTagline = $state("");
  let formColorAccent = $state("");
  let formSortOrder = $state(0);
  let formIsActive = $state(true);

  function resetForm() {
    formSlug = "";
    formName = "";
    formDescription = "";
    formTagline = "";
    formColorAccent = "";
    formSortOrder = 0;
    formIsActive = true;
    errorMsg = "";
  }

  function openCreate() {
    resetForm();
    editingId = null;
    showForm = true;
  }

  function openEdit(c: CollectionRow) {
    editingId = c.id;
    formSlug = c.slug;
    formName = c.name;
    formDescription = c.description ?? "";
    formTagline = c.tagline ?? "";
    formColorAccent = c.colorAccent ?? "";
    formSortOrder = c.sortOrder;
    formIsActive = c.isActive;
    errorMsg = "";
    showForm = true;
  }

  function closeForm() {
    showForm = false;
    editingId = null;
    resetForm();
  }

  async function saveCollection() {
    saving = true;
    errorMsg = "";
    try {
      const body = {
        slug: formSlug.trim(),
        name: formName.trim(),
        description: formDescription.trim() || null,
        tagline: formTagline.trim() || null,
        colorAccent: formColorAccent.trim() || null,
        sortOrder: formSortOrder,
        isActive: formIsActive,
      };
      const url = editingId
        ? `/api/admin/catalog/collections/${editingId}`
        : "/api/admin/catalog/collections";
      const res = await fetch(url, {
        method: editingId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        errorMsg = err?.error || `Failed to ${editingId ? "update" : "create"} collection`;
        return;
      }
      closeForm();
      await invalidateAll();
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : "Unknown error";
    } finally {
      saving = false;
    }
  }

  let deletingId = $state<string | null>(null);
  async function deleteCollection(c: CollectionRow) {
    if (!confirm(`Delete collection "${c.name}"? This removes its ${c._count.items} item(s) but doesn't touch the underlying ideas/pain-points.`)) {
      return;
    }
    deletingId = c.id;
    try {
      const res = await fetch(`/api/admin/catalog/collections/${c.id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const err = await res.json().catch(() => ({}));
        alert(err?.error || "Failed to delete");
        return;
      }
      // If the open detail pane is for this collection, close it.
      if (selectedId === c.id) selectedId = null;
      await invalidateAll();
    } finally {
      deletingId = null;
    }
  }

  async function toggleActive(c: CollectionRow) {
    saving = true;
    try {
      const res = await fetch(`/api/admin/catalog/collections/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isActive: !c.isActive }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err?.error || "Failed to toggle active");
        return;
      }
      await invalidateAll();
    } finally {
      saving = false;
    }
  }

  // ============================================
  // Detail pane — selected collection's items.
  // ============================================
  let selectedId = $state<string | null>(null);
  let selectedCollection = $state<CollectionDetail | null>(null);
  let loadingDetail = $state(false);

  async function selectCollection(c: CollectionRow) {
    if (selectedId === c.id) {
      selectedId = null;
      selectedCollection = null;
      return;
    }
    selectedId = c.id;
    loadingDetail = true;
    try {
      const res = await fetch(`/api/admin/catalog/collections/${c.id}`);
      if (!res.ok) {
        selectedCollection = null;
        return;
      }
      const data = await res.json();
      selectedCollection = data.collection;
    } finally {
      loadingDetail = false;
    }
  }

  async function refreshSelected() {
    if (!selectedId) return;
    const res = await fetch(`/api/admin/catalog/collections/${selectedId}`);
    if (res.ok) {
      const data = await res.json();
      selectedCollection = data.collection;
    }
    await invalidateAll();
  }

  // ============================================
  // Item picker — pick a category, then pick from its ideas/pain-points.
  // ============================================
  let pickerCategoryId = $state("");
  let pickerType = $state<"ideas" | "pain-points">("ideas");
  let pickerOptions = $state<Array<{ id: string; label: string; sub: string }>>([]);
  let pickerLoading = $state(false);
  let pickerQuery = $state("");
  let addingItemId = $state<string | null>(null);

  // Flatten the category tree so users can pick a sub-category.
  const flatCategories = $derived.by(() => {
    const out: { id: string; label: string }[] = [];
    for (const top of categories ?? []) {
      out.push({ id: top.id, label: top.name });
      for (const child of top.children ?? []) {
        out.push({ id: child.id, label: `${top.name} → ${child.name}` });
      }
    }
    return out;
  });

  $effect(() => {
    // Reload picker options when category or type changes.
    if (!pickerCategoryId) {
      pickerOptions = [];
      return;
    }
    const cid = pickerCategoryId;
    const type = pickerType;
    pickerLoading = true;
    fetch(`/api/admin/catalog/categories/${cid}/${type === "ideas" ? "ideas" : "pain-points"}`)
      .then((r) => r.json())
      .then((data) => {
        if (cid !== pickerCategoryId || type !== pickerType) return; // stale
        if (type === "ideas") {
          pickerOptions = (data.ideas ?? []).map((i: { id: string; solutionName: string; headline: string | null; sourceNiche: string }) => ({
            id: i.id,
            label: i.headline?.trim() || i.solutionName,
            sub: i.sourceNiche || "",
          }));
        } else {
          pickerOptions = (data.painPoints ?? []).map((p: { id: string; title: string; sourceNiche: string }) => ({
            id: p.id,
            label: p.title,
            sub: p.sourceNiche || "",
          }));
        }
      })
      .finally(() => {
        pickerLoading = false;
      });
  });

  const filteredPickerOptions = $derived.by(() => {
    const q = pickerQuery.trim().toLowerCase();
    if (!q) return pickerOptions;
    return pickerOptions.filter(
      (o) => o.label.toLowerCase().includes(q) || o.sub.toLowerCase().includes(q),
    );
  });

  async function addItem(option: { id: string; label: string }) {
    if (!selectedId) return;
    addingItemId = option.id;
    try {
      const body =
        pickerType === "ideas"
          ? { ideaId: option.id }
          : { painPointId: option.id };
      const res = await fetch(`/api/admin/catalog/collections/${selectedId}/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err?.error || "Failed to add item");
        return;
      }
      await refreshSelected();
    } finally {
      addingItemId = null;
    }
  }

  async function removeItem(item: CollectionItem) {
    if (!selectedId) return;
    if (!confirm("Remove this item from the collection?")) return;
    const res = await fetch(
      `/api/admin/catalog/collections/${selectedId}/items/${item.id}`,
      { method: "DELETE" },
    );
    if (!res.ok && res.status !== 204) {
      const err = await res.json().catch(() => ({}));
      alert(err?.error || "Failed to remove item");
      return;
    }
    await refreshSelected();
  }

  async function moveItem(item: CollectionItem, direction: -1 | 1) {
    if (!selectedCollection || !selectedId) return;
    const items = [...selectedCollection.items];
    const idx = items.findIndex((i) => i.id === item.id);
    const targetIdx = idx + direction;
    if (idx === -1 || targetIdx < 0 || targetIdx >= items.length) return;
    [items[idx], items[targetIdx]] = [items[targetIdx], items[idx]];
    const orderedIds = items.map((i) => i.id);
    const res = await fetch(`/api/admin/catalog/collections/${selectedId}/reorder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ orderedIds }),
    });
    if (!res.ok && res.status !== 204) {
      const err = await res.json().catch(() => ({}));
      alert(err?.error || "Failed to reorder");
      return;
    }
    await refreshSelected();
  }

  // Helper for slug auto-suggest from name.
  function suggestSlug() {
    if (formSlug.trim() === "" && formName.trim() !== "") {
      formSlug = formName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 80);
    }
  }
</script>

<div class="space-y-6">
  <!-- Header + create button -->
  <div class="flex items-center justify-between">
    <div>
      <h3 class="text-lg font-semibold text-text-primary">Featured collections</h3>
      <p class="text-sm text-text-muted mt-1">
        Curate hand-picked groups of ideas or pain-points. Active collections appear on the public catalog index.
      </p>
    </div>
    <button class="btn-secondary" onclick={openCreate}>
      <Plus size={14} /> New collection
    </button>
  </div>

  <!-- Inline create/edit form -->
  {#if showForm}
    <div class="rounded-lg border border-border bg-bg-surface p-4">
      <div class="flex items-center justify-between mb-3">
        <h4 class="text-sm font-semibold">
          {editingId ? "Edit collection" : "New collection"}
        </h4>
        <button
          class="text-text-muted hover:text-text-primary"
          onclick={closeForm}
          aria-label="Close form"
        >
          <X size={16} />
        </button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label class="block">
          <span class="block text-xs font-medium text-text-muted mb-1">Name</span>
          <input
            type="text"
            class="input"
            bind:value={formName}
            onblur={suggestSlug}
            placeholder="e.g., Top SaaS Builder Tools"
          />
        </label>

        <label class="block">
          <span class="block text-xs font-medium text-text-muted mb-1">
            Slug <span class="text-text-muted/60">(lowercase, dashes only)</span>
          </span>
          <input
            type="text"
            class="input mono-field"
            bind:value={formSlug}
            placeholder="top-saas-builder-tools"
            disabled={editingId != null}
          />
        </label>

        <label class="block md:col-span-2">
          <span class="block text-xs font-medium text-text-muted mb-1">Tagline</span>
          <input
            type="text"
            class="input"
            bind:value={formTagline}
            placeholder="e.g., Collection · 24 ideas"
            maxlength="160"
          />
        </label>

        <label class="block md:col-span-2">
          <span class="block text-xs font-medium text-text-muted mb-1">Description</span>
          <textarea
            class="input min-h-[80px]"
            bind:value={formDescription}
            placeholder="Optional. Shown below the title on the collection card."
            maxlength="2000"
          ></textarea>
        </label>

        <label class="block">
          <span class="block text-xs font-medium text-text-muted mb-1">
            Color accent <span class="text-text-muted/60">(hex or token)</span>
          </span>
          <input
            type="text"
            class="input mono-field"
            bind:value={formColorAccent}
            placeholder="#F06030"
            maxlength="20"
          />
        </label>

        <label class="block">
          <span class="block text-xs font-medium text-text-muted mb-1">Sort order</span>
          <input
            type="number"
            class="input"
            bind:value={formSortOrder}
            min="0"
          />
        </label>

        <label class="md:col-span-2 inline-flex items-center gap-2 text-sm">
          <input type="checkbox" bind:checked={formIsActive} />
          Active (visible on public catalog)
        </label>
      </div>

      {#if errorMsg}
        <p class="mt-3 text-sm text-[color:var(--color-error-text)]">{errorMsg}</p>
      {/if}

      <div class="mt-4 flex items-center gap-2">
        <button
          class="btn-primary"
          onclick={saveCollection}
          disabled={saving || !formName.trim() || !formSlug.trim()}
        >
          {#if saving}<Loader2 size={14} class="animate-spin" />{:else}<Check size={14} />{/if}
          {editingId ? "Save changes" : "Create collection"}
        </button>
        <button class="btn-ghost" onclick={closeForm}>
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Collections list -->
  {#if collections.length === 0}
    <div class="rounded-lg border border-dashed border-border p-8 text-center text-sm text-text-muted">
      No collections yet. Create one to feature curated picks on the catalog index.
    </div>
  {:else}
    <ul class="rounded-lg border border-border overflow-hidden divide-y divide-border">
      {#each collections as c (c.id)}
        <li class="bg-bg-surface">
          <div class="flex items-center justify-between gap-3 p-3">
            <button
              class="flex-1 min-w-0 text-left flex items-center gap-3"
              onclick={() => selectCollection(c)}
            >
              <Star
                size={16}
                class={c.isActive ? "text-[color:var(--color-accent-dark)] flex-shrink-0" : "text-text-muted flex-shrink-0"}
              />
              <div class="min-w-0">
                <div class="text-sm font-medium text-text-primary truncate">
                  {c.name}
                  {#if !c.isActive}
                    <span class="ml-2 text-xs font-mono uppercase text-text-muted">inactive</span>
                  {/if}
                </div>
                <div class="text-xs text-text-muted truncate">
                  /{c.slug} · {c._count.items} items · sort {c.sortOrder}
                </div>
              </div>
            </button>
            <div class="flex items-center gap-1 flex-shrink-0">
              <button
                class="rounded-md border border-border p-1.5 hover:bg-bg-elevated text-text-muted hover:text-text-primary"
                onclick={() => toggleActive(c)}
                title={c.isActive ? "Deactivate" : "Activate"}
                aria-label={c.isActive ? "Deactivate" : "Activate"}
                disabled={saving}
              >
                {#if c.isActive}<Eye size={14} />{:else}<EyeOff size={14} />{/if}
              </button>
              <button
                class="rounded-md border border-border p-1.5 hover:bg-bg-elevated text-text-muted hover:text-text-primary"
                onclick={() => openEdit(c)}
                aria-label="Edit"
              >
                <Pencil size={14} />
              </button>
              <button
                class="rounded-md border border-border p-1.5 hover:bg-error/10 text-text-muted hover:text-error"
                onclick={() => deleteCollection(c)}
                aria-label="Delete"
                disabled={deletingId === c.id}
              >
                {#if deletingId === c.id}<Loader2 size={14} class="animate-spin" />{:else}<Trash2 size={14} />{/if}
              </button>
            </div>
          </div>

          <!-- Detail pane (item picker) when selected -->
          {#if selectedId === c.id}
            <div class="border-t border-border p-4 bg-bg-base space-y-4">
              {#if loadingDetail}
                <div class="text-sm text-text-muted flex items-center gap-2">
                  <Loader2 size={14} class="animate-spin" /> Loading items…
                </div>
              {:else if selectedCollection}
                <!-- Existing items -->
                <div>
                  <div class="text-xs font-mono uppercase text-text-muted mb-2">
                    Items ({selectedCollection.items.length})
                  </div>
                  {#if selectedCollection.items.length === 0}
                    <p class="text-sm text-text-muted">No items yet. Pick a category below to add some.</p>
                  {:else}
                    <ul class="rounded-md border border-border divide-y divide-border">
                      {#each selectedCollection.items as item, i (item.id)}
                        <li class="flex items-center gap-2 p-2 bg-bg-surface">
                          <GripVertical size={14} class="text-text-muted flex-shrink-0" />
                          <span class="text-xs font-mono text-text-muted w-6 text-right">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <div class="flex-1 min-w-0">
                            {#if item.idea}
                              <div class="text-sm font-medium truncate">
                                {item.idea.headline?.trim() || item.idea.solutionName}
                              </div>
                              <div class="text-xs text-text-muted truncate">
                                Idea · {item.idea.category.name}
                              </div>
                            {:else if item.painPoint}
                              <div class="text-sm font-medium truncate">{item.painPoint.title}</div>
                              <div class="text-xs text-text-muted truncate">
                                Pain point · {item.painPoint.category.name}
                              </div>
                            {/if}
                          </div>
                          <div class="flex gap-1 flex-shrink-0">
                            <button
                              class="rounded-md border border-border px-2 py-1 text-xs hover:bg-bg-elevated disabled:opacity-30"
                              onclick={() => moveItem(item, -1)}
                              disabled={i === 0}
                              aria-label="Move up"
                            >↑</button>
                            <button
                              class="rounded-md border border-border px-2 py-1 text-xs hover:bg-bg-elevated disabled:opacity-30"
                              onclick={() => moveItem(item, 1)}
                              disabled={i === selectedCollection.items.length - 1}
                              aria-label="Move down"
                            >↓</button>
                            <button
                              class="rounded-md border border-border px-2 py-1 text-xs hover:bg-error/10 text-text-muted hover:text-error"
                              onclick={() => removeItem(item)}
                              aria-label="Remove"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </div>

                <!-- Picker -->
                <div class="rounded-md border border-border p-3 bg-bg-surface">
                  <div class="text-xs font-mono uppercase text-text-muted mb-2">Add items</div>
                  <div class="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
                    <label class="block">
                      <span class="block text-xs font-medium text-text-muted mb-1">Category</span>
                      <select
                        class="input"
                        bind:value={pickerCategoryId}
                      >
                        <option value="">— pick a category —</option>
                        {#each flatCategories as cat (cat.id)}
                          <option value={cat.id}>{cat.label}</option>
                        {/each}
                      </select>
                    </label>
                    <label class="block">
                      <span class="block text-xs font-medium text-text-muted mb-1">Type</span>
                      <select
                        class="input"
                        bind:value={pickerType}
                      >
                        <option value="ideas">Ideas</option>
                        <option value="pain-points">Pain points</option>
                      </select>
                    </label>
                    <label class="block">
                      <span class="block text-xs font-medium text-text-muted mb-1">Filter</span>
                      <input
                        type="text"
                        class="input"
                        bind:value={pickerQuery}
                        placeholder="Filter visible options…"
                      />
                    </label>
                  </div>

                  {#if pickerLoading}
                    <div class="text-sm text-text-muted flex items-center gap-2">
                      <Loader2 size={14} class="animate-spin" /> Loading options…
                    </div>
                  {:else if !pickerCategoryId}
                    <p class="text-sm text-text-muted">Pick a category to see available items.</p>
                  {:else if filteredPickerOptions.length === 0}
                    <p class="text-sm text-text-muted">
                      No {pickerType === "ideas" ? "ideas" : "pain points"} found in this category{pickerQuery ? " matching the filter" : ""}.
                    </p>
                  {:else}
                    <ul class="max-h-60 overflow-auto rounded-md border border-border divide-y divide-border">
                      {#each filteredPickerOptions as opt (opt.id)}
                        {@const alreadyAdded = selectedCollection.items.some(
                          (i) =>
                            (pickerType === "ideas" && i.ideaId === opt.id) ||
                            (pickerType === "pain-points" && i.painPointId === opt.id),
                        )}
                        <li class="flex items-center justify-between gap-2 p-2 bg-bg-base">
                          <div class="min-w-0 flex-1">
                            <div class="text-sm truncate">{opt.label}</div>
                            {#if opt.sub}
                              <div class="text-xs text-text-muted truncate">{opt.sub}</div>
                            {/if}
                          </div>
                          <button
                            class="rounded-md border border-border px-2 py-1 text-xs hover:bg-accent-hover hover:text-white disabled:opacity-50"
                            onclick={() => addItem(opt)}
                            disabled={alreadyAdded || addingItemId === opt.id}
                          >
                            {#if addingItemId === opt.id}
                              <Loader2 size={12} class="animate-spin" />
                            {:else if alreadyAdded}
                              Added
                            {:else}
                              <span class="inline-flex items-center gap-1">
                                <Plus size={12} /> Add
                              </span>
                            {/if}
                          </button>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </div>
              {:else}
                <p class="text-sm text-text-muted">Failed to load collection details.</p>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  /* .input's font-family is unlayered global CSS, so a Tailwind font-mono
     utility can't win against it (cascade layers rank utilities below
     unlayered rules) — this scoped class out-specificities it instead. */
  .mono-field {
    font-family: var(--font-mono);
  }
</style>
