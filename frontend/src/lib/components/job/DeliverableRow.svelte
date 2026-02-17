<script lang="ts">
  import type { ComponentType } from "svelte";
  import {
    ExternalLink,
    Loader2,
    Minus,
    RotateCw,
  } from "lucide-svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  interface Props {
    label: string;
    icon?: ComponentType;
    status: 'locked' | 'pending' | 'running' | 'completed' | 'failed';
    creditCost?: number;
    canAfford?: boolean;
    asset?: { url: string } | null;
    generating?: boolean;
    error?: string;
    onGenerate: () => Promise<void>;
  }

  let {
    label,
    icon: Icon,
    status,
    creditCost = 0,
    canAfford = true,
    asset = null,
    generating = false,
    error: errorMsg = "",
    onGenerate,
  }: Props = $props();

  let confirmPending = $state(false);
</script>

<div
  class="stage-row-lp"
  class:is-completed={status === 'completed'}
  class:is-running={status === 'running'}
  class:is-failed={status === 'failed'}
>
  <!-- Dot -->
  <div class="dot-lp"
    class:dot-completed={status === 'completed'}
    class:dot-running={status === 'running'}
    class:dot-failed={status === 'failed'}
    class:dot-locked={status === 'locked'}
    class:dot-pending={status === 'pending'}
  >
    {#if status === 'locked'}
      <Minus class="dot-icon dot-icon-muted" />
    {/if}
  </div>

  <!-- Label -->
  <span class="stage-name-lp"
    class:text-primary={status === 'completed'}
    class:text-info={status === 'running'}
    class:text-secondary={status !== 'completed' && status !== 'running'}
  >{label}</span>

  <!-- Actions -->
  <div class="lp-actions">
    {#if status === 'completed' && asset}
      <a href={asset.url} target="_blank" rel="noopener noreferrer" class="lp-link">
        <ExternalLink class="lp-link-icon" />
        View
      </a>
      <a href="{asset.url}?download=true" class="lp-link" download>
        Download
      </a>
    {:else if status === 'running' || generating}
      <span class="lp-generating">
        <Loader2 class="lp-spinner" />
        Generating...
      </span>
    {:else if status === 'failed'}
      <SubmitButton onclick={onGenerate} loading={generating} loadingText="Retrying..." icon={RotateCw} label="Retry" class="btn-secondary btn-sm" />
    {:else if status === 'pending'}
      {#if confirmPending}
        <div class="lp-confirm-inline">
          <span class="text-xs text-text-secondary">{creditCost} credits &mdash; confirm?</span>
          <button onclick={async () => { confirmPending = false; await onGenerate(); }} class="btn-primary btn-sm">Generate</button>
          <button onclick={() => { confirmPending = false; }} class="btn-secondary btn-sm">Cancel</button>
        </div>
      {:else}
        <SubmitButton onclick={() => { confirmPending = true; }} loading={generating} loadingText="Generating..." icon={Icon} label="Generate" class="btn-secondary btn-sm" />
        {#if creditCost > 0}
          <span class="text-xs text-text-muted opacity-70">{creditCost} credits</span>
        {/if}
        {#if !canAfford && creditCost > 0}
          <span class="text-xs text-warning">Requires {creditCost} credits. <a href="/billing" class="underline hover:text-warning/80">Add credits &rarr;</a></span>
        {/if}
      {/if}
    {:else if status === 'locked'}
      <span class="lp-locked">Available after analysis</span>
    {/if}
  </div>
</div>
{#if errorMsg}
  <p class="lp-error">{errorMsg}</p>
{/if}

<style>
  .stage-row-lp {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    padding: 0.5rem 0.25rem;
    position: relative;
    border-radius: 0.375rem;
    transition: background 0.15s ease;
  }

  .stage-row-lp.is-running {
    background: rgba(59, 130, 246, 0.04);
  }

  .dot-lp {
    width: 0.75rem;
    height: 0.75rem;
    margin-top: 0.1875rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    flex-shrink: 0;
    position: relative;
    z-index: 1;
  }

  .dot-lp.dot-completed {
    background: rgba(34, 197, 94, 0.45);
    border: 1px solid rgba(34, 197, 94, 0.55);
  }
  .dot-lp.dot-running {
    background: rgba(59, 130, 246, 0.45);
    border: 1px solid rgba(59, 130, 246, 0.55);
  }
  .dot-lp.dot-failed {
    background: rgba(239, 68, 68, 0.45);
    border: 1px solid rgba(239, 68, 68, 0.55);
  }
  .dot-lp.dot-locked {
    width: 0.875rem;
    height: 0.875rem;
    margin-top: 0.125rem;
    margin-left: -0.0625rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
  }
  .dot-lp.dot-pending {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
  }

  .stage-name-lp {
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.3;
  }

  .text-info { color: var(--color-info); }
  .text-primary { color: var(--color-text-primary); }
  .text-secondary { color: var(--color-text-secondary); }

  .lp-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-shrink: 0;
  }

  .lp-confirm-inline {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .lp-link {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-accent);
    text-decoration: none;
    transition: opacity 0.15s ease;
  }
  .lp-link:hover {
    opacity: 0.8;
  }

  :global(.lp-link-icon) {
    width: 0.75rem;
    height: 0.75rem;
  }

  .lp-generating {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-info);
  }

  :global(.lp-spinner) {
    width: 0.875rem;
    height: 0.875rem;
    animation: spin 1s linear infinite;
  }

  .lp-locked {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .lp-error {
    margin-top: 0.25rem;
    margin-left: calc(1.375rem + 0.625rem + 0.25rem);
    font-size: 0.8125rem;
    color: var(--color-error);
  }
</style>
