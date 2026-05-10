<script lang="ts">
  import { Sparkles, Trash2, Plus, X } from "lucide-svelte";
  import type { FaqEntry, FaqJsonMeta } from "$lib/types/catalog-landing";

  // Reusable Generate-FAQ button + preview/edit modal. Used by:
  //   - /admin/catalog/[id]/seo (category)
  //   - /admin/catalog/ideas/[id]/faq (new mini-editor)
  //   - /admin/catalog/pain-points/[id]/faq (new mini-editor)
  // Handles the full generate → preview → edit → save flow including the
  // overwrite-confirm step, 429 rate-limit toast, and cost banner.

  type EntityType = "category" | "idea" | "pain-point";

  interface Props {
    entityType: EntityType;
    entityId: string;
    /** Currently-saved FAQ on the entity (drives the Generate vs Regenerate
     *  label and the overwrite-confirm dialog). */
    existingFaqs: FaqEntry[] | null;
    /** Currently-saved meta (drives the provenance chip). */
    meta: FaqJsonMeta | null;
    /** Called after a successful save so the parent page can refresh. */
    onSaved: () => void | Promise<void>;
  }

  let { entityType, entityId, existingFaqs, meta, onSaved }: Props = $props();

  const existingCount = $derived(existingFaqs?.length ?? 0);
  const buttonLabel = $derived(existingCount > 0 ? "Regenerate FAQ" : "Generate FAQ");

  // Provenance chip text — switches on each save (via meta refresh from parent).
  const provenanceText = $derived.by(() => {
    if (!meta) return null;
    const when = formatRelative(meta.updatedAt);
    if (meta.source === "generated") {
      const m = meta.model ? ` by ${meta.model}` : "";
      return `Last generated${m} · ${when}`;
    }
    return `Manually edited · ${when}`;
  });

  function formatRelative(iso: string): string {
    try {
      const then = new Date(iso).getTime();
      const now = Date.now();
      const diff = Math.max(0, now - then);
      const min = Math.floor(diff / 60000);
      if (min < 1) return "just now";
      if (min < 60) return `${min} min ago`;
      const hr = Math.floor(min / 60);
      if (hr < 24) return `${hr} hr ago`;
      const d = Math.floor(hr / 24);
      return `${d} day${d === 1 ? "" : "s"} ago`;
    } catch {
      return "recently";
    }
  }

  let generating = $state(false);
  let saving = $state(false);
  let previewing = $state(false);
  let previewFaqs = $state<FaqEntry[]>([]);
  let lastModel = $state<string | null>(null);
  let lastTokensUsed = $state<number | null>(null);
  let lastCostUsd = $state<number | null>(null);
  let lastGeneratedAt = $state<string | null>(null);
  let toast = $state<{ kind: "ok" | "err"; msg: string } | null>(null);
  let toastTimeout: ReturnType<typeof setTimeout> | null = null;

  function showToast(kind: "ok" | "err", msg: string) {
    toast = { kind, msg };
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => (toast = null), 5000);
  }

  async function startGenerate() {
    if (existingCount > 0) {
      const ok = confirm(
        `Regenerate will replace the ${existingCount} existing Q&As. ` +
          `You can review and edit before saving. Continue?`,
      );
      if (!ok) return;
    }
    await runGenerate();
  }

  async function runGenerate() {
    generating = true;
    toast = null;
    try {
      const res = await fetch("/api/admin/catalog/faq/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entityType, entityId }),
      });
      const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      if (!res.ok) {
        const errText = (data.error as string | undefined) ?? `HTTP ${res.status}`;
        showToast("err", errText);
        return;
      }
      const faqs = (data.faqs as FaqEntry[] | undefined) ?? [];
      previewFaqs = faqs.map((f) => ({ q: f.q, a: f.a }));
      lastModel = (data.model as string | null) ?? null;
      lastTokensUsed = (data.tokensUsed as number | null) ?? null;
      lastCostUsd = (data.estimatedCostUsd as number | null) ?? null;
      lastGeneratedAt = (data.generatedAt as string | null) ?? null;
      previewing = true;
    } catch (err) {
      showToast("err", err instanceof Error ? err.message : "Generate failed");
    } finally {
      generating = false;
    }
  }

  async function savePreview() {
    if (previewFaqs.length < 2) {
      showToast("err", "Need at least 2 FAQ entries to save.");
      return;
    }
    saving = true;
    try {
      const body = {
        entityType,
        entityId,
        faqs: previewFaqs.map((f) => ({ q: f.q.trim(), a: f.a.trim() })),
        source: "generated" as const,
        ...(lastModel ? { model: lastModel } : {}),
        ...(lastGeneratedAt ? { generatedAt: lastGeneratedAt } : {}),
        ...(lastTokensUsed !== null ? { tokensUsed: lastTokensUsed } : {}),
      };
      const res = await fetch("/api/admin/catalog/faq/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      if (!res.ok) {
        const errText = (data.error as string | undefined) ?? `HTTP ${res.status}`;
        showToast("err", errText);
        return;
      }
      previewing = false;
      showToast("ok", "FAQ saved.");
      await onSaved();
    } catch (err) {
      showToast("err", err instanceof Error ? err.message : "Save failed");
    } finally {
      saving = false;
    }
  }

  function addRow() {
    if (previewFaqs.length >= 10) return;
    previewFaqs = [...previewFaqs, { q: "", a: "" }];
  }
  function removeRow(idx: number) {
    previewFaqs = previewFaqs.filter((_, i) => i !== idx);
  }
  function cancelPreview() {
    previewing = false;
  }

  function handleEsc(ev: KeyboardEvent) {
    if (ev.key === "Escape" && previewing && !saving) cancelPreview();
  }
</script>

<svelte:window onkeydown={handleEsc} />

<div class="generator-row">
  <button
    type="button"
    class="generate-btn"
    onclick={startGenerate}
    disabled={generating || saving}
  >
    <Sparkles class="w-3.5 h-3.5" />
    {generating ? "Generating…" : buttonLabel}
  </button>
  {#if provenanceText}
    <span class="provenance" title={meta?.updatedAt}>{provenanceText}</span>
  {/if}
</div>

{#if previewing}
  <!-- Modal — portal-style fixed overlay; mirrors CategorySheet pattern. -->
  <div class="modal-backdrop" onclick={cancelPreview} role="presentation">
    <div
      class="modal-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="faq-preview-title"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
      tabindex="-1"
    >
      <header class="modal-head">
        <h2 id="faq-preview-title">Review generated FAQ</h2>
        <button
          type="button"
          class="close-btn"
          onclick={cancelPreview}
          aria-label="Close preview"
        >
          <X class="w-4 h-4" />
        </button>
      </header>

      <div class="modal-body">
        <div class="cost-banner">
          {#if lastModel}
            <span class="cost-pill">{lastModel}</span>
          {/if}
          {#if lastTokensUsed !== null}
            <span>{lastTokensUsed.toLocaleString()} tokens</span>
          {/if}
          {#if lastCostUsd !== null && lastCostUsd >= 0}
            <span>≈ ${lastCostUsd.toFixed(4)}</span>
          {:else if lastCostUsd !== null}
            <span>≈ $? (unknown model)</span>
          {/if}
          <span class="cdn-note">Public pages refresh within ~15 min (CDN).</span>
        </div>

        <div class="faq-list">
          {#each previewFaqs as entry, idx (idx)}
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
                type="button"
                class="remove-btn"
                onclick={() => removeRow(idx)}
                aria-label="Remove FAQ entry"
                title="Remove"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          {/each}
        </div>

        <button
          type="button"
          class="add-btn"
          onclick={addRow}
          disabled={previewFaqs.length >= 10}
        >
          <Plus class="w-3.5 h-3.5" />
          Add question
        </button>
      </div>

      <footer class="modal-foot">
        <button
          type="button"
          class="link-btn"
          onclick={runGenerate}
          disabled={generating || saving}
        >
          {generating ? "Regenerating…" : "Regenerate"}
        </button>
        <div class="footer-spacer"></div>
        <button type="button" class="cancel-btn" onclick={cancelPreview} disabled={saving}>
          Cancel
        </button>
        <button
          type="button"
          class="save-btn"
          onclick={savePreview}
          disabled={saving || previewFaqs.length < 2}
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </footer>
    </div>
  </div>
{/if}

{#if toast}
  <div class="toast toast-{toast.kind}" role="status">{toast.msg}</div>
{/if}

<style>
  .generator-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .generate-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-accent);
    background: transparent;
    border: 1px solid var(--color-accent);
    border-radius: 0.375rem;
    cursor: pointer;
    transition: background 140ms ease;
  }
  .generate-btn:hover:not(:disabled) {
    background: rgba(var(--color-accent-rgb, 99 102 241), 0.08);
  }
  .generate-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .provenance {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
  }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
    padding: 1.5rem;
  }

  .modal-dialog {
    background: var(--color-bg-elevated, var(--color-bg-base));
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    width: min(720px, 100%);
    max-height: calc(100vh - 3rem);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
  }

  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--color-border);
  }
  .modal-head h2 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .close-btn {
    background: transparent;
    border: none;
    color: var(--color-text-muted);
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 0.25rem;
  }
  .close-btn:hover {
    color: var(--color-text-primary);
  }

  .modal-body {
    padding: 1rem 1.25rem;
    overflow-y: auto;
    flex: 1;
  }

  .cost-banner {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    padding: 0.5rem 0.75rem;
    background: rgba(0, 0, 0, 0.04);
    border-radius: 0.375rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
  .cost-pill {
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 0.25rem;
    color: var(--color-text-secondary);
  }
  .cdn-note {
    margin-left: auto;
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
  .input,
  .textarea {
    width: 100%;
    padding: 0.5rem 0.625rem;
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.875rem;
    color: var(--color-text-primary);
  }
  .input:focus,
  .textarea:focus {
    outline: none;
    border-color: var(--color-accent);
  }
  .textarea {
    resize: vertical;
    line-height: 1.5;
    font-family: var(--font-body);
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
    color: var(--color-error);
    border-color: var(--color-error);
  }

  .add-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    margin-top: 0.875rem;
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
    color: var(--color-accent);
  }
  .add-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .modal-foot {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.875rem 1.25rem;
    border-top: 1px solid var(--color-border);
  }
  .footer-spacer {
    flex: 1;
  }
  .link-btn {
    background: transparent;
    border: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
    padding: 0.375rem 0.5rem;
  }
  .link-btn:hover:not(:disabled) {
    color: var(--color-accent);
  }
  .link-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .cancel-btn {
    padding: 0.375rem 0.875rem;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    cursor: pointer;
  }
  .cancel-btn:hover:not(:disabled) {
    color: var(--color-text-primary);
  }
  .save-btn {
    padding: 0.375rem 1rem;
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
  }
  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .toast {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    padding: 0.75rem 1.25rem;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    z-index: 250;
    color: white;
  }
  .toast-ok {
    background: var(--color-success);
  }
  .toast-err {
    background: var(--color-error);
  }
</style>
