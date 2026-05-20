<script lang="ts">
  import { page } from "$app/state";
  import { AlertTriangle } from "lucide-svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";

  const status = $derived(page.status);
  const message = $derived(
    page.error?.message ?? "We hit a snag loading this page.",
  );
  const description = $derived(
    status === 404
      ? "That page isn't here. Maybe it moved — try the homepage or browse what's new in the catalog."
      : "Something went wrong on our side. Try again in a moment, or send us a note.",
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
    <Button href="/" label="Back to Home" class="btn-primary" />
    <Button
      href="mailto:hello@nicheiq.dev"
      label="Contact Support"
      class="btn-secondary"
    />
  </div>
</div>
