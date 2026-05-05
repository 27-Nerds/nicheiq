<script lang="ts">
  import type { Snippet } from "svelte";

  // Inline section header rendered as "01 · LABEL ────── right-slot".
  // Renders as a semantic <h2> (or <h3> via `level={3}`) so accessibility
  // tools and search engines see the document outline; visual styling stays
  // divider-like.
  //
  // Three variants from the design mock (`/ideas-v2/components.jsx:168-177`):
  //   A) num + label only                — pass num + label
  //   B) num + label + methodology copy  — pass `metaText` (mono lowercase)
  //   C) num + label + custom content    — pass `right` snippet (escape hatch)

  interface Props {
    /** 1-based section number. Padded to 2 digits ("01"). Omit to hide. */
    num?: number | null;
    label: string;
    /** Methodology / count copy for the right slot. Renders mono lowercase
     *  text-muted at 11px, matching the design mock's variant-B treatment.
     *  Mutually exclusive with `right` — if both are provided, `right` wins. */
    metaText?: string | null;
    /** Custom-content right slot for cases where plain text isn't enough
     *  (e.g., a "View all" button). Takes precedence over `metaText`. */
    right?: Snippet;
    /** Heading level. Default 2; pass 3 for nested sections. */
    level?: 2 | 3;
  }

  let {
    num = null,
    label,
    metaText = null,
    right,
    level = 2,
  }: Props = $props();

  const formattedNum = $derived(
    num == null ? null : String(num).padStart(2, "0"),
  );
  const hasRight = $derived(!!right || (metaText != null && metaText !== ""));
</script>

{#if level === 3}
  <h3 class="section-divider">
    <span class="lbl">
      {#if formattedNum}
        <span class="num">{formattedNum}</span>
        <span class="dot">·</span>
      {/if}
      {label}
    </span>
    <span class="line"></span>
    {#if hasRight}
      <span class="right">
        {#if right}
          {@render right()}
        {:else}
          <span class="meta">{metaText}</span>
        {/if}
      </span>
    {/if}
  </h3>
{:else}
  <h2 class="section-divider">
    <span class="lbl">
      {#if formattedNum}
        <span class="num">{formattedNum}</span>
        <span class="dot">·</span>
      {/if}
      {label}
    </span>
    <span class="line"></span>
    {#if hasRight}
      <span class="right">
        {#if right}
          {@render right()}
        {:else}
          <span class="meta">{metaText}</span>
        {/if}
      </span>
    {/if}
  </h2>
{/if}

<style>
  /* Locking font-size + line-height on the divider itself ensures every
     flex child (label, line, right) shares the same line-box height.
     Without this baseline, whitespace text nodes around snippet content
     inherit the <h2>'s default 24px font-size / ~28px line-height and
     vertically offset the right slot vs the label. */
  .section-divider {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 40px 0 16px;
    /* Reset h2/h3 default styles so the visual remains a divider, not a heading. */
    margin: 0;
    font-size: 11px;
    line-height: 1;
    font-weight: normal;
  }
  .lbl {
    font-size: 11px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .num {
    color: var(--color-text-primary);
    font-weight: 700;
  }
  .dot {
    margin: 0 4px;
  }
  .line {
    flex: 1;
    height: 1px;
    background: var(--color-border);
  }
  .right {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    line-height: 1;
  }
  /* Safe baseline for ANY right-slot content (snippet or metaText). Custom
     buttons / icons override via their own classes. */
  .right :global(span),
  .right :global(a) {
    font-size: 11px;
    color: var(--color-text-muted);
  }
  /* Mono variant — applied only when SectionDivider renders metaText. */
  .right .meta {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 400;
    color: var(--color-text-muted);
    text-transform: none;
    letter-spacing: 0;
    white-space: nowrap;
    font-feature-settings: "tnum" 1, "calt" 1;
  }

  @media (max-width: 640px) {
    .section-divider {
      flex-wrap: wrap;
    }
    .right {
      width: 100%;
      justify-content: flex-start;
    }
    .right .meta {
      white-space: normal;
    }
  }
</style>
