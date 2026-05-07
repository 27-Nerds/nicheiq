<script lang="ts">
  import type { SavedIdeaItem } from "$lib/types/saved";
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import IdeaCardV2 from "$lib/components/catalog/seo/IdeaCardV2.svelte";
  import Bookmark from "lucide-svelte/icons/bookmark";
  import Pencil from "lucide-svelte/icons/pencil";
  import NoteEditor from "./NoteEditor.svelte";
  import { formatDistanceToNow } from "./formatRelative";

  interface Props {
    item: SavedIdeaItem;
    onUnsave: (item: SavedIdeaItem) => void;
    onNotesChange: (item: SavedIdeaItem, notes: string | null) => void;
  }

  let { item, onUnsave, onNotesChange }: Props = $props();

  // "Parent · Leaf" niche path when the item lives in a sub-niche; the leaf
  // name alone otherwise. Passed to IdeaCardV2 as `subLabel` so the existing
  // .ic-meta row carries the full hierarchy without changing that component.
  const nichePath = $derived(
    item.idea.category.parent
      ? `${item.idea.category.parent.name} · ${item.idea.category.name}`
      : item.idea.category.name,
  );

  // Adapt the backend's camelCase projection to the snake_case IdeaPreview
  // shape that IdeaCardV2 (and its inner helpers) expect. Only the fields
  // the card actually reads are mapped — extras stay null.
  const preview = $derived<IdeaPreview>({
    id: item.idea.id,
    slug: item.idea.slug,
    solution_name: item.idea.solutionName,
    headline: item.idea.headline,
    short_description: item.idea.shortDescription,
    description: item.idea.description,
    value_proposition: null,
    project_type: item.idea.projectType,
    format: item.idea.format,
    core_features: null,
    target_personas: null,
    differentiation_factors: null,
    pricing_strategy: null,
    estimated_development_time: null,
    market_fit_score:
      item.idea.marketFitScore == null ? null : item.idea.marketFitScore / 100,
    technical_feasibility_score:
      item.idea.technicalFeasibility == null
        ? null
        : item.idea.technicalFeasibility / 100,
    seo_scalability_score:
      item.idea.seoScalabilityScore == null
        ? null
        : item.idea.seoScalabilityScore / 100,
    novelty_score: null,
    solo_dev_feasibility: null,
    estimated_cac_organic: null,
    programmatic_seo_opportunity: null,
    technical_approach: null,
    estimated_indexable_pages: null,
    why_it_works: null,
    conventional_approach: null,
    innovation_angle: null,
    estimated_cac_paid: null,
    organic_discovery_queries: null,
    source_niche: item.idea.sourceNiche,
    source_verdict: item.idea.sourceVerdict,
    is_featured: item.idea.isFeatured,
    category: item.idea.category,
    created_at: null,
    updated_at: null,
  } as unknown as IdeaPreview);

  const verdictClass = $derived.by(() => {
    const v = (item.idea.sourceVerdict ?? "").toUpperCase();
    if (v === "GO") return "v-go";
    if (v === "CONDITIONAL" || v === "CONDITIONAL_GO") return "v-cond";
    if (v === "NO_GO" || v === "NO-GO") return "v-no";
    return "v-none";
  });

  let editingNotes = $state(false);

  function startEditNote() {
    editingNotes = true;
  }
  function cancelEditNote() {
    editingNotes = false;
  }
  function commitNote(value: string) {
    const trimmed = value.trim();
    onNotesChange(item, trimmed === "" ? null : trimmed);
    editingNotes = false;
  }
</script>

<div class="saved-card {verdictClass}">
  <IdeaCardV2 idea={preview} subLabel={nichePath} />

  <!-- Notes block — sits below the card in its own row so it doesn't
       compete with the IdeaCardV2 internals. Italic with --accent left rail
       reads as marginalia (per design appendix). -->
  {#if editingNotes}
    <div class="saved-note-edit">
      <NoteEditor
        initialValue={item.notes ?? ""}
        placeholder="Why does this idea matter to you? (Optional)"
        onCommit={commitNote}
        onCancel={cancelEditNote}
      />
    </div>
  {:else if item.notes}
    <button
      type="button"
      class="saved-note"
      onclick={startEditNote}
      aria-label="Edit note"
    >
      <span class="saved-note-text">{item.notes}</span>
      <span class="saved-note-pencil" aria-hidden="true">
        <Pencil size={11} />
      </span>
    </button>
  {:else}
    <button
      type="button"
      class="saved-note-add"
      onclick={startEditNote}
      aria-label="Add a note to this saved idea"
    >
      <Pencil size={12} />
      <span>Add note</span>
    </button>
  {/if}

  <button
    type="button"
    class="saved-when"
    onclick={() => onUnsave(item)}
    aria-label="Remove this idea from saved"
  >
    <Bookmark size={11} fill="currentColor" />
    <span>{formatDistanceToNow(item.createdAt)}</span>
  </button>
</div>

<style>
  .saved-card {
    position: relative;
    /* The verdict rail rides on the IdeaCardV2 left edge. Add inset
       padding so the rail doesn't overlap the card's own border. */
  }
  /* Verdict severity rail — 3px left border using the catalog's existing
     pain-table rail vocabulary, transposed to ideas. Maps verdict tier
     to the same color set: GO=success, CONDITIONAL=warn, NO_GO=error. */
  .saved-card::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: 8px 0 0 8px;
    pointer-events: none;
    z-index: 1;
  }
  .saved-card.v-go::before {
    background: var(--color-success-dark, #16a34a);
  }
  .saved-card.v-cond::before {
    background: var(--color-warning, #ca8a04);
  }
  .saved-card.v-no::before {
    background: var(--color-error-dark, #dc2626);
  }
  .saved-card.v-none::before {
    background: transparent;
  }

  /* Notes marginalia — italic, --accent rail, two-line clamp. Click opens
     the inline editor. */
  .saved-note {
    display: block;
    width: 100%;
    margin-top: 8px;
    padding: 4px 8px 4px 10px;
    text-align: left;
    border: none;
    background: transparent;
    font-family: inherit;
    font-style: italic;
    font-size: 12px;
    line-height: 1.5;
    color: var(--color-text-secondary, var(--color-text-primary));
    border-left: 2px solid var(--color-accent);
    cursor: pointer;
    position: relative;
  }
  .saved-note:hover {
    color: var(--color-text-primary);
  }
  .saved-note-text {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .saved-note-pencil {
    position: absolute;
    top: 4px;
    right: 6px;
    color: var(--color-text-muted);
    opacity: 0;
    transition: opacity 120ms ease;
  }
  .saved-note:hover .saved-note-pencil {
    opacity: 1;
  }
  /* Empty-note affordance — a chipped button with pencil icon. Distinct
     from the filled note's italic+rail marginalia (which is for reading);
     this is for "do something". Hairline border + accent on hover keeps it
     visually consistent with the catalog's chip vocabulary. */
  .saved-note-add {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
    padding: 5px 10px;
    border: 1px dashed var(--color-border-emphasis);
    border-radius: 6px;
    background: transparent;
    font-family: inherit;
    font-size: 12px;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:
      color 0.12s ease,
      border-color 0.12s ease,
      background 0.12s ease;
  }
  .saved-note-add:hover {
    color: var(--color-accent);
    border-color: var(--color-border-accent);
    background: rgba(234, 88, 12, 0.04);
    border-style: solid;
  }

  .saved-note-edit {
    margin-top: 8px;
  }

  /* Saved-since glyph — bookmark + mono timestamp at the card's bottom-right.
     Click unsaves (bubbles up to the page-level optimistic toggle). */
  .saved-when {
    position: absolute;
    bottom: 14px;
    right: 14px;
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
    z-index: 2;
  }
  .saved-when:hover {
    color: var(--color-accent);
  }
</style>
