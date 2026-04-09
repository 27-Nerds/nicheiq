<script lang="ts">
  import { ChevronDown, Coins } from "lucide-svelte";
  import Badge from "./Badge.svelte";
  import type { ComponentType, Snippet } from "svelte";

  type SectionVariant = "default" | "success" | "warning" | "accent";
  type BorderStyle = "all" | "left" | "top" | "none";
  type HeaderSize = "sm" | "md" | "lg";
  type SpacingSize = "none" | "sm" | "md" | "lg" | "container";

  interface Props {
    // Header config
    title: string;
    subtitle?: string;
    icon?: ComponentType;

    // Count badge
    count?: number | null;
    countSuffix?: string;

    // Credit cost badge (shown in expandable header)
    creditCost?: number;

    // Section mode
    mode?: "static" | "expandable";
    defaultOpen?: boolean;

    // Visual styling
    variant?: SectionVariant;
    border?: BorderStyle;
    headerSize?: HeaderSize;
    elevated?: boolean;

    // Spacing
    padding?: SpacingSize;
    marginBottom?: SpacingSize;

    // Callbacks
    onToggle?: (expanded: boolean) => void;

    // Reset key: increment to force-reset user toggle state (e.g., on major status transitions)
    resetKey?: number | string;

    // Other
    id?: string;
    class?: string;

    // Snippets
    heroStrip?: Snippet;
    children: Snippet;
  }

  let {
    title,
    subtitle,
    icon: Icon,
    count = null,
    countSuffix,
    creditCost,
    mode = "static",
    defaultOpen = false,
    variant = "default",
    border = "all",
    headerSize = "md",
    elevated = true,
    padding = "md",
    marginBottom = "md",
    onToggle,
    resetKey,
    id,
    class: className = "",
    heroStrip,
    children,
  }: Props = $props();

  let expanded = $state<boolean>(false);
  let userHasToggled = $state(false);
  let prevDefaultOpen: boolean | undefined = undefined;
  let prevResetKey: number | string | undefined = undefined;

  // Reset user toggle state when resetKey changes (major status transitions)
  $effect(() => {
    if (resetKey !== undefined && prevResetKey !== resetKey) {
      prevResetKey = resetKey;
      userHasToggled = false;
    }
  });

  // Sync expanded from defaultOpen only when the prop changes AND user hasn't manually toggled
  $effect(() => {
    if (prevDefaultOpen !== defaultOpen) {
      prevDefaultOpen = defaultOpen;
      if (!userHasToggled) {
        expanded = defaultOpen;
      }
    }
  });

  function handleToggle() {
    expanded = !expanded;
    userHasToggled = true;
    onToggle?.(expanded);
  }

  const isExpandable = $derived(mode === "expandable");
  const showBody = $derived(!isExpandable || expanded);

  // Badge variant mapping
  const badgeVariants: Record<
    SectionVariant,
    "muted" | "success" | "warning" | "accent"
  > = {
    default: "muted",
    success: "success",
    warning: "warning",
    accent: "accent",
  };
</script>

<section
  class="section-container section-{variant} border-{border} padding-{padding} mb-{marginBottom} header-{headerSize} {className}"
  class:elevated
  class:expandable={isExpandable}
  {id}
>
  {#if isExpandable}
    <!-- Expandable header (clickable) -->
    <button
      class="section-header-row expandable-trigger"
      onclick={handleToggle}
      aria-expanded={expanded}
    >
      <div class="header-content">
        {#if Icon}
          <Icon class="section-icon" />
        {/if}
        <span class="section-header-title">{title}</span>
        {#if count != null}
          <Badge variant={badgeVariants[variant]} size="sm"
            >{count}{#if countSuffix}&nbsp;{countSuffix}{/if}</Badge
          >
        {/if}
        {#if creditCost && creditCost > 0}
          <span class="credit-cost-badge" aria-label="{creditCost} credits">
            <Coins class="credit-cost-icon" />{creditCost}
          </span>
        {/if}
      </div>
      <ChevronDown class="chevron-icon {expanded ? 'expanded' : ''}" />
    </button>

    <!-- Always-mounted body with CSS grid transition for smooth expand/collapse -->
    <div
      class="section-body"
      class:section-body--open={showBody}
      aria-hidden={!showBody}
      inert={!showBody ? true : undefined}
    >
      <div class="section-body-inner">
        {#if heroStrip}
          <div class="hero-strip-container">
            {@render heroStrip()}
          </div>
        {/if}
        <div class="section-content">
          {@render children()}
        </div>
      </div>
    </div>
  {:else if headerSize === "lg"}
    <!-- Large static header (SectionHeader style) -->
    <div class="section-header-row header-lg">
      <div class="header-icon-box">
        {#if Icon}
          <Icon class="section-icon-lg" />
        {/if}
      </div>
      <div class="header-text">
        <h2 class="section-header-title-lg">{title}</h2>
        {#if subtitle}
          <p class="section-header-subtitle">{subtitle}</p>
        {/if}
      </div>
      {#if count != null}
        <Badge variant={badgeVariants[variant]} size="sm"
          >{count}{#if countSuffix}&nbsp;{countSuffix}{/if}</Badge
        >
      {/if}
    </div>
    {#if heroStrip}
      <div class="hero-strip-container">
        {@render heroStrip()}
      </div>
    {/if}
    <div class="section-content">
      {@render children()}
    </div>
  {:else}
    <!-- Medium/Small static header (SubsectionHeader style) -->
    <div class="section-header-row header-inline">
      {#if Icon}
        <Icon class="section-icon" />
      {/if}
      <span class="section-header-title">{title}</span>
      {#if count != null}
        <Badge variant={badgeVariants[variant]} size="sm"
          >{count}{#if countSuffix}&nbsp;{countSuffix}{/if}</Badge
        >
      {/if}
    </div>
    {#if heroStrip}
      <div class="hero-strip-container">
        {@render heroStrip()}
      </div>
    {/if}
    <div class="section-content">
      {@render children()}
    </div>
  {/if}
</section>

<style>
  /* ============================================
	   Base Section Container
	   ============================================ */
  .section-container {
    border-radius: 0.75rem;
    overflow: hidden;
  }

  .section-container.elevated {
    background: var(--color-bg-elevated);
  }

  /* ============================================
	   Variant Styles (Simplified: 4 variants)
	   ============================================ */
  .section-default {
    --section-border-color: var(--color-border);
    --section-icon-color: var(--color-accent);
    --section-bg: transparent;
  }

  .section-success {
    --section-border-color: rgba(34, 197, 94, 0.3);
    --section-icon-color: var(--color-success);
    --section-bg: linear-gradient(
      135deg,
      rgba(34, 197, 94, 0.05) 0%,
      transparent 40%
    );
  }

  .section-warning {
    --section-border-color: rgba(239, 68, 68, 0.3);
    --section-icon-color: var(--color-error);
    --section-bg: linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.05) 0%,
      transparent 40%
    );
  }

  .section-accent {
    --section-border-color: var(--color-border-accent);
    --section-icon-color: var(--color-accent);
    --section-bg: linear-gradient(
      135deg,
      var(--color-accent-subtle) 0%,
      transparent 40%
    );
  }

  /* Apply variant background */
  .section-success,
  .section-warning,
  .section-accent {
    background: var(--section-bg);
  }

  /* ============================================
	   Border Styles
	   ============================================ */
  .border-all {
    border: 1px solid var(--section-border-color);
  }

  .border-left {
    border: 1px solid var(--section-border-color);
    border-left: 3px solid var(--section-border-color);
  }

  .border-top {
    border: 1px solid var(--section-border-color);
    border-top: 3px solid var(--section-border-color);
  }

  .border-none {
    border: none;
  }

  /* ============================================
	   Padding Styles
	   ============================================ */
  .padding-none > .section-content {
    padding: 0;
  }

  .padding-sm > .section-content {
    padding: 0.75rem;
  }

  .padding-md > .section-content {
    padding: 1rem 1.25rem 1.25rem;
  }

  .padding-lg > .section-content {
    padding: 1.5rem;
  }

  .padding-container {
    padding: 1.5rem;
  }

  .padding-container > .section-content {
    padding: 0;
  }

  .padding-container > .header-lg {
    padding: 0;
    margin-bottom: 1.5rem;
  }

  .padding-container > .header-inline {
    padding: 0;
    margin-bottom: 0.75rem;
  }

  .padding-container > .hero-strip-container {
    padding: 0;
    margin-bottom: 0.75rem;
  }

  @media (max-width: 768px) {
    .padding-container {
      padding: 1rem;
    }
  }

  /* ============================================
	   Expandable Body (CSS grid transition)
	   ============================================ */
  .section-body {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 220ms ease-out;
    overflow: hidden;
  }

  .section-body--open {
    grid-template-rows: 1fr;
  }

  .section-body-inner {
    overflow: hidden;
  }

  /* Expandable sections: inherit horizontal padding from variant.
     The > .section-content rules above don't match expandable mode
     because .section-content is nested inside .section-body > .section-body-inner. */
  .padding-sm .section-body .section-content {
    padding: 0.5rem 0.75rem 0.75rem;
  }

  .padding-md .section-body .section-content {
    padding: 0.5rem 1.25rem 1.25rem;
  }

  .padding-lg .section-body .section-content {
    padding: 0.5rem 1.5rem 1.5rem;
  }

  /* ============================================
	   Margin Bottom
	   ============================================ */
  .mb-none {
    margin-bottom: 0;
  }

  .mb-sm {
    margin-bottom: 0.5rem;
  }

  .mb-md {
    margin-bottom: 1rem;
  }

  .mb-lg {
    margin-bottom: 1.5rem;
  }

  /* ============================================
	   Header Styles
	   ============================================ */
  .section-header-row {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }

  /* Expandable trigger button */
  .expandable-trigger {
    justify-content: space-between;
    width: 100%;
    padding: 1rem 1.25rem;
    background: transparent;
    border: none;
    border-radius: 0.5rem;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .expandable-trigger:hover {
    background: var(--color-bg-surface);
  }

  .header-content {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }

  /* Inline header (md/sm static) */
  .header-inline {
    padding: 1rem 1.25rem 0;
  }

  /* Large header (lg static) — scoped to header row only */
  .section-header-row.header-lg {
    gap: 1rem;
    padding: 1.25rem 1.25rem 0;
    align-items: flex-start;
  }

  .header-icon-box {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.75rem;
    height: 2.75rem;
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: 0.75rem;
    flex-shrink: 0;
  }

  .header-text {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
  }

  /* ============================================
	   Title Styles
	   ============================================ */
  .section-header-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .section-header-title-lg {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
    margin: 0;
  }

  .section-header-subtitle {
    font-size: 0.9375rem;
    color: var(--color-text-muted);
    margin: 0;
  }

  /* ============================================
	   Icon Styles
	   ============================================ */
  :global(.section-icon) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--section-icon-color);
    flex-shrink: 0;
  }

  :global(.section-icon-lg) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent);
  }

  /* ============================================
	   Chevron (Expandable)
	   ============================================ */
  :global(.chevron-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-text-muted);
    transition: transform 0.2s ease-in-out;
  }

  :global(.chevron-icon.expanded) {
    transform: rotate(180deg);
  }

  /* ============================================
	   Hero Strip
	   ============================================ */
  .hero-strip-container {
    padding: 1rem 1.25rem 0;
  }

  .section-body .hero-strip-container {
    padding-top: 0;
  }

  /* ============================================
	   Credit Cost Badge
	   ============================================ */
  .credit-cost-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    opacity: 0.7;
  }

  :global(.credit-cost-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }
</style>
