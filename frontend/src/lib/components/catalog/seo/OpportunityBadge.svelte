<script lang="ts">
  // Inline opportunity-tier chip (HIGH / MEDIUM / LOW). Visual family matches
  // VerdictBadge so the catalog's small chips stay consistent. Reads the
  // backend's stored `CatalogPainPoint.opportunityLevel` (already lowercase
  // string) and maps to a tone — no recomputation here.

  interface Props {
    level: string | null | undefined;
    /** Quiet variant for dense table rows: neutral border, tone on text
     *  only — no tinted fill. Used by the /ideas index pain table where a
     *  filled green chip next to a red severity bar reads as noise. */
    muted?: boolean;
  }

  let { level, muted = false }: Props = $props();

  const normalized = $derived(
    typeof level === "string" ? level.trim().toLowerCase() : "",
  );

  const label = $derived(
    normalized === "high"
      ? "High"
      : normalized === "medium"
        ? "Medium"
        : normalized === "low"
          ? "Low"
          : null,
  );

  // High = positive opportunity, leans into success-tone green so it reads
  // as "go for it" rather than alarm. Medium = warn (caution amber).
  // Low = muted gray (no special signal).
  const tone = $derived(
    normalized === "high"
      ? "success"
      : normalized === "medium"
        ? "warn"
        : "muted",
  );
</script>

{#if label}
  <span class="opp-badge tone-{tone}" class:muted>{label}</span>
{/if}

<style>
  .opp-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 7px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    white-space: nowrap;
  }
  .tone-success {
    color: var(--color-opportunity);
    border-color: rgba(34, 197, 94, 0.25);
    background: rgba(34, 197, 94, 0.06);
  }
  .tone-warn {
    color: var(--color-warning-text);
    border-color: rgba(202, 138, 4, 0.25);
    background: rgba(202, 138, 4, 0.06);
  }
  .tone-muted {
    color: var(--color-text-muted);
  }
  /* Quiet variant — text-only tone on a neutral chip. Greens/ambers use the
     darker readable tokens (#22C55E at 11px on white fails AA). */
  .opp-badge.muted {
    border-color: var(--color-border);
    background: var(--color-surface);
  }
  .opp-badge.muted.tone-success {
    color: var(--color-opportunity);
  }
  .opp-badge.muted.tone-warn {
    color: var(--color-warning-text);
  }
</style>
