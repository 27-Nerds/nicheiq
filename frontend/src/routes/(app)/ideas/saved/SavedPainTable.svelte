<script lang="ts">
  import type { SavedPainPointItem } from "$lib/types/saved";
  import Pencil from "lucide-svelte/icons/pencil";
  import X from "lucide-svelte/icons/x";
  import NoteEditor from "./NoteEditor.svelte";
  import { formatDistanceToNow } from "./formatRelative";

  interface Props {
    items: SavedPainPointItem[];
    onUnsave: (item: SavedPainPointItem) => void;
    onNotesChange: (item: SavedPainPointItem, notes: string | null) => void;
  }

  let { items, onUnsave, onNotesChange }: Props = $props();

  let editingId = $state<string | null>(null);

  function severityTier(score: number): "high" | "med" | "low" {
    if (score >= 0.7) return "high";
    if (score >= 0.4) return "med";
    return "low";
  }

  function severityPercent(score: number): number {
    return Math.round(score * 100);
  }

  function handleNoteCommit(item: SavedPainPointItem, value: string) {
    const trimmed = value.trim();
    onNotesChange(item, trimmed === "" ? null : trimmed);
    editingId = null;
  }
</script>

<div class="pain-table" role="table">
  <div class="pt-head" role="row">
    <span role="columnheader">#</span>
    <span role="columnheader">Pain point</span>
    <span role="columnheader">Mentions</span>
    <span role="columnheader" class="ar">Severity</span>
    <span role="columnheader" class="ar">Saved</span>
    <span role="columnheader">Note</span>
    <span role="columnheader" class="ar" aria-label="Actions"></span>
  </div>
  {#each items as item, i (item.id)}
    {#if item.locked}
      <!-- Locked row — non-featured pain the user lost access to. Backend strips
           all content + the note; only the lock state + unlock CTA + unsave remain. -->
      <div class="pt-row pt-locked" role="row" style="--i: {Math.min(i, 5)}">
        <span class="rank" role="cell">{String(i + 1).padStart(2, "0")}</span>
        <span class="ttl ttl-locked" role="cell">
          <span class="ttl-text">🔒 Locked pain point</span>
          <span class="ttl-niche">Subscribe to view</span>
        </span>
        <span class="men" role="cell">—</span>
        <span class="sev" role="cell"><span class="num">—</span></span>
        <span class="when" role="cell">Saved {formatDistanceToNow(item.createdAt)} ago</span>
        <span class="note-cell" role="cell">
          <a class="unlock-link" href="/unlock-catalog">Unlock</a>
        </span>
        <button
          type="button"
          class="pt-remove"
          role="cell"
          onclick={() => onUnsave(item)}
          aria-label="Remove locked pain point from saved"
          title="Remove from saved"
        >
          <X size={11} aria-hidden="true" />
          <span>Remove</span>
        </button>
      </div>
    {:else}
      {@const tier = severityTier(item.painPoint.severityScore)}
      {@const sevPct = severityPercent(item.painPoint.severityScore)}
      <div class="pt-row t-{tier}" role="row" style="--i: {Math.min(i, 5)}">
      <span class="rank" role="cell">{String(i + 1).padStart(2, "0")}</span>
      <a
        class="ttl"
        role="cell"
        href={item.painPoint.slug
          ? `/pain-point/${item.painPoint.slug}`
          : "#"}
      >
        <span class="ttl-text">{item.painPoint.title}</span>
        <span class="ttl-niche">
          {#if item.painPoint.category.parent}
            {item.painPoint.category.parent.name} · {item.painPoint.category.name}
          {:else}
            {item.painPoint.category.name}
          {/if}
        </span>
      </a>
      <span class="men" role="cell">{item.painPoint.mentionCount}</span>
      <span class="sev" role="cell">
        <span class="bar" style="--w: {sevPct}%"></span>
        <span class="num">{sevPct}</span>
      </span>
      <!-- Non-interactive timestamp cell (was a button — split into
           passive metadata + an explicit remove button at the row end so
           the affordance is unambiguous). -->
      <span class="when" role="cell">
        Saved {formatDistanceToNow(item.createdAt)} ago
      </span>
      <span class="note-cell" role="cell">
        {#if editingId === item.id}
          <NoteEditor
            initialValue={item.notes ?? ""}
            placeholder="Why this pain matters…"
            onCommit={(v) => handleNoteCommit(item, v)}
            onCancel={() => (editingId = null)}
          />
        {:else if item.notes}
          <button
            type="button"
            class="note-text"
            onclick={() => (editingId = item.id)}
            aria-label={`Edit note: ${item.notes.slice(0, 80)}${item.notes.length > 80 ? "…" : ""}`}
          >
            <span class="note-content"
              ><span class="note-kicker" aria-hidden="true">NOTE</span>{item.notes}</span>
            <Pencil size={11} class="note-pencil" />
          </button>
        {:else}
          <button
            type="button"
            class="note-empty"
            onclick={() => (editingId = item.id)}
            aria-label="Add a note to this pain point"
          >
            <Pencil size={11} />
            <span>Add note</span>
          </button>
        {/if}
      </span>
      <!-- Explicit "Remove from saved" button — replaces the older
           bookmark+timestamp pattern that conflated metadata with action.
           Same onUnsave callback as before, so the existing UndoToast
           flow (5-second undo) keeps working unchanged. -->
      <button
        type="button"
        class="pt-remove"
        role="cell"
        onclick={() => onUnsave(item)}
        aria-label={`Remove "${item.painPoint.title}" from saved`}
        title="Remove from saved"
      >
        <X size={11} aria-hidden="true" />
        <span>Remove</span>
      </button>
      </div>
    {/if}
  {/each}
</div>

<style>
  /* Saved-page extension of the catalog's .pain-table format. The catalog's
     pain-table uses 4 cols (rank/title/mentions/severity); we add 2 more
     (saved-when, note) to surface user-state without losing the existing
     visual rhythm. Severity rails (3px left border) carry over unchanged. */
  .pain-table {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    overflow: hidden;
  }
  .pt-head {
    display: grid;
    grid-template-columns: 44px 1fr 100px 160px 110px 220px 88px;
    padding: 11px 18px;
    background: var(--color-bg-base, #fafafa);
    border-bottom: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    gap: 14px;
    align-items: center;
  }
  .pt-head .ar {
    text-align: right;
  }
  .pt-row {
    display: grid;
    grid-template-columns: 44px 1fr 100px 160px 110px 220px 88px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--color-border);
    gap: 14px;
    align-items: center;
    position: relative;
    transition: background 0.12s ease;
  }
  .pt-row:last-child {
    border-bottom: none;
  }
  /* Severity rail — same vocabulary as the public catalog pain-table. */
  .pt-row::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
  }
  .pt-row.t-high::before {
    background: var(--color-error-dark, #dc2626);
  }
  .pt-row.t-med::before {
    background: var(--color-accent);
  }
  .pt-row.t-low::before {
    background: var(--color-secondary, #2563eb);
  }
  .pt-row:hover {
    background: var(--color-bg-base, #fafafa);
  }
  /* Stagger reveal — each row sets `--i` (capped at 5) inline. Opacity-only
     to match the editorial direction. Replays on optimistic remove → undo
     and on filter changes; intentional, reads as ledger entries appearing. */
  .pt-row {
    opacity: 0;
    animation: saved-row-in 240ms ease-out forwards;
    animation-delay: calc(var(--i, 0) * 30ms);
  }
  @keyframes saved-row-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .pt-row {
      opacity: 1;
      animation: none;
    }
  }
  .rank {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .ttl {
    display: flex;
    flex-direction: column;
    gap: 2px;
    text-decoration: none;
    min-width: 0;
  }
  .ttl-text {
    font-size: 13.5px;
    color: var(--color-text-primary);
    font-weight: 500;
    line-height: 1.4;
  }
  .ttl-niche {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    text-transform: uppercase;
    font-weight: 500;
  }
  .ttl:hover .ttl-text {
    color: var(--color-accent);
  }
  .men {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-secondary);
  }
  .sev {
    display: flex;
    align-items: center;
    gap: 10px;
    justify-content: flex-end;
  }
  .sev .bar {
    width: 90px;
    height: 6px;
    background: var(--color-bg-subtle, #f0f0f0);
    border-radius: 3px;
    position: relative;
    overflow: hidden;
  }
  .sev .bar::after {
    content: "";
    position: absolute;
    inset: 0;
    width: var(--w, 50%);
    background: var(--color-text-muted);
    border-radius: 3px;
  }
  .pt-row.t-high .bar::after {
    background: var(--color-error-dark, #dc2626);
  }
  .pt-row.t-med .bar::after {
    background: var(--color-accent);
  }
  .pt-row.t-low .bar::after {
    background: var(--color-secondary, #2563eb);
  }
  .sev .num {
    font-family: var(--font-mono);
    font-size: 12.5px;
    color: var(--color-text-primary);
    font-weight: 600;
    min-width: 28px;
    text-align: right;
  }
  /* Saved-since timestamp — non-interactive metadata cell. The destructive
     remove action lives in .pt-remove at the row end. */
  .when {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
    font-feature-settings: "tnum";
    justify-self: end;
    text-align: right;
  }

  /* Explicit "× Remove" pill at the row end. Same shape as
     SavedIdeaCard's .saved-remove for visual consistency across both
     surfaces. Muted by default; accent on hover. */
  .pt-remove {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 9px;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:
      color 0.12s ease,
      border-color 0.12s ease,
      background 0.12s ease;
    justify-self: end;
    white-space: nowrap;
  }
  .pt-remove:hover {
    color: var(--color-accent);
    border-color: var(--color-accent);
    background: var(--color-bg-elevated, #fff);
  }
  /* Locked row — muted title, no severity rail, an inline "Unlock" link. */
  .ttl-locked {
    cursor: default;
  }
  .pt-locked .ttl-text {
    color: var(--color-text-muted);
    font-weight: 500;
  }
  .unlock-link {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    color: var(--color-accent);
    text-decoration: none;
  }
  .unlock-link:hover {
    text-decoration: underline;
  }
  .unlock-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 4px;
  }

  .note-cell {
    overflow: hidden;
  }
  .note-text,
  .note-empty {
    display: block;
    width: 100%;
    text-align: left;
    border: none;
    background: transparent;
    font-family: inherit;
    font-style: italic;
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
    border-left: 2px solid var(--color-accent);
    padding: 2px 6px 2px 8px;
    cursor: pointer;
    line-height: 1.4;
    position: relative;
  }
  .note-text {
    padding-right: 22px;
  }
  /* The visible span carries the existing nowrap+ellipsis treatment so
     the truncation behavior is preserved when the NOTE kicker is prefixed
     inline. Keeping it on .note-content (instead of the button) avoids
     conflicts with the absolutely-positioned pencil icon. */
  .note-text .note-content {
    display: inline-block;
    max-width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: middle;
  }
  .note-kicker {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    margin-right: 0.5rem;
    font-style: normal;
  }
  .note-text :global(.note-pencil) {
    position: absolute;
    right: 4px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-text-muted);
    opacity: 0;
    transition: opacity 120ms ease;
  }
  .note-text:hover :global(.note-pencil) {
    opacity: 1;
  }
  /* Pain-row empty-note state — chipped affordance matching SavedIdeaCard's
     .saved-note-add. Discoverable by sight; hover lights up the accent. */
  .note-empty {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border: 1px dashed var(--color-border-emphasis);
    border-radius: 4px;
    background: transparent;
    font-family: inherit;
    font-style: normal;
    font-size: 11px;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:
      color 0.12s ease,
      border-color 0.12s ease,
      background 0.12s ease;
  }
  .note-empty:hover {
    color: var(--color-accent);
    border-color: var(--color-border-accent);
    background: rgba(234, 88, 12, 0.04);
    border-style: solid;
  }

  /* Shared focus rule for every interactive control in the row. (.when is
     no longer a button per the redesign — it's plain timestamp text.) */
  .note-text:focus-visible,
  .note-empty:focus-visible,
  .pt-remove:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 4px;
  }

  /* Mobile layout — switch to flex so each cell flows naturally. The
     previous implementation collapsed three cells (.men, .sev, .when) to
     the same `grid-area: meta` which caused them to overlap. The flex
     layout below replaces that with explicit ordering and wrap so the
     row reads top-to-bottom: rank + remove on the first line, title full
     width, then a meta row, then notes. */
  @media (max-width: 900px) {
    .pt-head {
      display: none;
    }
    .pt-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
      padding: 14px;
    }
    .rank {
      flex: 0 0 auto;
      order: 0;
    }
    .pt-remove {
      flex: 0 0 auto;
      order: 1;
      margin-left: auto;
    }
    .ttl {
      flex: 1 1 100%;
      order: 2;
      min-width: 0;
    }
    .men,
    .sev,
    .when {
      flex: 0 0 auto;
      order: 3;
    }
    .sev {
      justify-content: flex-start;
    }
    .note-cell {
      flex: 1 1 100%;
      order: 4;
    }
  }
</style>
