<script lang="ts">
  import { page } from "$app/state";
  import { AlertTriangle } from "lucide-svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";

  const status = $derived(page.status);
  const message = $derived(
    page.error?.message ?? "Something went wrong on our end.",
  );
  const description = $derived(
    status === 404
      ? "The page you're looking for doesn't exist or has moved. Head back to your dashboard to keep going."
      : "An unexpected error interrupted this request. Try again, or reach out if it keeps happening.",
  );
</script>

<div class="max-w-2xl mx-auto py-16 px-4 text-center">
  <p
    class="text-xs font-mono uppercase tracking-[0.08em] text-text-muted mb-4"
  >
    Error {status}
  </p>
  <EmptyState
    icon={AlertTriangle}
    title={message}
    {description}
    variant="warning"
    size="lg"
  />
  <div class="mt-8 flex flex-wrap justify-center gap-3">
    <Button
      href="/dashboard"
      label="Back to Dashboard"
      class="btn-primary"
    />
    <Button
      href="mailto:hello@nicheiq.dev"
      label="Contact Support"
      class="btn-secondary"
    />
  </div>
</div>
