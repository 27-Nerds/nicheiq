<script lang="ts">
  interface FeedbackGroup {
    key: string;
    solutionName: string;
    comments: string[];
    linked: boolean;
  }

  interface Props {
    groups: FeedbackGroup[];
    onOpen: (key: string) => void;
    onAskAnalyst: () => void;
  }

  let { groups, onOpen, onAskAnalyst }: Props = $props();

  const rationaleCount = $derived(
    groups.reduce((total, group) => total + group.comments.length, 0),
  );

  // Local in-flight guard: onAskAnalyst is a fire-and-forget callback (no
  // promise to await), so a short lock is the only way to stop a double click
  // from opening the analyst prompt twice.
  let synthesizing = $state(false);
  function handleAskAnalyst() {
    if (synthesizing) return;
    synthesizing = true;
    onAskAnalyst();
    setTimeout(() => {
      synthesizing = false;
    }, 600);
  }
</script>

<details class="feedback collaborator-feedback" data-annotation-anchor="collaborator-feedback">
  <summary>
    <span>
      <strong>Collaborator feedback</strong>
      <small>Anonymous preference input, not market evidence</small>
    </span>
    <b aria-label={`${rationaleCount} rationale${rationaleCount === 1 ? "" : "s"}`}>{rationaleCount}</b>
  </summary>
  <div class="body">
    <div class="toolbar">
      <p>{rationaleCount} rationale{rationaleCount === 1 ? "" : "s"} from shared-report voting.</p>
      <button type="button" disabled={synthesizing} onclick={handleAskAnalyst}>Ask analyst to synthesize</button>
    </div>
    <div class="groups">
      {#each groups as group (group.key)}
        <article class="group">
          <header>
            {#if group.linked}
              <h4><button type="button" onclick={() => onOpen(group.key)}>
                {group.solutionName}
              </button></h4>
            {:else}
              <h4>{group.solutionName}</h4>
              <span>Previous or ambiguous candidate</span>
            {/if}
          </header>
          <ul>
            {#each group.comments as comment}
              <li><blockquote>{comment}</blockquote></li>
            {/each}
          </ul>
        </article>
      {/each}
    </div>
  </div>
</details>

<style>
  .feedback {
    margin: 0.65rem 0 1rem;
    border-block: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-accent) 3%, var(--color-bg-surface));
  }
  .feedback > summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    min-height: 3.5rem;
    padding: 0.7rem 0.8rem;
    cursor: pointer;
    list-style: none;
    transition: background-color var(--duration-fast) var(--ease-default);
  }
  .feedback > summary::-webkit-details-marker { display: none; }
  .feedback > summary:hover {
    background: color-mix(in srgb, var(--color-accent) 4%, transparent);
  }
  .feedback > summary:active {
    transform: scale(0.98);
  }
  .feedback > summary > span {
    display: grid;
    gap: 0.12rem;
    min-width: 0;
  }
  .feedback > summary strong {
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-weight: 700;
  }
  .feedback > summary small {
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
  }
  .feedback > summary b {
    display: inline-grid;
    min-width: 1.75rem;
    min-height: 1.75rem;
    place-items: center;
    border-radius: 999px;
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }
  .feedback > summary:focus-visible,
  .feedback button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .body {
    display: grid;
    gap: 0.9rem;
    padding: 0.85rem 0.8rem 1rem;
    border-top: 1px solid var(--color-border);
  }
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .toolbar p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.72rem;
  }
  .toolbar button,
  .group header button {
    min-height: 1.5rem;
    padding: 0.2rem 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font-size: 0.72rem;
    font-weight: 700;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .toolbar button:hover,
  .group header button:hover { color: var(--color-accent-hover); }
  .toolbar button:active:not(:disabled),
  .group header button:active { transform: scale(0.98); }
  .toolbar button:disabled { cursor: wait; color: var(--color-text-muted); }
  .groups {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr));
    gap: 1rem 1.4rem;
  }
  .group {
    min-width: 0;
    padding-left: 0.75rem;
    border-left: 2px solid var(--color-border);
  }
  .group header {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.3rem 0.55rem;
  }
  .group header button,
  .group header h4 {
    margin: 0;
    padding: 0;
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-weight: 700;
    text-align: left;
  }
  .group header span {
    color: var(--color-text-secondary);
    font-size: 0.7rem;
  }
  .group ul {
    display: grid;
    gap: 0.5rem;
    margin: 0.55rem 0 0;
    padding: 0;
    list-style: none;
  }
  .group blockquote {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    line-height: 1.5;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }
  @media (max-width: 640px) {
    .feedback > summary { align-items: flex-start; gap: 0.65rem; }
    .body { padding-inline: 0.65rem; }
    .toolbar { align-items: stretch; flex-direction: column; }
    .toolbar button { min-height: 2.5rem; text-align: left; }
    .group header { align-items: flex-start; }
    .group header button { flex: 1 1 12rem; }
  }
  @media (prefers-reduced-motion: reduce) {
    .feedback > summary,
    .toolbar button,
    .group header button {
      transition: none;
    }
    .feedback > summary:active,
    .toolbar button:active:not(:disabled),
    .group header button:active {
      transform: none;
    }
  }
</style>
