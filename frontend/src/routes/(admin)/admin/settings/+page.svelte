<script lang="ts">
  import { Check, AlertCircle } from "lucide-svelte";
  import { invalidateAll } from "$app/navigation";

  let { data } = $props();

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
</script>

<svelte:head>
  <title>Settings | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-2xl">
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
        <button type="submit" class="btn-primary" disabled={saving || clearing}>
          {saving ? "Saving..." : "Save"}
        </button>
        <button
          type="button"
          class="btn-secondary"
          disabled={!serverUrl || saving || clearing}
          onclick={handleClear}
        >
          {clearing ? "Clearing..." : "Clear"}
        </button>
      </div>
    </form>
  </div>
</div>
