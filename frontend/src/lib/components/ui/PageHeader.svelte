<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";
  import Breadcrumb from "./Breadcrumb.svelte";

  type IconColor = "accent" | "secondary" | "warning";
  type TitleVariant = "default" | "research-topic";

  interface Props {
    title: string;
    titleVariant?: TitleVariant;
    subtitle?: string;
    icon?: ComponentType;
    iconColor?: IconColor;
    breadcrumbItems?: Array<{ label: string; href: string }>;
    breadcrumbCurrent?: string;
    actions?: Snippet;
    badge?: Snippet;
    metadata?: Snippet;
    below?: Snippet;
    class?: string;
  }

  let {
    icon: Icon,
    title,
    titleVariant = "default",
    subtitle,
    iconColor = "accent",
    breadcrumbItems,
    breadcrumbCurrent,
    actions,
    badge,
    metadata,
    below,
    class: className = "",
  }: Props = $props();

  // Icon renders bare (no tinted box) — the icon-in-tinted-box pattern is
  // banned (DESIGN_SYSTEM.md §9.3).
  const colorMap: Record<IconColor, { text: string }> = {
    accent: { text: "text-accent" },
    secondary: { text: "text-secondary" },
    warning: { text: "text-warning" },
  };

  const colors = $derived(Icon ? colorMap[iconColor] : null);
  const hasBreadcrumb = $derived(!!(breadcrumbItems && breadcrumbCurrent));
  const actionsInTitleRow = $derived(!!actions);
  const isResearchTopic = $derived(titleVariant === "research-topic");
  const isLongResearchTopic = $derived(isResearchTopic && title.trim().length > 96);
</script>

<div class="page-header mb-8 {className}" class:page-header--research-topic={isResearchTopic}>
  {#if breadcrumbItems && breadcrumbCurrent}
    <div class="page-header-top flex items-center justify-between gap-4 flex-wrap">
      <Breadcrumb items={breadcrumbItems} current={breadcrumbCurrent} />
    </div>
  {/if}

  <div class={actionsInTitleRow ? 'page-header-body flex items-center justify-between flex-wrap gap-4' : 'page-header-body'}>
    <div class="page-header-title-row flex items-start gap-3" data-annotation-anchor="research-header-copy">
      {#if Icon && colors}
        <Icon class="w-6 h-6 {colors.text} shrink-0" />
      {/if}
      <div>
        <h1
          class="page-header-title text-text-primary flex items-center gap-3 text-balance"
          class:page-header-title--research-topic={isResearchTopic}
          class:page-header-title--long={isLongResearchTopic}
          title={isLongResearchTopic ? title : undefined}
          data-annotation-anchor={isResearchTopic ? "research-header-title" : undefined}
        >
          {title}
          {#if badge}{@render badge()}{/if}
        </h1>
        {#if subtitle}
          <p
            class="page-header-subtitle text-text-muted mt-1 text-pretty"
            data-annotation-anchor={isResearchTopic ? "research-header-subtitle" : undefined}
          >{subtitle}</p>
        {/if}
        {#if metadata}
          <div class="page-header-meta">
            {@render metadata()}
          </div>
        {/if}
      </div>
    </div>
    {#if actions}
      <div class="page-header-actions">
        {@render actions()}
      </div>
    {/if}
  </div>

  {#if below}
    <div class="mt-5">
      {@render below()}
    </div>
  {/if}
</div>

<style>
  /* Page title — snapped to the doc's command-header scale (.cmd h2, §5.1). */
  .page-header-title {
    font-family: var(--font-display);
    font-size: 1.375rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.15;
  }

  /* record-line recipe (§2) — canonical mono meta treatment for label/value
     metadata content passed via the `metadata` snippet. */
  .page-header-meta {
    margin-top: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
  }

  .page-header--research-topic {
    margin-bottom: 0;
  }

  .page-header--research-topic .page-header-title-row {
    /* Keep the semantic annotation anchor independent from optional actions
       (for example, the owner's Share button) and responsive navigation. */
    width: min(52rem, 100%);
  }

  .page-header-title--research-topic {
    max-width: 42ch;
    font-family: var(--font-display);
    font-size: clamp(1.55rem, 2.3vw, 2rem);
    line-height: 1.08;
    letter-spacing: -0.025em;
    text-wrap: balance;
  }

  .page-header-title--research-topic.page-header-title--long {
    display: -webkit-box;
    max-width: 64ch;
    overflow: hidden;
    font-size: clamp(1.35rem, 1.8vw, 1.625rem);
    line-height: 1.18;
    letter-spacing: -0.018em;
    text-wrap: pretty;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    line-clamp: 3;
  }

  .page-header--research-topic .page-header-subtitle {
    max-width: 52rem;
    margin-top: 0.55rem;
    font-size: 0.9375rem;
    line-height: 1.5;
  }

  @media (max-width: 639px) {
    .page-header-title--research-topic.page-header-title--long {
      -webkit-line-clamp: 4;
      line-clamp: 4;
    }
  }
</style>
