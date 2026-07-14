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

  const colorMap: Record<IconColor, { bg: string; border: string; text: string }> = {
    accent: { bg: "bg-accent/10", border: "border-accent/20", text: "text-accent" },
    secondary: { bg: "bg-secondary/10", border: "border-secondary/20", text: "text-secondary" },
    warning: { bg: "bg-warning/10", border: "border-warning/20", text: "text-warning" },
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
    <div class="page-header-title-row flex items-start gap-3">
      {#if Icon && colors}
        <div class="p-2 rounded-xl {colors.bg} border {colors.border} shrink-0">
          <Icon class="w-6 h-6 {colors.text}" />
        </div>
      {/if}
      <div>
        <h1
          class="page-header-title text-2xl font-bold text-text-primary flex items-center gap-3 text-balance"
          class:page-header-title--research-topic={isResearchTopic}
          class:page-header-title--long={isLongResearchTopic}
          title={isLongResearchTopic ? title : undefined}
        >
          {title}
          {#if badge}{@render badge()}{/if}
        </h1>
        {#if subtitle}
          <p class="page-header-subtitle text-text-muted mt-1 text-pretty">{subtitle}</p>
        {/if}
        {#if metadata}
          <div class="mt-2">
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
  .page-header--research-topic {
    margin-bottom: 0;
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
