<script lang="ts">
  import type { SavedIdeaItem, SavedIdeaItemUnlocked } from "$lib/types/saved";
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import IdeaCardV2 from "$lib/components/catalog/seo/IdeaCardV2.svelte";
  import Pencil from "lucide-svelte/icons/pencil";
  import X from "lucide-svelte/icons/x";
  import NoteEditor from "./NoteEditor.svelte";
  import { formatDistanceToNow } from "./formatRelative";

  // Only renders ACCESSIBLE saved ideas — the parent routes locked items to
  // <LockedSavedCard>, so `item.idea` is always present here.
  interface Props {
    item: SavedIdeaItemUnlocked;
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
    // Scores are stored 0–1 in the DB; IdeaCardV2 multiplies by 100 for the
    // dials. Pass them through raw — exactly as the public catalog projection
    // does. (Dividing by 100 here collapsed every dial to "1".)
    market_fit_score: item.idea.marketFitScore,
    technical_feasibility_score: item.idea.technicalFeasibility,
    seo_scalability_score: item.idea.seoScalabilityScore,
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
  <!-- Explicit "Remove from saved" affordance — replaces the older
       bookmark+timestamp button that conflated metadata with action. The
       pill is muted by default, accent on hover, and the only interactive
       element of its kind on the card. Click flows through onUnsave →
       optimistic remove → UndoToast (5-second undo, no logic change). -->
  <button
    type="button"
    class="saved-remove"
    onclick={() => onUnsave(item)}
    aria-label={`Remove "${item.idea.headline ?? item.idea.solutionName}" from saved`}
    title="Remove from saved"
  >
    <X size={12} aria-hidden="true" />
    <span>Remove</span>
  </button>

  <IdeaCardV2 idea={preview} subLabel={nichePath} flush />

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
      aria-label={`Edit note: ${item.notes.slice(0, 80)}${item.notes.length > 80 ? "…" : ""}`}
    >
      <span class="saved-note-text">
        <span class="saved-note-kicker" aria-hidden="true">NOTE</span>{item.notes}</span>
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

  <!-- Saved-since byline — a single muted, right-aligned timestamp in normal
       flow below the note. (The auto-numbered folio that used to sit on the
       left was dropped: it was a volatile grid-position number with no stable
       meaning.) The remove action lives in .saved-remove (top-right). -->
  <span class="saved-when" aria-hidden="true">
    Saved {formatDistanceToNow(item.createdAt)} ago
  </span>
</div>

<style>
  .saved-card {
    position: relative;
    /* This is the card shell. IdeaCardV2 renders flush (frameless) inside it,
       with the note + saved-since timestamp as a footer below — all within
       this one border, so nothing floats outside the box. The verdict rail
       (.saved-card::before) rides this left edge; the 16px padding keeps the
       content clear of it. */
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    padding: 16px;
    transition:
      border-color 0.15s ease,
      box-shadow 0.15s ease;
    /* Stagger reveal — each <li> in .cards-grid sets `--i` (capped at 5).
       Opacity-only; movement-free per the editorial direction. Replays on
       optimistic remove → undo and on filter changes; that's the intended
       feel: gentle ledger entries appearing in your notebook. */
    opacity: 0;
    animation: saved-docket-in 240ms ease-out forwards;
    animation-delay: calc(var(--i, 0) * 30ms);
  }
  /* Neutral elevation on hover — same idiom as IdeaCardV2 in the catalog
     (no translateY lift, per the project anti-slop convention). */
  .saved-card:hover {
    border-color: var(--color-border-emphasis);
    box-shadow:
      0 1px 2px rgba(24, 24, 27, 0.04),
      0 4px 12px rgba(24, 24, 27, 0.06);
  }
  @keyframes saved-docket-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .saved-card {
      opacity: 1;
      animation: none;
    }
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
  /* "NOTE" mono kicker prefixed inside the clamped span so it counts as
     part of the visible text and the line-clamp continues to work. */
  .saved-note-kicker {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    margin-right: 0.5rem;
    font-style: normal;
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

  /* Saved-since byline — a single muted, right-aligned timestamp in normal
     flow beneath the note. (Replaces the folio + timestamp row; the
     auto-numbered folio was dropped as a volatile, meaningless accent.) */
  .saved-when {
    display: block;
    text-align: right;
    margin-top: 12px;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    font-feature-settings: "tnum";
  }

  /* Explicit "Remove from saved" pill at the top-right corner. Always
     visible (no hover-reveal) so the affordance is unambiguous; muted by
     default so it doesn't dominate the reading layout; accent on hover. */
  .saved-remove {
    position: absolute;
    top: 12px;
    right: 12px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
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
    z-index: 2;
  }
  .saved-remove:hover {
    color: var(--color-accent);
    border-color: var(--color-accent);
    background: var(--color-bg-elevated, #fff);
  }

  /* Shared focus rule — accent ring on every interactive control inside
     the card. (.saved-when is no longer a button per the redesign — it's
     plain metadata text and intentionally NOT in this list.) */
  .saved-note:focus-visible,
  .saved-note-add:focus-visible,
  .saved-remove:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 4px;
  }
</style>
