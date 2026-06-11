<script lang="ts">
  import { IDEA_ICON, PAIN_ICON } from "$lib/config/entity-icons";

  // Self-hiding provenance pill for catalog-seeded jobs. The icon marks the
  // entity TYPE (idea vs pain), the label carries the COUNT (point vs points).
  let { entryMode }: { entryMode?: string | null } = $props();

  const meta = $derived.by(() => {
    switch (entryMode) {
      case "deep_idea":
        return { Icon: IDEA_ICON, label: "Idea", tip: "Seeded from a catalog idea" };
      case "pain_research":
        return { Icon: PAIN_ICON, label: "Pain point", tip: "Seeded from a catalog pain point" };
      case "pain_remix":
        return { Icon: PAIN_ICON, label: "Pain points", tip: "Seeded from catalog pain points (remix)" };
      default:
        return null;
    }
  });
</script>

{#if meta}
  {@const Icon = meta.Icon}
  <span class="prov-badge" title={meta.tip}>
    <Icon size={11} aria-hidden="true" />
    <span>{meta.label}</span>
  </span>
{/if}

<style>
  .prov-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    padding: 1px 7px 1px 6px;
    border-radius: 9999px;
    font-family: var(--font-mono);
    font-size: 9.5px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-accent) 22%, transparent);
    white-space: nowrap;
    line-height: 1.4;
  }
</style>
