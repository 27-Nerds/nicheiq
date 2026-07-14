<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import { AlertCircle, Check } from "lucide-svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  interface ModelOption {
    id: string;
    pricing: {
      input: number;
      output: number;
      cacheWrite?: number;
      cacheRead?: number;
    };
  }

  interface Setting {
    value: string | null;
    effectiveValue: string;
    defaultValue: string;
    options: ModelOption[];
  }

  interface Props {
    setting: Setting | null;
  }

  let { setting }: Props = $props();
  let override = $state<string | null>(null);
  let saving = $state(false);
  let feedback = $state<{ type: "success" | "error"; message: string } | null>(null);

  const selected = $derived(override ?? setting?.value ?? "__default__");
  const effective = $derived(
    selected === "__default__" ? (setting?.defaultValue ?? "gpt-5-mini") : selected,
  );

  async function save() {
    if (!setting || saving) return;
    saving = true;
    feedback = null;
    try {
      const reset = selected === "__default__";
      const response = await fetch("/api/admin/settings/analyst_chat_model", {
        method: reset ? "DELETE" : "PUT",
        headers: reset ? undefined : { "Content-Type": "application/json" },
        body: reset ? undefined : JSON.stringify({ value: selected }),
      });
      const result = await response.json();
      if (!response.ok) {
        feedback = { type: "error", message: result.error || "Failed to update analyst model" };
        return;
      }
      feedback = {
        type: "success",
        message: reset ? "Analyst model reset to the deployment default" : `Analyst model changed to ${selected}`,
      };
      await invalidateAll();
      override = null;
    } catch {
      feedback = { type: "error", message: "Network error" };
    } finally {
      saving = false;
    }
  }
</script>

<div class="bg-bg-surface border border-border rounded-xl p-5">
  <h3 class="text-lg font-semibold text-text-primary mb-1">Analyst Model</h3>
  <p class="text-sm text-text-muted mb-4">
    Controls report chat, follow-up suggestions, and post-mutation commentary. New operations use
    the change immediately; an in-progress response keeps the model it started with.
  </p>

  {#if !setting}
    <p class="text-sm text-error">Model settings could not be loaded.</p>
  {:else}
    {#if feedback}
      <div class="model-feedback {feedback.type}" role="status">
        {#if feedback.type === "success"}<Check class="w-4 h-4" />{:else}<AlertCircle class="w-4 h-4" />{/if}
        <span>{feedback.message}</span>
      </div>
    {/if}

    <label for="analyst-model" class="block text-sm font-medium text-text-secondary mb-1">
      Model for new analyst operations
    </label>
    <select
      id="analyst-model"
      value={selected}
      onchange={(event) => (override = (event.currentTarget as HTMLSelectElement).value)}
      class="model-select"
    >
      <option value="__default__">Use deployment default ({setting.defaultValue})</option>
      {#each setting.options as option}
        <option value={option.id}>{option.id}</option>
      {/each}
    </select>
    <p class="text-xs text-text-muted mt-1.5">Effective model: <strong>{effective}</strong></p>

    <div class="pricing-table" role="table" aria-label="Analyst model prices per one million tokens">
      <div class="pricing-row pricing-head" role="row">
        <span>Model</span><span>Input</span><span>Output</span><span>Cache write</span><span>Cache read</span>
      </div>
      {#each setting.options as option}
        <div class="pricing-row" class:is-effective={option.id === effective} role="row">
          <strong>{option.id}</strong>
          <span>${option.pricing.input.toFixed(2)}</span>
          <span>${option.pricing.output.toFixed(2)}</span>
          <span>{option.pricing.cacheWrite == null ? "—" : `$${option.pricing.cacheWrite.toFixed(2)}`}</span>
          <span>{option.pricing.cacheRead == null ? "—" : `$${option.pricing.cacheRead.toFixed(2)}`}</span>
        </div>
      {/each}
    </div>

    <SubmitButton onclick={save} loading={saving} loadingText="Saving..." label="Save model" class="btn-primary mt-4" />
  {/if}
</div>

<style>
  .model-feedback { display: flex; align-items: center; gap: 0.5rem; padding: 0.65rem; margin-bottom: 1rem; border-radius: 0.5rem; font-size: 0.8125rem; }
  .model-feedback.success { color: var(--color-success); background: color-mix(in srgb, var(--color-success) 10%, transparent); }
  .model-feedback.error { color: var(--color-error); background: color-mix(in srgb, var(--color-error) 10%, transparent); }
  .model-select { width: 100%; padding: 0.6rem 0.75rem; color: var(--color-text-primary); background: var(--color-bg-elevated); border: 1px solid var(--color-input-border); border-radius: 0.5rem; }
  .model-select:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .pricing-table { margin-top: 1rem; overflow-x: auto; border: 1px solid var(--color-border); border-radius: 0.5rem; }
  .pricing-row { display: grid; grid-template-columns: minmax(8rem, 1.4fr) repeat(4, minmax(5.5rem, 1fr)); min-width: 34rem; }
  .pricing-row > * { padding: 0.55rem 0.65rem; border-top: 1px solid var(--color-border); font-size: 0.75rem; }
  .pricing-row > * + * { border-left: 1px solid var(--color-border); }
  .pricing-head > * { border-top: 0; color: var(--color-text-muted); font-weight: 700; }
  .pricing-row.is-effective { background: color-mix(in srgb, var(--color-accent) 6%, transparent); }
</style>
