<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import SubmitButton from "./SubmitButton.svelte";

  interface Props {
    key: string;
    label: string;
    defaultValue: number;
    min?: number;
    max?: number;
    value: string | null;
  }

  let {
    key,
    label,
    defaultValue,
    min = 0,
    max = 100,
    value,
  }: Props = $props();

  let inputValue = $state("");
  let saving = $state(false);
  let feedback = $state<{ type: "success" | "error"; message: string } | null>(null);

  // Sync input from server data (value prop) when it changes
  $effect(() => {
    inputValue = value ?? String(defaultValue);
  });

  async function save() {
    saving = true;
    feedback = null;

    try {
      const res = await fetch(`/api/admin/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: inputValue }),
      });

      const result = await res.json();

      if (!res.ok) {
        feedback = { type: "error", message: result.error || "Failed to save" };
        return;
      }

      feedback = { type: "success", message: "Saved" };
      await invalidateAll();
    } catch {
      feedback = { type: "error", message: "Network error" };
    } finally {
      saving = false;
    }
  }

  async function reset() {
    saving = true;
    feedback = null;

    try {
      const res = await fetch(`/api/admin/settings/${key}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const result = await res.json();
        feedback = { type: "error", message: result.error || "Failed to reset" };
        return;
      }

      inputValue = String(defaultValue);
      feedback = { type: "success", message: "Reset to default" };
      await invalidateAll();
    } catch {
      feedback = { type: "error", message: "Network error" };
    } finally {
      saving = false;
    }
  }
</script>

<div>
  <div class="flex items-center justify-between gap-3">
    <label for={key} class="text-sm font-medium text-text-secondary">
      {label}
      <span class="text-xs text-text-muted font-normal">(default: {defaultValue})</span>
    </label>
    <div class="flex items-center gap-2">
      <input
        id={key}
        type="number"
        {min}
        {max}
        bind:value={inputValue}
        class="w-20 px-3 py-1.5 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm text-center focus:outline-none focus:border-accent"
      />
      <SubmitButton
        onclick={save}
        loading={saving}
        loadingText="..."
        label="Save"
        class="btn-primary btn-sm"
      />
      <SubmitButton
        onclick={reset}
        loading={saving}
        loadingText="..."
        label="Reset"
        type="button"
        class="btn-secondary btn-sm"
      />
    </div>
  </div>
  {#if feedback}
    <p class="text-xs mt-1 {feedback.type === 'success' ? 'text-success' : 'text-error'}">
      {feedback.message}
    </p>
  {/if}
</div>
