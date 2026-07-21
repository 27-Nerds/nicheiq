<script lang="ts">
  import { ArrowLeft, ExternalLink, Plus, Trash2 } from "lucide-svelte";
  import { invalidateAll } from "$app/navigation";
  import FaqGenerator from "$lib/components/admin/FaqGenerator.svelte";
  import type { FaqEntry as FaqEntryType, FaqJsonMeta } from "$lib/types/catalog-landing";

  interface FaqEntry {
    q: string;
    a: string;
  }

  let { data } = $props();

  // Editable form state. Initialized empty and re-synced from `data.category`
  // when the route navigates to a different category, when `invalidateAll()`
  // refreshes the page data after save, or on first render.
  //
  // The resync key combines the category id with `faqJsonMeta.updatedAt` so
  // that a FAQ save (manual or via the FaqGenerator modal) bumps the key and
  // triggers re-sync — without that, the guard would return early on the
  // same-id refresh and the local `faq` array would stay stale until a hard
  // reload.
  let syncedKey = $state<string | null>(null);
  let seoTitle = $state("");
  let seoDescription = $state("");
  let longDescription = $state("");
  let tagsInput = $state("");
  let faq = $state<FaqEntry[]>([]);

  $effect(() => {
    const key = `${data.category.id}:${data.category.faqJsonMeta?.updatedAt ?? ""}`;
    if (syncedKey === key) return;
    syncedKey = key;
    seoTitle = data.category.seoTitle ?? "";
    seoDescription = data.category.seoDescription ?? "";
    longDescription = data.category.longDescription ?? "";
    tagsInput = (data.category.tags ?? []).join(", ");
    faq = Array.isArray(data.category.faqJson)
      ? data.category.faqJson.map((f) => ({ q: f.q, a: f.a }))
      : [];
  });

  let saving = $state(false);
  let toast = $state<{ kind: "ok" | "err"; msg: string } | null>(null);
  let toastTimeout: ReturnType<typeof setTimeout> | null = null;

  function showToast(kind: "ok" | "err", msg: string) {
    toast = { kind, msg };
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => (toast = null), 4000);
  }

  function addFaq() {
    if (faq.length >= 15) return;
    faq = [...faq, { q: "", a: "" }];
  }

  function removeFaq(idx: number) {
    faq = faq.filter((_, i) => i !== idx);
  }

  // Char counters (Zod limits in the backend mirror these).
  const seoTitleLen = $derived(seoTitle.length);
  const seoDescLen = $derived(seoDescription.length);
  const longDescLen = $derived(longDescription.length);

  // Lightweight HTML detector (matches the Zod refine on the backend).
  const NO_HTML = /<[^>]*>/;
  const hasHtmlAnywhere = $derived(
    NO_HTML.test(seoTitle) ||
      NO_HTML.test(seoDescription) ||
      NO_HTML.test(longDescription) ||
      faq.some((f) => NO_HTML.test(f.q) || NO_HTML.test(f.a)),
  );

  // Tag parsing — split on commas, trim, dedupe, cap at 8.
  const parsedTags = $derived(
    tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0)
      .filter((t, i, arr) => arr.indexOf(t) === i)
      .slice(0, 8),
  );

  // Save validity — keep button disabled when input would 400 from the server.
  const canSave = $derived.by(() => {
    if (saving) return false;
    if (hasHtmlAnywhere) return false;
    if (seoTitle && (seoTitle.length < 10 || seoTitle.length > 160)) return false;
    if (seoDescription && (seoDescription.length < 20 || seoDescription.length > 320)) return false;
    if (longDescription && (longDescription.length < 50 || longDescription.length > 2000)) return false;
    for (const f of faq) {
      if (f.q.length > 0 && f.q.length < 5) return false;
      if (f.q.length > 200) return false;
      if (f.a.length > 0 && f.a.length < 10) return false;
      if (f.a.length > 1000) return false;
      if ((f.q && !f.a) || (f.a && !f.q)) return false;
    }
    return true;
  });

  async function save() {
    if (!canSave) return;
    saving = true;
    toast = null;

    // Empty strings → null so the database doesn't store empty placeholder rows.
    const body: Record<string, unknown> = {
      seoTitle: seoTitle.trim() || null,
      seoDescription: seoDescription.trim() || null,
      longDescription: longDescription.trim() || null,
      tags: parsedTags,
      faqJson: faq.length === 0 ? null : faq.map((f) => ({ q: f.q.trim(), a: f.a.trim() })),
    };

    try {
      const res = await fetch(`/api/admin/catalog/categories/${data.category.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok) {
        const detail = result.details?.[0]?.message ?? result.error ?? "Failed to save";
        showToast("err", detail);
        return;
      }
      showToast("ok", "Saved.");
      await invalidateAll();
    } catch (err) {
      showToast("err", err instanceof Error ? err.message : "Failed to save");
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>SEO · {data.category.name} | Admin | NicheIQ</title>
</svelte:head>

<div class="seo-editor max-w-3xl">
  <header class="mb-6">
    <a href="/admin/catalog?tab=categories" class="back-link">
      <ArrowLeft class="w-3.5 h-3.5" />
      Back to categories
    </a>
    <h1 class="text-2xl font-bold text-text-primary mt-3">
      SEO · {data.category.name}
    </h1>
    <p class="text-sm text-text-muted mt-1">
      {#if data.parent}
        <span class="font-mono text-xs">{data.parent.slug}/{data.category.slug}</span>
      {:else}
        <span class="font-mono text-xs">{data.category.slug}</span>
      {/if}
      <span class="mx-1.5">·</span>
      <a href={data.previewPath} target="_blank" rel="noopener" class="preview-link">
        Preview public page
        <ExternalLink class="w-3 h-3" />
      </a>
    </p>
  </header>

  <!-- SEO Title -->
  <div class="field">
    <div class="field-header">
      <label for="seo-title">SEO title</label>
      <span class="char-count" class:over={seoTitleLen > 160} class:under={seoTitleLen > 0 && seoTitleLen < 10}>
        {seoTitleLen} / 160
      </span>
    </div>
    <input
      id="seo-title"
      type="text"
      bind:value={seoTitle}
      placeholder="e.g. Accounting & Finance Ops Ideas | NicheIQ"
      class="input"
    />
    <p class="hint">10–160 characters. Used as the page <code>&lt;title&gt;</code>. Leave blank for the auto-generated default.</p>
  </div>

  <!-- SEO Description -->
  <div class="field">
    <div class="field-header">
      <label for="seo-description">Meta description</label>
      <span class="char-count" class:over={seoDescLen > 320} class:under={seoDescLen > 0 && seoDescLen < 20}>
        {seoDescLen} / 320
      </span>
    </div>
    <textarea
      id="seo-description"
      bind:value={seoDescription}
      rows="2"
      placeholder="Used in SERP previews. Aim for 140–160 chars."
      class="textarea"
    ></textarea>
    <p class="hint">20–320 characters. Falls back to a templated description if empty.</p>
  </div>

  <!-- Long Description -->
  <div class="field">
    <div class="field-header">
      <label for="long-description">Long description (Overview body)</label>
      <span class="char-count" class:over={longDescLen > 2000} class:under={longDescLen > 0 && longDescLen < 50}>
        {longDescLen} / 2000
      </span>
    </div>
    <textarea
      id="long-description"
      bind:value={longDescription}
      rows="10"
      placeholder="Plain text. 200–350 words is the sweet spot. No HTML."
      class="textarea"
    ></textarea>
    <p class="hint">
      50–2000 characters. Renders as the Overview section on the public landing
      page. <strong>HTML is rejected</strong> by the backend (XSS guard).
    </p>
  </div>

  <!-- Tags -->
  <div class="field">
    <div class="field-header">
      <label for="tags">Tags</label>
      <span class="char-count">{parsedTags.length} / 8</span>
    </div>
    <input
      id="tags"
      type="text"
      bind:value={tagsInput}
      placeholder="Comma-separated, e.g. B2B, Vertical, Recurring Revenue"
      class="input"
    />
    {#if parsedTags.length > 0}
      <div class="tag-preview">
        {#each parsedTags as tag}
          <span class="tag-chip font-mono">{tag}</span>
        {/each}
      </div>
    {/if}
    <p class="hint">Up to 8. Renders as the chip row beneath the H1.</p>
  </div>

  <!-- FAQ -->
  <div class="field">
    <div class="field-header">
      <span class="field-section-label">FAQ ({faq.length} / 15)</span>
      <button class="add-btn" onclick={addFaq} disabled={faq.length >= 15}>
        <Plus class="w-3.5 h-3.5" />
        Add question
      </button>
    </div>
    <!-- Admin-triggered LLM generator. Click runs OpenAI on the joined
         category data, opens a preview modal, and persists faqJson +
         faqJsonMeta on Save. After save, invalidateAll() reloads this
         page so the chip and the table reflect the new state. -->
    <div class="faq-generator-row">
      <FaqGenerator
        entityType="category"
        entityId={data.category.id}
        existingFaqs={(faq as FaqEntryType[]) ?? null}
        meta={(data.category.faqJsonMeta as FaqJsonMeta | null) ?? null}
        onSaved={async () => {
          await invalidateAll();
        }}
      />
    </div>
    {#if faq.length === 0}
      <p class="empty-faq">
        No FAQ entries yet. Generate one above, or add entries manually — both
        flows persist <code>faqJson</code> and surface as a public
        <code>&lt;CategoryFAQ&gt;</code> + <code>FAQPage</code> JSON-LD when at
        least 2 entries exist.
      </p>
    {/if}
    <div class="faq-list">
      {#each faq as entry, idx}
        <div class="faq-row">
          <div class="faq-fields">
            <input
              type="text"
              bind:value={entry.q}
              placeholder="Question (5–200 chars)"
              class="input"
            />
            <textarea
              bind:value={entry.a}
              rows="3"
              placeholder="Answer (10–1000 chars). No HTML."
              class="textarea"
            ></textarea>
          </div>
          <button
            class="remove-btn"
            onclick={() => removeFaq(idx)}
            aria-label="Remove FAQ entry"
            title="Remove"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      {/each}
    </div>
  </div>

  {#if hasHtmlAnywhere}
    <p class="error-banner">
      One of the fields contains HTML-looking syntax (<code>&lt;…&gt;</code>).
      The backend will reject this. Strip the tags before saving.
    </p>
  {/if}

  <div class="actions">
    <a href="/admin/catalog?tab=categories" class="cancel-link">Cancel</a>
    <button class="btn-primary" onclick={save} disabled={!canSave}>
      {saving ? "Saving…" : "Save"}
    </button>
  </div>

  {#if toast}
    <div class="toast toast-{toast.kind}" role="status">{toast.msg}</div>
  {/if}
</div>

<style>
  .seo-editor {
    padding-bottom: 6rem;
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 140ms ease;
  }
  .back-link:hover {
    color: var(--color-text-primary);
  }

  .preview-link {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    color: var(--color-accent-dark);
    text-decoration: none;
  }
  .preview-link:hover {
    text-decoration: underline;
  }

  .field {
    margin-bottom: 1.5rem;
  }

  .field-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 0.375rem;
  }

  .field-header label,
  .field-section-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .char-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
  }
  .char-count.over {
    color: var(--color-error-text);
  }
  .char-count.under {
    color: var(--color-warning-text);
  }

  .input,
  .textarea {
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: var(--color-bg-base);
    border: 1px solid var(--color-input-border);
    border-radius: 0.375rem;
    font-size: 0.875rem;
    color: var(--color-text-primary);
    transition: border-color 140ms ease, box-shadow 140ms ease;
  }
  .input:hover,
  .textarea:hover {
    border-color: var(--color-input-border-hover);
  }
  .input:focus,
  .textarea:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }
  .textarea {
    resize: vertical;
    line-height: 1.5;
    font-family: var(--font-body);
  }

  .hint {
    margin-top: 0.375rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    line-height: 1.5;
  }

  .tag-preview {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
    margin-top: 0.5rem;
  }
  .tag-chip {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
    border-radius: 0.25rem;
  }

  .add-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: 0.25rem;
    cursor: pointer;
    transition: border-color 140ms ease, color 140ms ease;
  }
  .add-btn:hover:not(:disabled) {
    border-color: var(--color-accent);
    color: var(--color-accent-dark);
  }
  .add-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .faq-generator-row {
    margin-bottom: 0.75rem;
  }

  .empty-faq {
    margin: 0;
    padding: 1rem;
    border: 1px dashed var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.875rem;
    color: var(--color-text-muted);
    line-height: 1.55;
  }
  .empty-faq code {
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .faq-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .faq-row {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .faq-fields {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .remove-btn {
    flex-shrink: 0;
    padding: 0.5rem;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: color 140ms ease, border-color 140ms ease;
  }
  .remove-btn:hover {
    color: var(--color-error-text);
    border-color: var(--color-error-text);
  }

  .error-banner {
    margin: 1rem 0;
    padding: 0.75rem 1rem;
    background: var(--color-error-subtle);
    border: 1px solid color-mix(in srgb, var(--color-error-text) 30%, transparent);
    border-radius: 0.375rem;
    font-size: 0.875rem;
    color: var(--color-error-text);
  }
  .error-banner code {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
  }

  .actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.75rem;
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--color-border);
  }

  .cancel-link {
    font-size: 0.875rem;
    color: var(--color-text-muted);
    text-decoration: none;
  }
  .cancel-link:hover {
    color: var(--color-text-primary);
  }

  .toast {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    padding: 0.75rem 1.25rem;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    z-index: 100;
  }
  .toast-ok {
    background: var(--color-success);
    color: white;
  }
  .toast-err {
    background: var(--color-error);
    color: white;
  }
</style>
