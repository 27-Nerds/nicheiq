<script lang="ts">
  import type { SavedPainPointItem } from "$lib/types/saved";
  import Bookmark from "lucide-svelte/icons/bookmark";
  import Pencil from "lucide-svelte/icons/pencil";
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
  </div>
  {#each items as item, i (item.id)}
    {@const tier = severityTier(item.painPoint.severityScore)}
    {@const sevPct = severityPercent(item.painPoint.severityScore)}
    <div class="pt-row t-{tier}" role="row">
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
      <button
        type="button"
        class="when"
        role="cell"
        onclick={() => onUnsave(item)}
        aria-label="Remove pain point from saved"
      >
        <Bookmark size={11} fill="currentColor" />
        <span>{formatDistanceToNow(item.createdAt)}</span>
      </button>
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
            aria-label="Edit note"
          >
            <span>{item.notes}</span>
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
    </div>
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
    grid-template-columns: 44px 1fr 100px 160px 90px 220px;
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
    grid-template-columns: 44px 1fr 100px 160px 90px 220px;
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
  .when {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 6px;
    border: none;
    background: transparent;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    cursor: pointer;
    transition: color 120ms ease;
    justify-self: end;
  }
  .when:hover {
    color: var(--color-accent);
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
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    padding-right: 22px;
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

  @media (max-width: 900px) {
    .pt-head {
      display: none;
    }
    .pt-row {
      grid-template-columns: 36px 1fr;
      grid-template-areas:
        "rank title"
        ". meta"
        ". note";
      row-gap: 6px;
    }
    .rank {
      grid-area: rank;
    }
    .ttl {
      grid-area: title;
    }
    .men,
    .sev,
    .when {
      grid-area: meta;
      justify-self: start;
    }
    .men + .sev,
    .sev + .when {
      margin-left: 12px;
    }
    .note-cell {
      grid-area: note;
    }
  }
</style>
