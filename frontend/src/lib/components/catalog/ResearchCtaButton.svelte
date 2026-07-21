<script lang="ts">
  import { page } from "$app/state";
  import { goto } from "$app/navigation";
  import { Sparkles } from "lucide-svelte";
  import ResearchConfirmModal from "./ResearchConfirmModal.svelte";

  type Kind = "pain" | "idea";

  let {
    kind,
    slug,
    label,
    subject,
  }: { kind: Kind; slug: string; label: string; subject: string } = $props();

  let confirmOpen = $state(false);
  let loading = $state(false);
  let error = $state("");
  // Balance can be overridden by a 402 (stale page.data) so the modal morphs to insufficient.
  let balanceOverride = $state<number | null>(null);

  const session = $derived(page.data.session);
  const stageName = $derived(kind === "idea" ? "deep_research" : "discovery");
  const modalKind = $derived(kind === "idea" ? "deep_idea" : "pain");
  const cost = $derived(
    page.data.stageCosts?.[stageName] ?? (kind === "idea" ? 15 : 5),
  );
  const balance = $derived(balanceOverride ?? page.data.creditBalance ?? 0);

  function openConfirm() {
    // Anonymous → register, returning to this exact page afterwards.
    if (!session?.user) {
      const returnTo = encodeURIComponent(page.url.pathname);
      goto(`/register?ref=catalog&returnTo=${returnTo}`);
      return;
    }
    balanceOverride = null;
    error = "";
    confirmOpen = true;
  }

  async function startResearch() {
    if (loading) return;
    loading = true;
    error = "";
    try {
      const url =
        kind === "idea"
          ? `/api/catalog/ideas/${slug}/deep-research`
          : `/api/catalog/pain-research`;
      const body = kind === "idea" ? undefined : JSON.stringify({ painSlugs: [slug] });

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        ...(body ? { body } : {}),
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        goto(`/jobs/${data.id}`, { invalidateAll: true });
        return;
      }
      // Normalized error contract (switch on status + code, never message strings).
      switch (res.status) {
        case 401: {
          const returnTo = encodeURIComponent(page.url.pathname);
          goto(`/register?ref=catalog&returnTo=${returnTo}`);
          return;
        }
        case 402:
          // Stale balance — flip the modal to its insufficient state.
          balanceOverride = data.balance ?? Math.max(0, cost - 1);
          error = "";
          break;
        case 403:
          error = "This item is no longer available to research.";
          break;
        case 404:
          // Deleted from the catalog — retrying can't succeed.
          error = "This item was removed from the catalog.";
          break;
        case 400:
          error = data.error || "That request wasn't valid.";
          break;
        default:
          error = "Something went wrong — please try again.";
      }
    } catch {
      error = "Something went wrong — please try again.";
    } finally {
      loading = false;
    }
  }
</script>

<button type="button" class="research-cta" onclick={openConfirm}>
  <Sparkles size={14} />
  <span>{label}</span>
</button>

<ResearchConfirmModal
  bind:open={confirmOpen}
  kind={modalKind}
  {subject}
  {cost}
  {balance}
  {loading}
  {error}
  onConfirm={startResearch}
/>

<style>
  .research-cta {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 18px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    border: 1px solid transparent;
    cursor: pointer;
    background: var(--color-accent);
    color: var(--color-surface);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.18),
      0 1px 2px rgba(154, 52, 18, 0.18),
      0 6px 14px rgba(154, 52, 18, 0.1);
    transition: background-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
    white-space: nowrap;
  }
  .research-cta:hover {
    background: var(--color-accent-hover, var(--color-accent-dark));
  }
  .research-cta:active {
    transform: scale(0.98);
  }
  .research-cta:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>
