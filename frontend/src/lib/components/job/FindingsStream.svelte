<script lang="ts">
  import {
    Flame,
    Globe,
    Users,
    Lightbulb,
    TrendingUp,
    BarChart3,
    Flag,
    ChevronDown,
  } from "lucide-svelte";
  import type { FindingItem, FindingType } from "$lib/types/stageArtifacts";

  interface Props {
    items: FindingItem[];
    class?: string;
    collapsed?: boolean;
    onToggleCollapse?: () => void;
  }

  let {
    items,
    class: className = "",
    collapsed = false,
    onToggleCollapse,
  }: Props = $props();

  let expandedIds = $state<Set<string>>(new Set());

  function toggleExpanded(id: string) {
    const next = new Set(expandedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    expandedIds = next;
  }

  const iconMap: Record<FindingType, typeof Flame> = {
    pain_point: Flame,
    community: Globe,
    audience: Users,
    solution: Lightbulb,
    keyword: TrendingUp,
    market: BarChart3,
    milestone: Flag,
  };

  const colorMap: Record<FindingType, string> = {
    pain_point: 'finding-pain',
    community: 'finding-community',
    audience: 'finding-audience',
    solution: 'finding-solution',
    keyword: 'finding-keyword',
    market: 'finding-market',
    milestone: 'finding-milestone',
  };

  const labelMap: Record<FindingType, string> = {
    pain_point: 'Pain Point',
    community: 'Community',
    audience: 'Audience',
    solution: 'Solution',
    keyword: 'Keyword',
    market: 'Market',
    milestone: 'Milestone',
  };
</script>

<div class="findings-stream {className}">
  <button class="stream-header" onclick={onToggleCollapse}>
    <div class="header-left">
      <span class="header-title">Live Findings</span>
      {#if items.length > 0}
        <span class="count-badge">{items.length}</span>
      {/if}
    </div>
    {#if onToggleCollapse}
      <ChevronDown class="collapse-chevron {collapsed ? '' : 'expanded'}" />
    {/if}
  </button>

  {#if !collapsed}
    <div class="stream-body">
      {#if items.length === 0}
        <div class="empty-state">
          <p>Discoveries will appear here as the AI works...</p>
        </div>
      {:else}
        <div class="findings-list">
          {#each items as item (item.id)}
            {@const Icon = iconMap[item.type]}
            {@const colorClass = colorMap[item.type]}
            <div class="finding-card {colorClass}" style="animation-delay: {items.indexOf(item) * 80}ms">
              {#if item.expandable}
                <button
                  class="finding-main finding-main-btn"
                  onclick={() => toggleExpanded(item.id)}
                >
                  <span class="finding-icon">
                    <Icon class="finding-icon-svg" />
                  </span>
                  <div class="finding-content">
                    <span class="finding-title">{item.title}</span>
                    {#if item.detail}
                      <span class="finding-detail">{item.detail}</span>
                    {/if}
                  </div>
                  {#if item.value}
                    <span class="finding-value">{item.value}</span>
                  {/if}
                </button>
              {:else}
                <div class="finding-main">
                  <span class="finding-icon">
                    <Icon class="finding-icon-svg" />
                  </span>
                  <div class="finding-content">
                    <span class="finding-title">{item.title}</span>
                    {#if item.detail}
                      <span class="finding-detail">{item.detail}</span>
                    {/if}
                  </div>
                  {#if item.value}
                    <span class="finding-value">{item.value}</span>
                  {/if}
                </div>
              {/if}
              {#if item.expandable && expandedIds.has(item.id) && item.expandedContent}
                <div class="finding-expanded">
                  <p>{item.expandedContent}</p>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .findings-stream {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    overflow: hidden;
  }

  .stream-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 0.875rem 1rem;
    border-bottom: 1px solid var(--color-border);
    background: transparent;
    border-top: none;
    border-left: none;
    border-right: none;
    cursor: pointer;
  }

  .stream-header:hover {
    background: var(--color-bg-surface);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .header-title {
    font-family: var(--font-display);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .count-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.25rem;
    height: 1.25rem;
    padding: 0 0.375rem;
    border-radius: 999px;
    background: var(--color-accent);
    color: white;
    font-size: 0.6875rem;
    font-weight: 600;
    font-family: var(--font-mono);
  }

  :global(.collapse-chevron) {
    width: 1rem;
    height: 1rem;
    color: var(--color-text-muted);
    transition: transform 0.2s ease;
  }

  :global(.collapse-chevron.expanded) {
    transform: rotate(180deg);
  }

  .stream-body {
    max-height: 600px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--color-border) transparent;
  }

  .empty-state {
    padding: 2rem 1rem;
    text-align: center;
  }

  .empty-state p {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    font-style: italic;
  }

  .findings-list {
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .finding-card {
    border-radius: 0.5rem;
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-border);
    background: var(--color-bg-surface);
    overflow: hidden;
    animation: slide-in-right 300ms ease-out both;
  }

  @keyframes slide-in-right {
    0% {
      opacity: 0;
      transform: translateX(20px);
    }
    100% {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .finding-card {
      animation: none;
    }
  }

  /* Color variants via left border */
  .finding-pain { border-left-color: #f87171; }
  .finding-community { border-left-color: #60a5fa; }
  .finding-audience { border-left-color: #a78bfa; }
  .finding-solution { border-left-color: #fb923c; }
  .finding-keyword { border-left-color: #34d399; }
  .finding-market { border-left-color: #2dd4bf; }
  .finding-milestone { border-left-color: var(--color-accent); }

  .finding-main {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.625rem 0.75rem;
  }

  .finding-main-btn {
    cursor: pointer;
    width: 100%;
    border: none;
    background: transparent;
    text-align: left;
    font: inherit;
  }

  .finding-main-btn:hover {
    background: rgba(255, 255, 255, 0.02);
  }

  .finding-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 0.0625rem;
  }

  :global(.finding-icon-svg) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-text-muted);
  }

  /* Color icons to match their type */
  .finding-pain :global(.finding-icon-svg) { color: #f87171; }
  .finding-community :global(.finding-icon-svg) { color: #60a5fa; }
  .finding-audience :global(.finding-icon-svg) { color: #a78bfa; }
  .finding-solution :global(.finding-icon-svg) { color: #fb923c; }
  .finding-keyword :global(.finding-icon-svg) { color: #34d399; }
  .finding-market :global(.finding-icon-svg) { color: #2dd4bf; }
  .finding-milestone :global(.finding-icon-svg) { color: var(--color-accent); }

  .finding-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    min-width: 0;
  }

  .finding-title {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-primary);
    line-height: 1.3;
  }

  .finding-detail {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    line-height: 1.3;
  }

  .finding-value {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    flex-shrink: 0;
    white-space: nowrap;
  }

  .finding-expanded {
    padding: 0 0.75rem 0.625rem 2.125rem;
    border-top: 1px solid var(--color-border);
    animation: expand-in 200ms ease-out;
  }

  @keyframes expand-in {
    0% { opacity: 0; max-height: 0; }
    100% { opacity: 1; max-height: 200px; }
  }

  .finding-expanded p {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0.5rem 0 0;
  }
</style>
