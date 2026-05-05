<script lang="ts">
  import { mapVerdict } from "$lib/types/publicCatalog.js";
  import Check from "lucide-svelte/icons/check";
  import AlertCircle from "lucide-svelte/icons/alert-circle";
  import X from "lucide-svelte/icons/x";

  // Hero verdict prominence: rounded tinted box with circular icon + verdict
  // label + supporting one-liner. Replaces the small VerdictBadge chip on
  // /idea/[slug] hero. Renders nothing for unknown / null verdicts.

  interface Props {
    /** Raw `goNoGoVerdict` string from the backend (GO / NO_GO / MAYBE / etc).
     *  Will be normalized via mapVerdict. */
    verdict: string | null | undefined;
    /** One-line supporting copy. Caller is expected to pass
     *  `idea.why_it_works ?? idea.value_proposition ?? idea.short_description`. */
    note?: string | null;
  }

  let { verdict, note = null }: Props = $props();

  const mapped = $derived(mapVerdict(verdict));

  type Tone = "success" | "warn" | "error";
  const tone = $derived.by<Tone | null>(() => {
    if (mapped === "GO") return "success";
    if (mapped === "CONDITIONAL") return "warn";
    if (mapped === "NO-GO") return "error";
    return null;
  });
</script>

{#if mapped && tone}
  <aside class="vb tone-{tone}">
    <div class="v-mark">
      {#if tone === "success"}
        <Check size={18} />
      {:else if tone === "warn"}
        <AlertCircle size={18} />
      {:else}
        <X size={18} />
      {/if}
    </div>
    <div class="v-text">
      <span class="v-name">Verdict: {mapped}</span>
      {#if note}
        <span class="v-note">{note}</span>
      {/if}
    </div>
  </aside>
{/if}

<style>
  .vb {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 18px;
    border-radius: 8px;
    margin: 22px 0 0;
  }
  .vb.tone-success {
    background: var(--color-success-subtle, rgba(34, 197, 94, 0.08));
    border: 1px solid var(--color-border-success, rgba(34, 197, 94, 0.22));
  }
  .vb.tone-warn {
    background: var(--color-warning-subtle, rgba(245, 158, 11, 0.08));
    border: 1px solid var(--color-border-warning, rgba(245, 158, 11, 0.22));
  }
  .vb.tone-error {
    background: var(--color-error-subtle, rgba(239, 68, 68, 0.08));
    border: 1px solid var(--color-border-error, rgba(239, 68, 68, 0.22));
  }
  .v-mark {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    color: #fff;
    display: grid;
    place-items: center;
    flex-shrink: 0;
  }
  .tone-success .v-mark {
    background: var(--color-success-dark, #16a34a);
  }
  .tone-warn .v-mark {
    background: var(--color-warning-dark, #b45309);
  }
  .tone-error .v-mark {
    background: var(--color-error-dark, #dc2626);
  }
  .v-text {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
    flex: 1;
  }
  .v-name {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-family: var(--font-mono);
  }
  .tone-success .v-name {
    color: var(--color-success-dark, #16a34a);
  }
  .tone-warn .v-name {
    color: var(--color-warning-dark, #b45309);
  }
  .tone-error .v-name {
    color: var(--color-error-dark, #dc2626);
  }
  .v-note {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    margin-top: 2px;
  }
</style>
