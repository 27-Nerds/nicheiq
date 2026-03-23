<script lang="ts">
  import Section from "$lib/components/ui/Section.svelte";
  import type { Snippet } from "svelte";
  import type { PhaseStatus } from "./phaseConfig";
  import type { ComponentType } from "svelte";

  type SectionVariant = "default" | "success" | "warning" | "accent";

  interface Props {
    title: string;
    status: PhaseStatus;
    stagesCompleted: number;
    stagesTotal: number;
    defaultOpen?: boolean;
    icon?: ComponentType;
    creditCost?: number;
    heroStrip?: Snippet;
    children: Snippet;
  }

  let {
    title,
    status,
    stagesCompleted,
    stagesTotal,
    defaultOpen = false,
    icon,
    creditCost,
    heroStrip,
    children,
  }: Props = $props();

  const variant = $derived<SectionVariant>(
    status === 'active' ? 'accent'
    : status === 'completed' ? 'success'
    : status === 'failed' ? 'warning'
    : 'default'
  );

  const isLocked = $derived(status === 'locked');

  const sectionOpen = $derived(
    status === 'active' ? true
    : status === 'completed' ? false
    : status === 'preview' ? true
    : defaultOpen
  );

  const countDisplay = $derived(
    `${stagesCompleted}/${stagesTotal}`
  );
</script>

<div class="phase-section" class:locked={isLocked}>
  <Section
    {title}
    mode="expandable"
    defaultOpen={sectionOpen}
    {variant}
    border="none"
    {icon}
    count={stagesCompleted > 0 ? stagesCompleted : null}
    countSuffix="/ {stagesTotal}"
    {creditCost}
    {heroStrip}
  >
    {@render children()}
  </Section>
</div>

<style>
  .phase-section {
    margin-bottom: 0.75rem;
  }

  .phase-section.locked {
    opacity: 0.5;
    pointer-events: none;
  }
</style>
