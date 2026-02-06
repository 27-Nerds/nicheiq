<script lang="ts">
  import { formatCurrency } from "$lib/utils/format";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { getTermTooltip, getTermFullName } from "$lib/stores/glossary";

  interface Props {
    tam: string;
    sam: string;
    somY1: string;
    somY3?: string;
    class?: string;
  }

  let { tam, sam, somY1, somY3, class: className = "" }: Props = $props();

  const stages = $derived([
    {
      id: "tam",
      label: "TAM",
      value: tam,
      fullName: getTermFullName("TAM"),
      tooltip: getTermTooltip("TAM"),
      width: "100%",
      delay: 0,
    },
    {
      id: "sam",
      label: "SAM",
      value: sam,
      fullName: getTermFullName("SAM"),
      tooltip: getTermTooltip("SAM"),
      width: "80%",
      delay: 100,
    },
    {
      id: "som-y1",
      label: "SOM Y1",
      value: somY1,
      fullName: "Year 1 " + getTermFullName("SOM"),
      tooltip: getTermTooltip("SOM") + " (Year 1 target)",
      width: "55%",
      delay: 200,
    },
    ...(somY3
      ? [
          {
            id: "som-y3",
            label: "SOM Y3",
            value: somY3,
            fullName: "Year 3 " + getTermFullName("SOM"),
            tooltip: getTermTooltip("SOM") + " (Year 3 projection)",
            width: "35%",
            delay: 300,
          },
        ]
      : []),
  ]);
</script>

<div class="market-funnel {className}">
  {#each stages as stage, i}
    <AnimateOnScroll animation="slide-right" delay={stage.delay}>
      <div class="funnel-stage funnel-{stage.id}" style="width: {stage.width}">
        <div class="funnel-label-group">
          <span class="funnel-label">{stage.label}</span>
          <Tooltip content={stage.tooltip} position="right" />
        </div>
        <span class="funnel-value">{formatCurrency(stage.value)}</span>
        <span class="funnel-desc">{stage.fullName}</span>
      </div>
    </AnimateOnScroll>
  {/each}
</div>

<style>
  .market-funnel {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
    max-width: 700px;
    margin: 0 auto;
  }

  .funnel-stage {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.25rem;
    border-radius: 8px;
    transition: all 0.3s var(--ease-out);
    margin-left: auto;
  }

  .funnel-stage:hover {
    transform: translateX(-4px);
  }

  .funnel-tam {
    background: linear-gradient(90deg, var(--funnel-tam), transparent);
    border-left: 4px solid var(--color-success);
  }

  .funnel-sam {
    background: linear-gradient(90deg, var(--funnel-sam), transparent);
    border-left: 4px solid var(--viz-cat-2);
  }

  .funnel-som-y1 {
    background: linear-gradient(90deg, var(--funnel-som), transparent);
    border-left: 4px solid var(--color-accent);
  }

  .funnel-som-y3 {
    background: linear-gradient(90deg, var(--funnel-target), transparent);
    border-left: 4px solid var(--viz-cat-4);
  }

  .funnel-label-group {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    min-width: 70px;
  }

  .funnel-label {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .funnel-value {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
    flex-shrink: 0;
  }

  .funnel-desc {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  @media (max-width: 640px) {
    .funnel-stage {
      flex-wrap: wrap;
      gap: 0.5rem;
      padding: 0.875rem 1rem;
    }

    .funnel-value {
      font-size: 1.125rem;
    }

    .funnel-desc {
      width: 100%;
      order: 3;
    }
  }
</style>
