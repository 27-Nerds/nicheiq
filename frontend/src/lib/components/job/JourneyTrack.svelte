<script lang="ts">
  import { Check } from "lucide-svelte";
  import type { PhaseStatus } from "./phaseConfig";

  interface PhaseNode {
    id: string;
    label: string;
    status: PhaseStatus;
  }

  interface Props {
    phases: PhaseNode[];
    gateStatus?: 'locked' | 'active' | 'passed';
    isInteractive?: boolean;
    currentStageName?: string;
    progressPercent?: number;
    stagesCompleted?: number;
    totalStages?: number;
    isRunning?: boolean;
    isFailed?: boolean;
    painPointCount?: number;
  }

  let {
    phases,
    gateStatus = 'locked',
    isInteractive = false,
    currentStageName,
    progressPercent = 0,
    stagesCompleted = 0,
    totalStages = 0,
    isRunning = false,
    isFailed = false,
    painPointCount,
  }: Props = $props();

  const painPointsCompleted = $derived(painPointCount != null && painPointCount > 0);
</script>

<div class="journey-track">
  <div class="track-nodes">
    {#each phases as phase, i}
      <!-- Phase node -->
      <div class="node-group">
        <div
          class="node"
          class:node-completed={phase.status === 'completed'}
          class:node-active={phase.status === 'active'}
          class:node-failed={phase.status === 'failed'}
          class:node-pending={phase.status === 'pending' || phase.status === 'locked' || phase.status === 'preview'}
        >
          {#if phase.status === 'completed'}
            <Check class="node-check" />
          {:else if phase.status === 'active'}
            <span class="node-pulse"></span>
          {:else}
            <span class="node-dot"></span>
          {/if}
        </div>
        <span
          class="node-label"
          class:label-active={phase.status === 'active'}
          class:label-completed={phase.status === 'completed'}
        >
          {phase.label}
        </span>
      </div>

      <!-- Connector line (between nodes) -->
      {#if i < phases.length - 1}
        <!-- Milestones + gate for interactive jobs between discovery and analysis -->
        {#if isInteractive && i === 0}
          <!-- Line from Discovery to Pain Points milestone -->
          <div class="connector-segment connector-segment--short">
            <div class="track-line" class:line-filled={painPointsCompleted}></div>
          </div>

          <!-- Pain Points milestone -->
          <div class="node-group">
            <div
              class="milestone-node"
              class:milestone-completed={painPointsCompleted}
              class:milestone-pending={!painPointsCompleted}
            >
              {#if painPointsCompleted}
                <Check class="milestone-check" />
              {:else}
                <span class="milestone-dot"></span>
              {/if}
            </div>
            <span
              class="milestone-label"
              class:label-completed={painPointsCompleted}
            >
              Pain Points{#if painPointsCompleted && painPointCount}&nbsp;({painPointCount}){/if}
            </span>
          </div>

          <!-- Line from Pain Points to Ideas gate -->
          <div class="connector-segment connector-segment--short">
            <div class="track-line" class:line-filled={gateStatus === 'active' || gateStatus === 'passed'}></div>
          </div>

          <!-- Ideas gate (= diamond) -->
          <div class="node-group">
            <div
              class="gate-diamond"
              class:diamond-active={gateStatus === 'active'}
              class:diamond-passed={gateStatus === 'passed'}
            >
              <span class="diamond-inner"></span>
            </div>
            <span
              class="milestone-label"
              class:label-active={gateStatus === 'active'}
              class:label-completed={gateStatus === 'passed'}
            >
              Ideas
            </span>
          </div>

          <!-- Line from Ideas to Analysis -->
          <div class="connector-segment connector-segment--short">
            <div class="track-line" class:line-filled={gateStatus === 'passed'}></div>
          </div>
        {:else if i === 0}
          <!-- Non-interactive: Pain Points milestone only (no Ideas gate) -->
          <div class="connector-segment connector-segment--short">
            <div class="track-line" class:line-filled={painPointsCompleted}></div>
          </div>
          <div class="node-group">
            <div
              class="milestone-node"
              class:milestone-completed={painPointsCompleted}
              class:milestone-pending={!painPointsCompleted}
            >
              {#if painPointsCompleted}
                <Check class="milestone-check" />
              {:else}
                <span class="milestone-dot"></span>
              {/if}
            </div>
            <span
              class="milestone-label"
              class:label-completed={painPointsCompleted}
            >
              Pain Points{#if painPointsCompleted && painPointCount}&nbsp;({painPointCount}){/if}
            </span>
          </div>
          <div class="connector-segment connector-segment--short">
            <div class="track-line" class:line-filled={phases[i].status === 'completed'}></div>
          </div>
        {:else}
          <div class="connector-segment">
            <div class="track-line" class:line-filled={phases[i].status === 'completed'}></div>
          </div>
        {/if}
      {/if}
    {/each}

    <!-- Connector to Done node -->
    <div class="connector-segment">
      <div class="track-line" class:line-filled={phases[phases.length - 1]?.status === 'completed'}></div>
    </div>

    <!-- Done node -->
    <div class="node-group">
      <div
        class="node"
        class:node-completed={phases.every((p) => p.status === 'completed')}
        class:node-pending={!phases.every((p) => p.status === 'completed')}
      >
        {#if phases.every((p) => p.status === 'completed')}
          <Check class="node-check" />
        {:else}
          <span class="node-dot"></span>
        {/if}
      </div>
      <span
        class="node-label"
        class:label-completed={phases.every((p) => p.status === 'completed')}
      >
        Done
      </span>
    </div>
  </div>

</div>

<style>
  .journey-track {
    padding: 1rem 0;
  }

  .track-nodes {
    display: flex;
    align-items: flex-start;
    justify-content: center;
    gap: 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .node-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .node {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
    position: relative;
  }

  .node-completed {
    background: rgba(34, 197, 94, 0.15);
    border: 2px solid rgba(34, 197, 94, 0.4);
  }

  .node-active {
    background: rgba(229, 90, 40, 0.15);
    border: 2px solid rgba(229, 90, 40, 0.4);
  }

  .node-active::after {
    content: '';
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    border: 2px solid rgba(229, 90, 40, 0.3);
    animation: ring-expand 2.5s ease-out infinite;
  }

  .node-failed {
    background: rgba(239, 68, 68, 0.15);
    border: 2px solid rgba(239, 68, 68, 0.4);
  }

  .node-pending {
    background: var(--color-bg-elevated);
    border: 2px solid var(--color-border);
  }

  :global(.node-check) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-success);
  }

  .node-pulse {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--color-accent);
  }

  .node-dot {
    width: 0.375rem;
    height: 0.375rem;
    border-radius: 50%;
    background: var(--color-text-muted);
    opacity: 0.5;
  }

  .node-label {
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }

  .label-active {
    color: var(--color-accent);
    font-weight: 600;
  }

  .label-completed {
    color: var(--color-success);
  }

  .connector-segment {
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 2rem;
    max-width: 8rem;
    height: 2rem;
    gap: 0;
  }

  .track-line {
    flex: 1;
    height: 2px;
    background: var(--color-border);
    transition: background 1s ease-out;
  }

  .line-filled {
    background: rgba(34, 197, 94, 0.4);
  }

  .gate-diamond {
    width: 1.25rem;
    height: 1.25rem;
    transform: rotate(45deg);
    border: 2px solid var(--color-border);
    background: var(--color-bg-elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.3s ease;
  }

  .diamond-active {
    border-color: rgba(229, 90, 40, 0.4);
    background: rgba(229, 90, 40, 0.1);
  }

  .diamond-passed {
    border-color: rgba(34, 197, 94, 0.4);
    background: rgba(34, 197, 94, 0.1);
  }

  .diamond-inner {
    width: 0.25rem;
    height: 0.25rem;
    border-radius: 50%;
    background: var(--color-text-muted);
    transform: rotate(-45deg);
  }

  .diamond-active .diamond-inner {
    background: var(--color-accent);
  }

  .diamond-passed .diamond-inner {
    background: var(--color-success);
  }

  /* ===== Milestone nodes (smaller, subordinate to phase nodes) ===== */
  .milestone-node {
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
  }

  .milestone-completed {
    background: rgba(34, 197, 94, 0.15);
    border: 1.5px solid rgba(34, 197, 94, 0.4);
  }

  .milestone-pending {
    background: var(--color-bg-elevated);
    border: 1.5px solid var(--color-border);
  }

  :global(.milestone-check) {
    width: 0.625rem;
    height: 0.625rem;
    color: var(--color-success);
  }

  .milestone-dot {
    width: 0.25rem;
    height: 0.25rem;
    border-radius: 50%;
    background: var(--color-text-muted);
    opacity: 0.4;
  }

  .milestone-label {
    font-size: 0.5625rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .connector-segment--short {
    min-width: 1rem;
    max-width: 4rem;
  }

  /* The gate diamond also needs a label now — vertically offset to align */
  .node-group > .gate-diamond {
    margin-top: 0.125rem;
  }

  @keyframes pulse-glow {
    0%, 100% { box-shadow: none; }
    50% { box-shadow: none; }
  }

  @keyframes ring-expand {
    0% { inset: -4px; opacity: 0.6; }
    70% { inset: -10px; opacity: 0; }
    100% { inset: -10px; opacity: 0; }
  }

  @media (max-width: 480px) {
    .milestone-label {
      display: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .node-active {
      animation: none;

    }
    .node-active::after {
      animation: none;
      display: none;
    }
  }
</style>
