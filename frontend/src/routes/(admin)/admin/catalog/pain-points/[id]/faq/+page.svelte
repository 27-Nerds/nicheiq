<script lang="ts">
  import { ArrowLeft, Plus, Trash2 } from "lucide-svelte";
  import { invalidateAll } from "$app/navigation";
  import FaqGenerator from "$lib/components/admin/FaqGenerator.svelte";
  import type { FaqEntry as FaqEntryType } from "$lib/types/catalog-landing";

  // FAQ-only mini-editor for catalog pain-points. Mirrors the idea editor —
  // single FAQ section + Generate button + manual save. Pain titles ARE real
  // search phrases so the FaqArraySchema anchor check uses pp.title.

  interface FaqEntry {
    q: string;
    a: string;
  }

  let { data } = $props();

  // Resync key includes faqJsonMeta.updatedAt so a save bumps the key and the
  // local `faq` array refreshes from the freshly-loaded data.
  let syncedKey = $state<string | null>(null);
  let faq = $state<FaqEntry[]>([]);

  $effect(() => {
    const key = `${data.painPoint.id}:${data.painPoint.faqJsonMeta?.updatedAt ?? ""}`;
    if (syncedKey === key) return;
    syncedKey = key;
    faq = Array.isArray(data.painPoint.faqJson)
      ? data.painPoint.faqJson.map((f) => ({ q: f.q, a: f.a }))
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
    if (faq.length >= 10) return;
    faq = [...faq, { q: "", a: "" }];
  }

  function removeFaq(idx: number) {
    faq = faq.filter((_, i) => i !== idx);
  }

  const NO_HTML = /<[^>]*>/;
  const hasHtmlAnywhere = $derived(
    faq.some((f) => NO_HTML.test(f.q) || NO_HTML.test(f.a)),
  );

  const canSave = $derived.by(() => {
    if (saving) return false;
    if (hasHtmlAnywhere) return false;
    if (faq.length > 0 && faq.length < 2) return false;
    if (faq.length > 10) return false;
    for (const f of faq) {
      if (f.q.length > 0 && f.q.length < 5) return false;
      if (f.q.length > 200) return false;
      if (f.a.length > 0 && f.a.length < 10) return false;
      if (f.a.length > 1000) return false;
      if ((f.q && !f.a) || (f.a && !f.q)) return false;
    }
    return true;
  });

  async function saveManual() {
    if (!canSave) return;
    saving = true;
    toast = null;
    try {
      const cleaned = faq
        .filter((f) => f.q.trim() && f.a.trim())
        .map((f) => ({ q: f.q.trim(), a: f.a.trim() }));
      if (cleaned.length > 0 && cleaned.length < 2) {
        showToast("err", "Need at least 2 complete Q&A pairs (or save 0 to clear).");
        return;
      }
      const res = await fetch("/api/admin/catalog/faq/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entityType: "pain-point",
          entityId: data.painPoint.id,
          faqs: cleaned,
          source: "manual",
        }),
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = (result as { error?: string }).error ?? `HTTP ${res.status}`;
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
  <title>FAQ · {data.painPoint.title} | Admin | NicheIQ</title>
</svelte:head>

<div class="seo-editor max-w-3xl">
  <header class="mb-6">
    <a href="/admin/catalog?tab=curate&type=painPoints" class="back-link">
      <ArrowLeft class="w-3.5 h-3.5" />
      Back to pain points
    </a>
    <h1 class="text-2xl font-bold text-text-primary mt-3">
      FAQ · {data.painPoint.title}
    </h1>
    <p class="text-sm text-text-muted mt-1">
      <span class="font-mono text-xs">
        {data.painPoint.category.parent?.name ?? "—"} / {data.painPoint.category.name}
      </span>
    </p>
    <p class="text-xs text-text-muted mt-2">
      FAQs are anchored on the pain title for AI-search citation. Public pages
      may take up to ~1&nbsp;hour to refresh after save (CDN cache).
    </p>
  </header>

  <div class="field">
    <div class="field-header">
      <span class="field-section-label">FAQ ({faq.length} / 10)</span>
      <button class="add-btn" onclick={addFaq} disabled={faq.length >= 10}>
        <Plus class="w-3.5 h-3.5" />
        Add question
      </button>
    </div>
    <div class="faq-generator-row">
      <FaqGenerator
        entityType="pain-point"
        entityId={data.painPoint.id}
        existingFaqs={(faq as FaqEntryType[]) ?? null}
        meta={data.painPoint.faqJsonMeta ?? null}
        onSaved={async () => {
          await invalidateAll();
        }}
      />
    </div>
    {#if faq.length === 0}
      <p class="empty-faq">
        No FAQ entries yet. Click <strong>Generate FAQ</strong> above to draft
        a set from this pain point's data, or add entries manually below.
      </p>
    {/if}
    <div class="faq-list">
      {#each faq as entry, idx (idx)}
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
      One of the FAQ entries contains HTML-looking syntax. The backend will
      reject this. Strip the tags before saving.
    </p>
  {/if}

  <div class="actions">
    <a href="/admin/catalog?tab=curate&type=painPoints" class="cancel-link">Cancel</a>
    <button class="btn-primary" onclick={saveManual} disabled={!canSave}>
      {saving ? "Saving…" : "Save manual edits"}
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
  }
  .back-link:hover {
    color: var(--color-text-primary);
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
  .field-section-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
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
  .faq-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 0.75rem;
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
    color: white;
  }
  .toast-ok {
    background: var(--color-success);
  }
  .toast-err {
    background: var(--color-error);
  }
</style>
