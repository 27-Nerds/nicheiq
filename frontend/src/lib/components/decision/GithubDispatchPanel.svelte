<script lang="ts">
  import { onMount } from "svelte";
  import {
    AlertTriangle,
    CheckCircle2,
    ExternalLink,
    Github,
    Loader2,
    RefreshCw,
  } from "lucide-svelte";
  import {
    dispatchGithubHandoffIssue,
    getGithubConnections,
    getGithubHandoffDispatch,
    getGithubRepositories,
    previewGithubHandoffIssue,
    reconcileGithubHandoffDispatch,
  } from "$lib/api";
  import FormField from "$lib/components/ui/FormField.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import type {
    GithubConnection,
    GithubHandoffDispatch,
    GithubIssuePreview,
    GithubRepository,
  } from "$lib/types/githubIntegration";

  interface Props {
    jobId: string;
  }

  let { jobId }: Props = $props();

  let enabled = $state(true);
  let connections = $state<GithubConnection[]>([]);
  let repositories = $state<GithubRepository[]>([]);
  let selectedConnectionId = $state("");
  let selectedRepositoryId = $state("");
  let preview = $state<GithubIssuePreview | null>(null);
  let dispatch = $state<GithubHandoffDispatch | null>(null);
  let loading = $state(true);
  let loadingRepositories = $state(false);
  let previewing = $state(false);
  let dispatching = $state(false);
  let reconciling = $state(false);
  let error = $state("");
  let reconciliationMessage = $state("");
  let resultHeading = $state<HTMLHeadingElement>();
  let repositorySequence = 0;

  const selectedConnection = $derived(
    connections.find((connection) => connection.id === selectedConnectionId) ?? null,
  );
  const selectedRepository = $derived(
    repositories.find((repository) => repository.id === selectedRepositoryId) ?? null,
  );

  function focusResult(): void {
    requestAnimationFrame(() => {
      resultHeading?.focus();
      const reduced = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      resultHeading?.scrollIntoView?.({
        behavior: reduced ? "auto" : "smooth",
        block: "nearest",
      });
    });
  }

  async function loadRepositories(connectionId: string): Promise<void> {
    const sequence = ++repositorySequence;
    repositories = [];
    selectedRepositoryId = "";
    preview = null;
    if (!connectionId) return;
    loadingRepositories = true;
    error = "";
    try {
      const result = await getGithubRepositories(connectionId);
      if (sequence !== repositorySequence) return;
      repositories = result;
      selectedRepositoryId = result.find((repository) => repository.hasIssues)?.id ?? "";
    } catch (cause) {
      if (sequence === repositorySequence) {
        error = cause instanceof Error ? cause.message : "Could not load GitHub repositories.";
      }
    } finally {
      if (sequence === repositorySequence) loadingRepositories = false;
    }
  }

  async function loadDispatch(): Promise<void> {
    error = "";
    try {
      dispatch = await getGithubHandoffDispatch(jobId);
      if (dispatch) focusResult();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not load the GitHub receipt.";
    }
  }

  async function load(): Promise<void> {
    loading = true;
    error = "";
    const [connectionResult, dispatchResult] = await Promise.allSettled([
      getGithubConnections(),
      getGithubHandoffDispatch(jobId),
    ]);
    if (dispatchResult.status === "fulfilled") {
      dispatch = dispatchResult.value;
    } else {
      error = dispatchResult.reason instanceof Error
        ? dispatchResult.reason.message
        : "Could not load the GitHub receipt.";
    }
    if (connectionResult.status === "fulfilled") {
      enabled = connectionResult.value.enabled;
      connections = connectionResult.value.connections;
      selectedConnectionId = connections[0]?.id ?? "";
      if (!dispatch && selectedConnectionId) {
        await loadRepositories(selectedConnectionId);
      }
    } else {
      error ||= connectionResult.reason instanceof Error
        ? connectionResult.reason.message
        : "Could not load GitHub connections.";
    }
    loading = false;
  }

  function changeConnection(): void {
    void loadRepositories(selectedConnectionId);
  }

  function changeRepository(): void {
    preview = null;
    error = "";
  }

  async function reviewIssue(): Promise<void> {
    if (!selectedConnectionId || !selectedRepositoryId) return;
    previewing = true;
    error = "";
    reconciliationMessage = "";
    try {
      preview = await previewGithubHandoffIssue(jobId, {
        connectionId: selectedConnectionId,
        repositoryId: selectedRepositoryId,
      });
      focusResult();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not prepare the GitHub issue preview.";
    } finally {
      previewing = false;
    }
  }

  async function createIssue(): Promise<void> {
    if (!preview) return;
    dispatching = true;
    error = "";
    try {
      dispatch = await dispatchGithubHandoffIssue(jobId, {
        connectionId: preview.connectionId,
        repositoryId: preview.payload.destination.repositoryId,
        payloadFingerprint: preview.payloadFingerprint,
      });
      preview = null;
      focusResult();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not create the GitHub issue.";
    } finally {
      dispatching = false;
    }
  }

  async function retryIssue(): Promise<void> {
    if (!dispatch?.retryable) return;
    dispatching = true;
    error = "";
    try {
      dispatch = await dispatchGithubHandoffIssue(jobId, {
        connectionId: dispatch.connectionId,
        repositoryId: dispatch.destinationContainerId,
        payloadFingerprint: dispatch.payloadFingerprint,
      });
      focusResult();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not retry the GitHub issue.";
    } finally {
      dispatching = false;
    }
  }

  async function reconcile(): Promise<void> {
    if (!dispatch) return;
    reconciling = true;
    error = "";
    reconciliationMessage = "";
    try {
      const result = await reconcileGithubHandoffDispatch(jobId, dispatch.id);
      dispatch = result.dispatch;
      reconciliationMessage = result.reconciliation === "matched"
        ? "The matching GitHub issue was found."
        : result.reconciliation === "not_found"
          ? "No exact matching issue was found. Do not create another issue."
          : result.reconciliation === "multiple_matches"
            ? "More than one matching issue was found. Manual review is required."
            : "This receipt no longer needs reconciliation.";
      focusResult();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not reconcile the GitHub receipt.";
    } finally {
      reconciling = false;
    }
  }

  onMount(load);
</script>

<section class="github-dispatch" aria-labelledby="github-dispatch-heading" aria-busy={loading || previewing || dispatching || reconciling}>
  <div class="dispatch-heading">
    <Github aria-hidden="true" size={19} />
    <div>
      <h5 id="github-dispatch-heading">Send to GitHub</h5>
      <p>Create one issue from the frozen owner handoff.</p>
    </div>
  </div>

  {#if loading}
    <p class="dispatch-state"><Loader2 class="spin" aria-hidden="true" size={16} /> Loading GitHub…</p>
  {:else if dispatch}
    <div class="receipt">
      <h6 bind:this={resultHeading} tabindex="-1">
        {#if dispatch.status === "SUCCEEDED"}
          <CheckCircle2 aria-hidden="true" size={18} /> GitHub issue created
        {:else if dispatch.status === "PENDING"}
          <Loader2 class="spin" aria-hidden="true" size={18} /> Creation in progress
        {:else}
          <AlertTriangle aria-hidden="true" size={18} />
          {dispatch.status === "UNKNOWN" ? "Creation outcome unknown" : "GitHub rejected the issue"}
        {/if}
      </h6>
      <p><strong>{dispatch.destination.fullName}</strong> · {dispatch.payload.request.title}</p>
      {#if dispatch.status === "SUCCEEDED" && dispatch.providerResourceUrl}
        <a class="primary-link" href={dispatch.providerResourceUrl} target="_blank" rel="noopener noreferrer">
          Open GitHub issue <ExternalLink aria-hidden="true" size={15} />
        </a>
      {:else if dispatch.status === "PENDING"}
        <p class="caution">The request may already be at GitHub. Do not submit it again.</p>
        <button type="button" class="secondary-action" onclick={loadDispatch}>
          <RefreshCw aria-hidden="true" size={15} /> Refresh status
        </button>
      {:else if dispatch.status === "UNKNOWN"}
        <p class="caution">
          GitHub may have created the issue. NicheIQ will not retry automatically because that could create a duplicate.
        </p>
        <button type="button" class="secondary-action" onclick={reconcile} disabled={reconciling}>
          {#if reconciling}<Loader2 class="spin" aria-hidden="true" size={15} />{/if}
          {reconciling ? "Checking…" : "Reconcile status"}
        </button>
      {:else}
        <p class="caution">
          No issue was created. GitHub rejected this attempt before accepting the write.
        </p>
        {#if dispatch.retryable}
          <button type="button" class="secondary-action" onclick={retryIssue} disabled={dispatching}>
            {#if dispatching}<Loader2 class="spin" aria-hidden="true" size={15} />{/if}
            {dispatching ? "Retrying…" : "Retry issue creation"}
          </button>
        {/if}
      {/if}
      {#if reconciliationMessage}
        <p class="reconciliation" role="status" aria-live="polite">{reconciliationMessage}</p>
      {/if}
    </div>
  {:else if !enabled}
    <p class="dispatch-state">GitHub issue creation is not configured for this workspace.</p>
  {:else if !connections.length}
    <div class="connect-state">
      <p>Connect a GitHub App installation before choosing a repository.</p>
      <a class="primary-link" href={`/api/integrations/github/connect?jobId=${encodeURIComponent(jobId)}`}>
        Connect GitHub <ExternalLink aria-hidden="true" size={15} />
      </a>
    </div>
  {:else if preview}
    <form class="preview" onsubmit={(event) => { event.preventDefault(); void createIssue(); }}>
      <h6 bind:this={resultHeading} tabindex="-1">Review the exact issue</h6>
      <p class="preview-note">
        NicheIQ will send only this title and Markdown body. It will not add labels,
        assignees, milestones, projects, attachments, or generated subtasks.
      </p>
      <dl>
        <div><dt>Repository</dt><dd>{preview.payload.destination.fullName}</dd></div>
        <div><dt>Title</dt><dd>{preview.payload.request.title}</dd></div>
      </dl>
      <div class="body-preview">
        <span>Markdown body</span>
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -- keyboard focus keeps the long read-only issue body scrollable -->
        <pre
          role="region"
          tabindex="0"
          aria-label="GitHub issue Markdown body"
        >{preview.payload.request.body}</pre>
      </div>
      <div class="actions">
        <button type="button" class="secondary-action" onclick={() => (preview = null)} disabled={dispatching}>
          Change repository
        </button>
        <SubmitButton
          type="submit"
          class=""
          loading={dispatching}
          loadingText="Creating…"
          label="Create issue in GitHub"
        />
      </div>
    </form>
  {:else}
    <form class="destination" onsubmit={(event) => { event.preventDefault(); void reviewIssue(); }}>
      {#if connections.length > 1}
        <FormField
          id="github-connection"
          kind="select"
          label="GitHub account"
          bind:value={selectedConnectionId}
          onchange={changeConnection}
        >
          {#each connections as connection}
            <option value={connection.id}>{connection.accountLogin}</option>
          {/each}
        </FormField>
      {:else if selectedConnection}
        <p class="account-line">Connected as <strong>{selectedConnection.accountLogin}</strong></p>
      {/if}

      <FormField
        id="github-repository"
        kind="select"
        label="Repository"
        bind:value={selectedRepositoryId}
        onchange={changeRepository}
        disabled={loadingRepositories}
      >
        {#if loadingRepositories}
          <option value="">Loading repositories…</option>
        {:else if !repositories.length}
          <option value="">No available repositories</option>
        {:else}
          {#each repositories as repository}
            <option value={repository.id} disabled={!repository.hasIssues}>
              {repository.fullName}{repository.private ? " · private" : ""}{repository.hasIssues ? "" : " · issues disabled"}
            </option>
          {/each}
        {/if}
      </FormField>
      <p class="destination-note">
        Preview is read-only. GitHub is contacted for a write only after the separate confirmation.
      </p>
      <SubmitButton
        type="submit"
        class=""
        loading={previewing}
        disabled={!selectedRepository}
        loadingText="Preparing…"
        label="Review exact issue"
      />
    </form>
  {/if}

  {#if error}
    <p class="dispatch-error" role="alert"><AlertTriangle aria-hidden="true" size={16} /> {error}</p>
  {/if}
</section>

<style>
  .github-dispatch {
    margin-top: 1.15rem;
    padding-top: 1.15rem;
    border-top: 1px solid var(--color-border);
  }

  .dispatch-heading {
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
  }

  .dispatch-heading > :global(svg) {
    flex: 0 0 auto;
    margin-top: 0.1rem;
  }

  h5,
  h6 {
    margin: 0;
    color: var(--color-text-primary);
  }

  h5 {
    font-size: 1rem;
    line-height: 1.25;
  }

  h6 {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 1rem;
    line-height: 1.35;
  }

  h6:focus {
    outline: none;
  }

  .dispatch-heading p,
  .dispatch-state,
  .connect-state p,
  .preview-note,
  .destination-note,
  .account-line,
  .caution,
  .reconciliation {
    margin: 0.25rem 0 0;
    color: var(--color-text-muted);
    font-size: var(--text-13);
    line-height: 1.5;
  }

  .dispatch-state {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-height: 3rem;
  }

  .connect-state,
  .destination,
  .preview,
  .receipt {
    margin-top: 0.9rem;
  }

  .destination {
    display: grid;
    max-width: 38rem;
    gap: 0.45rem;
  }

  .body-preview > span {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
  }

  button:focus-visible,
  a:focus-visible,
  pre:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  dl {
    margin: 0.9rem 0;
  }

  dl div {
    display: grid;
    grid-template-columns: minmax(7rem, 1fr) minmax(0, 3fr);
    gap: 0.75rem;
    padding: 0.55rem 0;
    border-bottom: 1px solid var(--color-border);
  }

  dt {
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    font-weight: 700;
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
    font-size: var(--text-13);
  }

  .body-preview {
    margin-top: 0.85rem;
  }

  .body-preview pre {
    display: block;
    width: 100%;
    min-height: 16rem;
    max-height: 22rem;
    margin: 0.4rem 0 0;
    padding: 0.85rem;
    overflow: auto;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    line-height: 1.55;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin-top: 0.9rem;
  }

  .secondary-action,
  .primary-link {
    display: inline-flex;
    min-height: 2.4rem;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    width: fit-content;
    padding: 0.5rem 0.8rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .secondary-action:hover,
  .primary-link:hover {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .secondary-action:active:not(:disabled),
  .primary-link:active {
    transform: scale(0.98);
  }

  .secondary-action:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .receipt {
    padding: 0.85rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .receipt > p {
    margin: 0.45rem 0 0.7rem;
    font-size: var(--text-13);
    overflow-wrap: anywhere;
  }

  .receipt .caution,
  .receipt .reconciliation {
    max-width: 68ch;
  }

  .dispatch-error {
    display: flex;
    align-items: flex-start;
    gap: 0.4rem;
    margin: 0.75rem 0 0;
    color: var(--color-error-text);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  :global(.github-dispatch .spin) {
    animation: github-spin 800ms linear infinite;
  }

  @keyframes github-spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 560px) {
    dl div {
      display: block;
    }

    dd {
      margin-top: 0.2rem;
    }

    .actions button {
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    :global(.github-dispatch .spin) {
      animation-duration: 1.6s;
    }

    .secondary-action:active:not(:disabled),
    .primary-link:active {
      transform: none;
    }
  }
</style>
