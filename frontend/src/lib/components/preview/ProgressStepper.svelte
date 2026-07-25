<script lang="ts">
  type StepState = 'done' | 'active' | 'pending';

  interface Props {
    currentStep: 'discovery' | 'selection' | 'deep_research';
    discussionCount?: number;
    painPointCount?: number;
    solutionCount?: number;
  }

  let {
    currentStep,
    discussionCount = 0,
    painPointCount = 0,
    solutionCount = 0,
  }: Props = $props();

  const steps = $derived([
    {
      id: 'discovery',
      label: 'Discovery',
      state: (currentStep === 'discovery' ? 'active'
        : 'done') as StepState,
      stat: discussionCount > 0 ? `${discussionCount.toLocaleString()} discussions` : undefined,
    },
    {
      id: 'selection',
      label: 'Selection',
      state: (currentStep === 'discovery' ? 'pending'
        : currentStep === 'selection' ? 'active'
        : 'done') as StepState,
      stat: painPointCount > 0 ? `${painPointCount} pain points` : undefined,
    },
    {
      id: 'deep_research',
      label: 'Deep Research',
      state: (currentStep === 'deep_research' ? 'active' : 'pending') as StepState,
      stat: solutionCount > 0 ? `${solutionCount} opportunities` : undefined,
    },
  ]);
</script>

<div class="stepper-panel">
  <div class="stepper">
    {#each steps as step, i}
      {#if i > 0}
        <div class="step-line" class:step-line--done={step.state === 'done' || step.state === 'active'}></div>
      {/if}
      <div class="step">
        <div class="step-dot step-dot--{step.state}">
          {#if step.state === 'done'}
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          {:else}
            <span class="step-num">{i + 1}</span>
          {/if}
        </div>
        <span class="step-label step-label--{step.state}">{step.label}</span>
      </div>
    {/each}
  </div>

  {#if steps.some(s => s.stat)}
    <div class="stepper-stats">
      {#each steps as step}
        {#if step.stat}
          <div class="stepper-stat">
            <span class="stepper-stat-dot stepper-stat-dot--{step.state}"></span>
            <span class="stepper-stat-text">{step.stat}</span>
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .stepper-panel {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 1.25rem;
    margin-bottom: 1rem;
  }

  .stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    margin-bottom: 1rem;
  }

  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.375rem;
  }

  .step-dot {
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-sm);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    transition: background-color 300ms ease, border-color 300ms ease, color 300ms ease;
  }

  .step-dot--done {
    background: var(--color-accent);
    color: var(--color-text-on-accent);
  }

  .step-dot--active {
    background: transparent;
    border: 2px solid var(--color-accent);
    color: var(--color-accent);
  }

  .step-dot--pending {
    background: var(--color-bg-surface);
    border: 1.5px solid var(--color-border);
    color: var(--color-text-muted);
  }

  .step-num {
    font-size: var(--text-11);
  }

  .step-line {
    width: 5rem;
    height: 2px;
    background: var(--color-border);
    margin-bottom: 1.25rem;
    transition: background-color 300ms ease;
  }

  .step-line--done {
    background: var(--color-accent);
  }

  .step-label {
    font-family: var(--font-display);
    font-size: var(--text-11);
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  .step-label--done {
    color: var(--color-accent);
  }

  .step-label--active {
    color: var(--color-text-secondary);
  }

  .step-label--pending {
    color: var(--color-text-muted);
  }

  .stepper-stats {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    justify-content: center;
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border);
  }

  .stepper-stat {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: var(--text-13);
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  .stepper-stat-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
  }

  .stepper-stat-dot--done {
    background: var(--color-accent);
  }

  .stepper-stat-dot--active {
    background: var(--color-text-secondary);
  }

  .stepper-stat-dot--pending {
    background: var(--color-border);
  }

  .stepper-stat-text {
    font-weight: 500;
    color: var(--color-text-primary);
  }

  @media (max-width: 480px) {
    .step-line {
      width: 2.5rem;
    }

    .stepper-stats {
      flex-direction: column;
      gap: 0.5rem;
    }
  }
</style>
