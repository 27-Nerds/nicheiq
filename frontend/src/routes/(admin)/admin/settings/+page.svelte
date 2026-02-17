<script lang="ts">
  import { Check, AlertCircle } from "lucide-svelte";
  import { invalidateAll } from "$app/navigation";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  let { data } = $props();

  // ======= Sample Report =======
  let serverUrl = $derived(data.sampleReportUrl || "");
  let userUrl = $state<string | null>(null);
  let currentUrl = $derived(userUrl ?? serverUrl);

  let saving = $state(false);
  let clearing = $state(false);
  let feedback = $state<{ type: "success" | "error"; message: string } | null>(
    null,
  );

  async function handleSave() {
    saving = true;
    feedback = null;

    try {
      const res = await fetch("/api/admin/settings/sample_report_url", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: currentUrl }),
      });

      const result = await res.json();

      if (!res.ok) {
        feedback = {
          type: "error",
          message: result.error || "Failed to save setting",
        };
        return;
      }

      feedback = {
        type: "success",
        message: "Sample report URL saved successfully",
      };
      await invalidateAll();
      userUrl = null;
    } catch {
      feedback = { type: "error", message: "Network error" };
    } finally {
      saving = false;
    }
  }

  async function handleClear() {
    clearing = true;
    feedback = null;

    try {
      const res = await fetch("/api/admin/settings/sample_report_url", {
        method: "DELETE",
      });

      const result = await res.json();

      if (!res.ok) {
        feedback = {
          type: "error",
          message: result.error || "Failed to clear setting",
        };
        return;
      }

      feedback = { type: "success", message: "Sample report URL cleared" };
      userUrl = "";
      await invalidateAll();
    } catch {
      feedback = { type: "error", message: "Network error" };
    } finally {
      clearing = false;
    }
  }

  // ======= Token Pricing =======
  const COST_FIELDS = [
    { key: "token_cost_discovery", label: "Discovery", default: 5 },
    { key: "token_cost_deep_research", label: "Deep Research", default: 15 },
    { key: "token_cost_regenerate_ideas", label: "Generate More Ideas", default: 2 },
    { key: "token_cost_landing_page", label: "Landing Page", default: 5 },
  ] as const;

  let tokenValues = $state<Record<string, string>>({});
  let tokenSaving = $state<Record<string, boolean>>({});
  let tokenFeedback = $state<Record<string, { type: "success" | "error"; message: string } | null>>({});

  // Initialize values from server data
  $effect(() => {
    const costs = data.tokenCosts ?? {};
    for (const field of COST_FIELDS) {
      if (tokenValues[field.key] === undefined) {
        tokenValues[field.key] = costs[field.key] ?? String(field.default);
      }
    }
  });

  async function saveTokenCost(key: string) {
    tokenSaving[key] = true;
    tokenFeedback[key] = null;

    try {
      const res = await fetch(`/api/admin/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: tokenValues[key] }),
      });

      const result = await res.json();

      if (!res.ok) {
        tokenFeedback[key] = {
          type: "error",
          message: result.error || "Failed to save",
        };
        return;
      }

      tokenFeedback[key] = { type: "success", message: "Saved" };
      await invalidateAll();
    } catch {
      tokenFeedback[key] = { type: "error", message: "Network error" };
    } finally {
      tokenSaving[key] = false;
    }
  }

  async function resetTokenCost(key: string, defaultVal: number) {
    tokenSaving[key] = true;
    tokenFeedback[key] = null;

    try {
      const res = await fetch(`/api/admin/settings/${key}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const result = await res.json();
        tokenFeedback[key] = {
          type: "error",
          message: result.error || "Failed to reset",
        };
        return;
      }

      tokenValues[key] = String(defaultVal);
      tokenFeedback[key] = { type: "success", message: "Reset to default" };
      await invalidateAll();
    } catch {
      tokenFeedback[key] = { type: "error", message: "Network error" };
    } finally {
      tokenSaving[key] = false;
    }
  }
</script>

<svelte:head>
  <title>Settings | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-2xl space-y-6">
  <h2 class="text-2xl font-bold text-text-primary mb-6">Settings</h2>

  <div class="bg-bg-surface border border-border rounded-xl p-5">
    <h3 class="text-lg font-semibold text-text-primary mb-1">Sample Report</h3>
    <p class="text-sm text-text-muted mb-4">
      Configure which shared report is displayed on the public <code
        class="text-xs bg-bg-elevated px-1.5 py-0.5 rounded"
        >/sample-report</code
      > page.
    </p>

    {#if feedback}
      <div
        class="flex items-center gap-2 text-sm mb-4 p-2.5 rounded-lg {feedback.type ===
        'success'
          ? 'bg-success/10 text-success'
          : 'bg-error/10 text-error'}"
      >
        {#if feedback.type === "success"}
          <Check class="w-4 h-4 shrink-0" />
        {:else}
          <AlertCircle class="w-4 h-4 shrink-0" />
        {/if}
        {feedback.message}
      </div>
    {/if}

    <form
      onsubmit={(e) => {
        e.preventDefault();
        handleSave();
      }}
    >
      <label
        for="sample-report-url"
        class="block text-sm font-medium text-text-secondary mb-1"
      >
        Share URL
      </label>
      <input
        id="sample-report-url"
        type="text"
        value={currentUrl}
        oninput={(e) => {
          userUrl = (e.target as HTMLInputElement).value;
        }}
        placeholder="/shared/AbCdEf123..."
        class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
      />
      <p class="text-xs text-text-muted mt-1.5">
        Paste the share URL path from a completed report (e.g. <code
          class="bg-bg-elevated px-1 py-0.5 rounded">/shared/abc123</code
        >).
      </p>

      <div class="flex gap-2 mt-4">
        <SubmitButton loading={saving} loadingText="Saving..." label="Save" disabled={clearing} class="btn-primary" />
        <SubmitButton onclick={handleClear} loading={clearing} loadingText="Clearing..." label="Clear" disabled={!serverUrl || saving} type="button" class="btn-secondary" />
      </div>
    </form>
  </div>

  <!-- Token Pricing -->
  <div class="bg-bg-surface border border-border rounded-xl p-5">
    <h3 class="text-lg font-semibold text-text-primary mb-1">Token Pricing</h3>
    <p class="text-sm text-text-muted mb-4">
      Configure how many credits each stage costs. Set to 0 to make a stage free.
    </p>

    <div class="space-y-4">
      {#each COST_FIELDS as field}
        <div>
          <div class="flex items-center justify-between gap-3">
            <label
              for={field.key}
              class="text-sm font-medium text-text-secondary"
            >
              {field.label}
              <span class="text-xs text-text-muted font-normal">(default: {field.default})</span>
            </label>
            <div class="flex items-center gap-2">
              <input
                id={field.key}
                type="number"
                min="0"
                max="100"
                bind:value={tokenValues[field.key]}
                class="w-20 px-3 py-1.5 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm text-center focus:outline-none focus:border-accent"
              />
              <SubmitButton
                onclick={() => saveTokenCost(field.key)}
                loading={tokenSaving[field.key] ?? false}
                loadingText="..."
                label="Save"
                class="btn-primary btn-sm"
              />
              <SubmitButton
                onclick={() => resetTokenCost(field.key, field.default)}
                loading={tokenSaving[field.key] ?? false}
                loadingText="..."
                label="Reset"
                type="button"
                class="btn-secondary btn-sm"
              />
            </div>
          </div>
          {#if tokenFeedback[field.key]}
            <p
              class="text-xs mt-1 {tokenFeedback[field.key]?.type === 'success'
                ? 'text-success'
                : 'text-error'}"
            >
              {tokenFeedback[field.key]?.message}
            </p>
          {/if}
        </div>
      {/each}
    </div>
  </div>
</div>
