<script lang="ts">
  // Platform-icon + count chip used in the "Source signal" section of the
  // idea/pain-point detail pages. Platform string drives the tone/icon.

  interface Props {
    /** Platform name — case-insensitive. Known: reddit, twitter, x, discord,
     *  hackernews, indiehackers, generic. Falls back to neutral. */
    platform?: string;
    /** Display label (e.g. "r/ecommerce"). */
    label: string;
    /** Optional count; rendered after a separator dot. */
    count?: number | null;
  }

  let { platform = "generic", label, count = null }: Props = $props();

  const tone = $derived.by(() => {
    const p = (platform ?? "").toLowerCase();
    if (p === "reddit") return "reddit";
    if (p === "twitter" || p === "x") return "twitter";
    if (p === "discord") return "discord";
    if (p === "hackernews" || p === "hn") return "hn";
    return "generic";
  });
</script>

<span class="src-chip tone-{tone}">
  <span class="label">{label}</span>
  {#if count != null}
    <span class="num">·&nbsp;{count.toLocaleString()}</span>
  {/if}
</span>

<style>
  .src-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 7px 11px;
    border-radius: 6px;
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    font-size: 11.5px;
    color: var(--color-text-secondary, var(--color-text-primary));
    font-family: var(--font-mono);
  }
  .num {
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .tone-reddit .label {
    color: var(--color-accent);
  }
  .tone-twitter .label {
    color: var(--color-info);
  }
  .tone-discord .label {
    color: var(--color-info);
  }
  .tone-hn .label {
    color: var(--color-accent);
  }
</style>
