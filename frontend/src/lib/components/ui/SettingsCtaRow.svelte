<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import SubmitButton from "./SubmitButton.svelte";
  import type { CtaIconName } from "$lib/types/cta";

  interface Props {
    key: string;
    label: string;
    defaultText: string;
    defaultUrl: string;
    defaultIcon?: CtaIconName;
    placeholder?: string;
    value: string | null;
  }

  let {
    key,
    label,
    defaultText,
    defaultUrl,
    defaultIcon = "none",
    placeholder = "",
    value,
  }: Props = $props();

  let textValue = $state("");
  let urlValue = $state("");
  let visible = $state(true);
  let iconValue = $state<CtaIconName>("none");
  let saving = $state(false);
  let feedback = $state<{ type: "success" | "error"; message: string } | null>(null);

  $effect(() => {
    if (value) {
      try {
        const parsed = JSON.parse(value);
        textValue = parsed.text ?? defaultText;
        urlValue = parsed.url ?? defaultUrl;
        visible = parsed.visible ?? true;
        iconValue = parsed.icon ?? defaultIcon;
      } catch {
        textValue = defaultText;
        urlValue = defaultUrl;
        visible = true;
        iconValue = defaultIcon;
      }
    } else {
      textValue = defaultText;
      urlValue = defaultUrl;
      visible = true;
      iconValue = defaultIcon;
    }
  });

  let charCount = $derived(textValue.length);

  const iconOptions: { value: CtaIconName; label: string }[] = [
    { value: "none", label: "None" },
    { value: "arrow-right", label: "Arrow Right" },
    { value: "scroll-text", label: "Scroll Text" },
    { value: "file-text", label: "File Text" },
    { value: "sparkles", label: "Sparkles" },
    { value: "external-link", label: "External Link" },
  ];

  async function save() {
    saving = true;
    feedback = null;

    try {
      const res = await fetch(`/api/admin/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          value: JSON.stringify({ text: textValue, visible, url: urlValue, icon: iconValue }),
        }),
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

      textValue = defaultText;
      urlValue = defaultUrl;
      visible = true;
      iconValue = defaultIcon;
      feedback = { type: "success", message: "Reset to default" };
      await invalidateAll();
    } catch {
      feedback = { type: "error", message: "Network error" };
    } finally {
      saving = false;
    }
  }
</script>

<div class="space-y-2">
  <div class="flex items-center justify-between gap-3">
    <label for="{key}-text" class="text-sm font-medium text-text-secondary">
      {label}
    </label>
    <div class="flex items-center gap-2">
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

  <div class="flex flex-col sm:flex-row gap-2">
    <!-- Text input -->
    <div class="flex-1">
      <div class="flex items-center gap-2">
        <input
          id="{key}-text"
          type="text"
          maxlength={60}
          bind:value={textValue}
          placeholder={placeholder || defaultText}
          class="w-full px-3 py-1.5 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
        />
        <span class="text-xs text-text-muted whitespace-nowrap">{charCount}/60</span>
      </div>
    </div>

    <!-- URL input -->
    <div class="w-full sm:w-40">
      <input
        id="{key}-url"
        type="text"
        bind:value={urlValue}
        placeholder={defaultUrl}
        class="w-full px-3 py-1.5 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
      />
    </div>

    <!-- Icon dropdown -->
    <div class="w-full sm:w-36">
      <select
        id="{key}-icon"
        bind:value={iconValue}
        class="w-full px-3 py-1.5 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
      >
        {#each iconOptions as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
      </select>
    </div>

    <!-- Visibility toggle -->
    <label class="flex items-center gap-1.5 cursor-pointer whitespace-nowrap">
      <input
        type="checkbox"
        bind:checked={visible}
        class="w-4 h-4 rounded border-border text-accent focus:ring-accent"
      />
      <span class="text-xs text-text-muted">Visible</span>
    </label>
  </div>

  <p class="text-xs text-text-muted">
    Default: "{defaultText}" &rarr; {defaultUrl}
  </p>

  {#if feedback}
    <p class="text-xs {feedback.type === 'success' ? 'text-success' : 'text-error'}">
      {feedback.message}
    </p>
  {/if}
</div>
