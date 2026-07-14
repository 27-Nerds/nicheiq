<script lang="ts">
  import ChatThread from "./ChatThread.svelte";
  import { chatLedger } from "$lib/stores/chatLedger.svelte";

  interface Props {
    jobId: string;
    compact?: boolean;
  }

  let { jobId, compact = false }: Props = $props();

  $effect(() => {
    void chatLedger.init(jobId).then(() => chatLedger.reload());
  });

  const starters = [
    "What is the strongest reason to pursue this idea?",
    "What are the biggest risks in this report?",
    "Compare the winner with the strongest alternative.",
    "Export the key findings as Markdown.",
  ];
</script>

<section class="completed-analyst" class:compact aria-label="Completed report analyst">
  <header>
    <div>
      <p>Report analyst</p>
      <h2>Ask about any finding</h2>
    </div>
    <span>Read-only report</span>
  </header>
  <p class="intro">
    I can explain the evidence, compare the researched options, help you decide what to do next,
    or prepare a Markdown, CSV, or JSON export. Completed research cannot be changed.
  </p>
  <ChatThread {jobId} dock="main" gateStage={6} {starters} />
</section>

<style>
  .completed-analyst {
    width: min(62rem, calc(100% - 2rem));
    margin: 2rem auto 4rem;
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: 0.875rem;
    background: var(--color-bg-surface);
  }
  .completed-analyst.compact { width: 100%; margin: 1.5rem 0 0; }
  header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding: 1rem 1.1rem 0; }
  header p { margin: 0 0 0.2rem; color: var(--color-text-muted); font-family: var(--font-mono); font-size: 0.625rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
  header h2 { margin: 0; color: var(--color-text-primary); font-size: 1rem; }
  header span { padding: 0.28rem 0.5rem; border: 1px solid var(--color-border); border-radius: 999px; color: var(--color-text-muted); font-size: 0.6875rem; white-space: nowrap; }
  .intro { max-width: 72ch; margin: 0.75rem 1.1rem 0; color: var(--color-text-secondary); font-size: 0.8125rem; line-height: 1.55; }
  .completed-analyst :global(.chat) { border: 0; border-radius: 0; }
  @media (max-width: 640px) { header { align-items: stretch; flex-direction: column; } header span { width: fit-content; } }
</style>
