<script lang="ts">
  import Bookmark from "lucide-svelte/icons/bookmark";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";

  interface Props {
    itemType: "idea" | "painPoint";
    itemId: string;
    /** Path to return to after successful registration. Encoded inline. */
    returnTo: string;
    /** Optional: visual variant. "ghost" matches IdeaHeroV2's btn-cta-ghost
     *  exactly; "compact" is a smaller version for use in card-grid contexts. */
    variant?: "ghost" | "compact";
  }

  let { itemType, itemId, returnTo, variant = "ghost" }: Props = $props();

  // Three states: null = unknown (still fetching), true = saved, false = not.
  // Anonymous visitors stay at null forever (we never fetch for them).
  let saved = $state<boolean | null>(null);
  let pending = $state(false);

  const session = $derived(page.data.session);
  const isAuthed = $derived(Boolean(session?.user));

  const apiBase = $derived(itemType === "idea" ? "/api/saves/ideas" : "/api/saves/pain-points");

  // On mount, fetch the saved-state from the authenticated status endpoint.
  // Skipped for anonymous visitors — the button renders in its neutral
  // "Save" state and clicks redirect to /register.
  $effect(() => {
    if (!isAuthed) {
      saved = null;
      return;
    }
    const ctrl = new AbortController();
    fetch(`${apiBase}/status?ids=${encodeURIComponent(itemId)}`, {
      signal: ctrl.signal,
      credentials: "same-origin",
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && itemId in data) saved = Boolean(data[itemId]);
      })
      .catch(() => {
        // Network error — leave `saved` null so the button is usable but
        // optimistic toggle starts from a neutral state.
      });
    return () => ctrl.abort();
  });

  async function toggle() {
    if (!isAuthed) {
      const target = `/register?ref=save&returnTo=${encodeURIComponent(returnTo)}`;
      goto(target);
      return;
    }
    if (pending) return;

    const wasSaved = saved === true;
    // Optimistic flip.
    saved = !wasSaved;
    pending = true;

    try {
      let res: Response;
      if (wasSaved) {
        res = await fetch(`${apiBase}/${itemId}`, {
          method: "DELETE",
          credentials: "same-origin",
        });
      } else {
        const bodyKey = itemType === "idea" ? "ideaId" : "painPointId";
        res = await fetch(apiBase, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ [bodyKey]: itemId }),
        });
      }
      if (!res.ok) throw new Error(`Save failed: ${res.status}`);
    } catch {
      // Revert on error. The user sees a brief flash and the original state.
      saved = wasSaved;
    } finally {
      pending = false;
    }
  }

  const label = $derived(saved === true ? "Saved" : "Save");
  const ariaLabel = $derived(
    itemType === "idea"
      ? saved === true
        ? "Remove this idea from saved"
        : "Save this idea"
      : saved === true
        ? "Remove this pain point from saved"
        : "Save this pain point",
  );
</script>

<button
  class="save-btn"
  class:save-btn-ghost={variant === "ghost"}
  class:save-btn-compact={variant === "compact"}
  class:is-saved={saved === true}
  class:is-pending={pending}
  type="button"
  aria-label={ariaLabel}
  aria-pressed={saved === true}
  onclick={toggle}
  disabled={pending}
>
  <Bookmark
    size={variant === "ghost" ? 14 : 12}
    fill={saved === true ? "currentColor" : "none"}
  />
  <span>{label}</span>
</button>

<style>
  .save-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition:
      color 140ms ease,
      border-color 140ms ease,
      background 140ms ease;
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-bg-elevated, #fff);
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .save-btn:disabled {
    cursor: progress;
    opacity: 0.7;
  }
  /* Ghost variant — matches IdeaHeroV2's btn-cta-ghost exactly so the button
     slots into the existing hero CTA cluster without visual disruption. */
  .save-btn-ghost {
    padding: 13px 18px;
    font-size: 14px;
  }
  /* Compact variant — for in-card use later (e.g. saved-page card footers,
     hover-save on category landing pages). Currently unused; reserved. */
  .save-btn-compact {
    padding: 6px 10px;
    font-size: 12px;
  }
  .save-btn:hover:not(:disabled) {
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
    background: var(--color-bg-base, #fafafa);
  }
  .save-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  /* Saved state — bookmark filled + accent text + accent border. The 1px
     accent ring keeps the visual weight similar to the unsaved ghost button
     so the CTA cluster doesn't reflow. */
  .save-btn.is-saved {
    color: var(--color-accent);
    border-color: var(--color-border-accent);
    background: rgba(234, 88, 12, 0.04);
  }
  .save-btn.is-saved:hover:not(:disabled) {
    color: var(--color-accent-hover, var(--color-accent-dark));
    border-color: var(--color-accent);
    background: rgba(234, 88, 12, 0.08);
  }
</style>
