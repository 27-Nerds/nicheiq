/**
 * API client for NicheIQ backend
 */

export const API_BASE = '/api';
// SSE uses the same proxy - SvelteKit +server.ts handles streaming and adds auth headers
export const SSE_BASE = '/api';

export type IdeaFocus = 'auto' | 'novelty' | 'distribution';

export interface CreateJobRequest {
  email: string;
  niche: string;
  allowedProjectTypes?: string[];
  ideaFocus?: IdeaFocus;
}

export interface CreateJobResponse {
  id: string;
  status: string;
  statusUrl: string;
  message: string;
}

export type {
  Job,
  JobAsset,
  StageProgress as JobProgress,
  ErrorDetails,
  ErrorSeverity,
  SolutionPreview,
  SolutionValidationData,
  ReportSummary,
  GateArtifact,
  GateG1Artifact,
  GateG2Artifact,
  GateG1PatchFields,
  GateG2PatchFields,
} from '$lib/types/job';
import type { Job, SolutionPreview, ReportSummary, GateG1PatchFields, GateG2PatchFields } from '$lib/types/job';
import type { RuledOutFinding, OverlapGroup, MarketReality, NicheDifficultyVerdict, DataQualitySummary } from '$lib/types/report';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  const data = await response.json();

  if (!response.ok) {
    throw new ApiError(
      data.error || 'An error occurred',
      response.status,
      // Fall back to the whole body when there's no `details` envelope. Several errors carry
      // their payload at the top level — a 402 reports `balance`/`required` there, and the gate
      // needs those to tell the user how far short they are rather than just "payment required".
      data.details ?? data
    );
  }

  return data as T;
}

/**
 * Create a new research job
 */
export async function createJob(request: CreateJobRequest): Promise<CreateJobResponse> {
  const response = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  return handleResponse<CreateJobResponse>(response);
}

/**
 * Get job status and progress
 */
export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`);
  return handleResponse<Job>(response);
}

/**
 * Cancel a job
 */
export async function cancelJob(jobId: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`, {
    method: 'DELETE',
  });

  return handleResponse<{ message: string }>(response);
}

// ============================================
// Interactive Job Flow
// ============================================

export interface SelectSolutionRequest {
  solutionNames: string[];
  rationale?: string;
}

export interface SolutionsResponse {
  solutionIdeas: SolutionPreview[] | null;
  selectedSolution: string | null;
  selectedSolutions: string[] | null;
  selectionRationale: string | null;
  canRegenerate: boolean;
}

/**
 * Select a solution for deep investigation (Phase 2)
 */
export async function selectSolution(jobId: string, request: SelectSolutionRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/select-solution`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<{ message: string }>(response);
}

/**
 * Regenerate solution ideas
 */
export async function regenerateIdeas(
  jobId: string,
  ideaFocus?: IdeaFocus,
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/regenerate-ideas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ideaFocus ? { idea_focus: ideaFocus } : {}),
  });
  return handleResponse<{ message: string }>(response);
}

/**
 * Get solution ideas for an interactive job
 */
export async function getSolutions(jobId: string): Promise<SolutionsResponse> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/solutions`);
  return handleResponse<SolutionsResponse>(response);
}

/**
 * Get per-stage credit costs (billing/stage-costs). Used at G3 to refresh the
 * `seed_idea` price after a 409 PRICE_CHANGED — the layout's own stageCosts load
 * is a one-time SSR snapshot, so a re-price mid-session needs a fresh fetch.
 */
export async function getStageCosts(): Promise<import('$lib/types/job').StageCosts> {
  const response = await fetch(`${API_BASE}/billing/stage-costs`);
  return handleResponse<import('$lib/types/job').StageCosts>(response);
}

/**
 * Submit a user-composed idea seed for evaluation (plans/eager-meandering-feather.md,
 * Phase 5/6). Runs the SAME idea-birth + scoring as a pool idea and merges into the
 * pool on success — paid, admission-gated by the backend's dispatch/price-CAS
 * contract (mirrors `gateAction`'s `expectedCost`): the server 409s (PRICE_CHANGED)
 * on a mid-flight reprice instead of silently charging a different number, and 402
 * returns `{balance, required}`.
 */
export interface SeedIdeaRequest {
  free_text: string;
  pain_ref?: string;
  tool_ref?: string;
  rationale?: string;
  /** The assistant chat message that proposed this seed — the card identity the
   *  durable settlement receipt is keyed on (see LedgerEventEnvelope). */
  sourceMessageId: string;
  /** The price the seed card showed. Required — evaluating a seed is a purchase,
   *  so the number the user agreed to must be the number they're charged. */
  expectedCost: number;
}

export async function seedIdea(jobId: string, request: SeedIdeaRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/seed-idea`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<{ message: string }>(response);
}

// ============================================
// Guided chat (Phase A — plans/eager-meandering-feather.md)
// ============================================

/** G3 (AWAITING_SELECTION) patch shape — a regeneration steer. */
export interface IdeaFocusPatch {
  idea_focus: IdeaFocus;
  rationale: string;
}

/** G1/G2 (AWAITING_GATE) patch shape — a whitelisted field diff, applied via
 *  `gateAction(jobId, { action: 'apply_stay', patch })`. Mirrors backend chat.ts's
 *  `{gateStage, patch, rationale}` wrapping of the validated tool-call args. */
export interface GatePatchProposal {
  gateStage: 1 | 4;
  patch: GateG1PatchFields | GateG2PatchFields;
  rationale: string;
}

/** Durable ledger row payload (backend utils/ledgerEvents.ts) — carried on a
 *  `role: 'receipt'` ChatMessage. Two-phase: 'gate_patch_submitted' is written when
 *  the user approves an apply, promoted to 'gate_patch_applied' once the pipeline
 *  re-arrives at the gate with the change baked in. Only APPLIED rows are shown.
 *
 *  `seed_submitted` / `seed_settled` are the SAME two-phase idiom for a chat-composed
 *  idea seed (plans/eager-meandering-feather.md, Phase 6/8): 'seed_submitted' is a
 *  durable "evaluation is in flight" marker (so a page reload mid-evaluation still
 *  shows the seed card as pending, never re-arming Evaluate/Dismiss); 'seed_settled'
 *  carries the terminal `outcome`. Both are chrome only — the frontend derives card
 *  state from them but never renders them as their own visible row (the ORIGINAL
 *  `new_idea_seed` proposal message is the one card whose state changes). This client
 *  type is written read-only against a contract another worker is landing server-side
 *  — see plan bullet "Extend the durable server receipt envelope with seed outcomes". */
export interface SeedResultSummary {
  solution_name: string;
  short_description?: string;
  market_fit_score?: number;
}

export interface LedgerEventEnvelope {
  kind: 'ledger_event';
  version: number;
  event: 'gate_patch_submitted' | 'gate_patch_applied' | 'seed_submitted' | 'seed_settled';
  patch: Record<string, unknown>;
  rows: { label: string; value: string }[];
  sourceMessageId?: string;
  /** Compact evaluated result; full detail lives in the candidates/ruled-out UI. */
  idea?: SeedResultSummary;
  /** `seed_settled` only — the seed's terminal outcome. */
  outcome?: 'accepted' | 'demoted' | 'failed' | 'refunded';
}

/** G3 (AWAITING_SELECTION) patch shape — the user composes their own idea via chat
 *  (required free text + optional pain/tool references) and it runs the same
 *  idea-birth + scoring as a pool idea, merging into the pool if it clears the bar.
 *  Card identity is the assistant ChatMessage id that carried this patch
 *  (`sourceMessageId` on the settlement receipt), NOT a separate operation id. */
export interface NewIdeaSeedPatch {
  kind: 'new_idea_seed';
  free_text: string;
  pain_ref?: string;
  tool_ref?: string;
  rationale: string;
}

export type ChatPatch = IdeaFocusPatch | GatePatchProposal | LedgerEventEnvelope | NewIdeaSeedPatch;

/** Narrowing helper — G1/G2 patches carry `gateStage`; the G3 idea-focus patch doesn't. */
export function isGatePatch(patch: ChatPatch): patch is GatePatchProposal {
  return 'gateStage' in patch && 'patch' in patch && !('kind' in patch);
}

/** Narrowing helper — durable ledger rows carry the `kind: 'ledger_event'` envelope. */
export function isLedgerEvent(patch: ChatPatch): patch is LedgerEventEnvelope {
  return (patch as LedgerEventEnvelope).kind === 'ledger_event';
}

/** Narrowing helper — the user-composed-idea proposal carries `kind: 'new_idea_seed'`.
 *  The discriminator the existing G3 idea-focus patch never had. */
export function isNewIdeaSeedPatch(patch: ChatPatch): patch is NewIdeaSeedPatch {
  return (patch as NewIdeaSeedPatch).kind === 'new_idea_seed';
}

/** Narrowing helper — the G3 idea-focus (regenerate-steer) patch is the only shape left
 *  once gate/ledger-event/seed are ruled out; named explicitly (rather than an implicit
 *  `else`) so a dispatch can end in `assertNever` and a future fifth patch kind fails to
 *  compile instead of silently falling through to this one. */
export function isIdeaFocusPatch(patch: ChatPatch): patch is IdeaFocusPatch {
  return 'idea_focus' in patch && !('gateStage' in patch) && !('kind' in patch);
}

/** A single read-only tool invocation made while resolving a turn (chat agent tools v1.1)
 *  — persisted on the assistant ChatMessage row and rendered as a ledger receipt. */
export interface ChatToolCall {
  name: string;
  args: unknown;
  label: string;
}

export interface ChatMessageDTO {
  id: string;
  gateStage: number;
  /** 'receipt' (durable applied-change rows) and 'system' (lifecycle markers) are
   *  non-conversational ledger rows — never fed to the LLM or counted toward the
   *  turn cap. Renderers must tolerate roles they don't know. */
  role: 'user' | 'assistant' | 'receipt' | 'system';
  content: string;
  patchJson?: ChatPatch | null;
  toolCallsJson?: ChatToolCall[] | null;
  /** Follow-up questions the analyst proposed for THIS turn. Null when generation
   *  failed or predates stored suggestions; the client then uses contextual prompts. */
  suggestionsJson?: string[] | null;
  truncated?: boolean;
  createdAt: string;
}

export type ChatStreamEvent =
  | { type: 'token'; delta: string }
  /** Emitted live as each read-only tool call resolves — always BEFORE the terminal
   *  `done` event (and before any streamed tokens from a later round), so the ledger can
   *  render "ANALYST checked evidence for…" receipts as the work happens. */
  | { type: 'tool'; label: string }
  | {
      type: 'done';
      message: {
        id: string;
        role: 'assistant';
        content: string;
        patchJson: ChatPatch | null;
        toolCallsJson?: ChatToolCall[] | null;
        /** Analyst-authored follow-up chips for this turn (null → contextual client prompts). */
        suggestionsJson?: string[] | null;
        createdAt: string;
      };
      /** Persisted id of the USER's turn. We sent it optimistically under a `local-…` id; without
       *  the real one, reconciliation on the next history load keeps BOTH rows and the question
       *  renders twice. */
      userMessageId?: string;
      /** Authoritative turn count after this turn. The client was previously pinned to whatever
       *  the last history GET said, so the counter under-reported all session. */
      usedTurns?: number;
      maxTurns?: number;
    }
  | { type: 'note'; note: string }
  | {
      type: 'error';
      error: string;
      /** Set when the server rolled the user's turn back (a generation that produced nothing must
       *  not cost a turn). The client must retract its optimistic copy, or the question sits in
       *  the thread forever with no answer under it. */
      retractMessageId?: string;
      usedTurns?: number;
    };

/**
 * Get the persisted chat transcript for a job (used to restore history on
 * mount/reload — also the natural entitlement probe: a non-entitled caller gets
 * a 402 here, same as from `streamChat`). `weakPool` (G3/AWAITING_SELECTION only,
 * false otherwise) flags a free-culture-wallet pool where no idea cleared a strong
 * market-fit bar — drives the "Should I even proceed with this niche?" starter chip.
 */
export async function getChatHistory(jobId: string): Promise<{ messages: ChatMessageDTO[]; weakPool?: boolean; usedTurns?: number; maxTurns?: number; stage?: number; capabilities?: string[]; activeOperation?: unknown }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/chat/history`);
  return handleResponse<{ messages: ChatMessageDTO[]; weakPool?: boolean; usedTurns?: number; maxTurns?: number; stage?: number; capabilities?: string[]; activeOperation?: unknown }>(response);
}

/**
 * Stream a guided-chat reply. `EventSource` is GET-only, so this is a separate
 * fetch+ReadableStream transport from `subscribeToProgress` (R3 — the two client
 * transports stay separate, don't try to unify them). Parses the backend's
 * `data: {...}\n\n` lines (same idiom as the SSE progress endpoint) and invokes
 * `onEvent` per line as it arrives.
 */
export async function streamChat(
  jobId: string,
  message: string,
  opts: { signal?: AbortSignal; onEvent: (event: ChatStreamEvent) => void }
): Promise<void> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal: opts.signal,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(data.error || 'Chat request failed', response.status, data.details);
  }
  if (!response.body) {
    throw new Error('Chat response had no body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminalSeen = false;

  const emitChunk = (chunk: string) => {
    const payload = chunk
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n');
    if (!payload) return;
    try {
      const event = JSON.parse(payload) as ChatStreamEvent;
      opts.onEvent(event);
      if (event.type === 'done' || event.type === 'error') terminalSeen = true;
    } catch {
      // A complete but malformed event is ignored. If it was terminal, the
      // history-recovery path below restores the persisted answer.
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    for (const chunk of chunks) emitChunk(chunk);
  }

  // TextDecoder and the SSE frame can both retain a final tail when the proxy closes
  // immediately after the terminal event. The old parser discarded this tail, so the
  // UI removed its pending row even though the backend had persisted the answer.
  buffer += decoder.decode();
  for (const chunk of buffer.split('\n\n')) emitChunk(chunk);
  if (terminalSeen) return;

  // A proxy/network edge can still lose the terminal frame after the backend commits.
  // Recover the exact latest user turn and its following assistant row from durable
  // history instead of leaving a blank-looking response until the next page refresh.
  try {
    const history = await getChatHistory(jobId);
    let userIndex = -1;
    for (let index = history.messages.length - 1; index >= 0; index -= 1) {
      const row = history.messages[index];
      if (row.role === 'user' && row.content === message) {
        userIndex = index;
        break;
      }
    }
    if (userIndex >= 0) {
      const userRow = history.messages[userIndex];
      const assistant = history.messages
        .slice(userIndex + 1)
        .find((row) => row.role === 'assistant');
      if (assistant) {
        opts.onEvent({
          type: 'done',
          message: {
            id: assistant.id,
            role: 'assistant',
            content: assistant.content,
            patchJson: assistant.patchJson ?? null,
            toolCallsJson: assistant.toolCallsJson ?? null,
            suggestionsJson: assistant.suggestionsJson ?? null,
            createdAt: assistant.createdAt,
          },
          userMessageId: userRow.id,
          usedTurns: history.usedTurns,
          maxTurns: history.maxTurns,
        });
        return;
      }
    }
  } catch {
    // Preserve the transport error below; callers already provide retry UX.
  }

  throw new Error('Chat stream ended before the final response arrived');
}

// ============================================
// Guided gates (Phase B — plans/eager-meandering-feather.md)
// ============================================

export interface GateActionRequest {
  action: 'continue' | 'apply_stay';
  gateStage: 1 | 4;
  /** Required for apply_stay; optional carry-along for continue. */
  patch?: GateG1PatchFields | GateG2PatchFields;
  /** Chat message that proposed this patch — stored on the durable receipt so the
   *  proposal card stays in its terminal "Applied" state across reloads. */
  sourceMessageId?: string;
  /** The price the Continue button showed. Continue is a purchase now, so the number the user
   *  agreed to has to be the number they're charged — if an admin re-priced the segment while the
   *  gate was open, the server 409s (PRICE_CHANGED) instead of quietly charging something else. */
  expectedCost?: number;
}

export interface GateActionResponse {
  status: string;
  message: string;
}

/**
 * Continue past, or apply-and-stay at, a guided-mode (chatMode) G1/G2 stage gate.
 * `apply_stay` re-notifies the SAME gate with a refreshed artifact (capped at 5
 * applies/gate — `Job.gateApplyCount`); `continue` advances to the next stop. No
 * credit charge in v1. Mirrors `regenerateIdeas`'s call shape.
 */
export async function gateAction(jobId: string, request: GateActionRequest): Promise<GateActionResponse> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/gate-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<GateActionResponse>(response);
}

/**
 * Terminal job statuses - SSE should close when job reaches these
 */
const TERMINAL_STATUSES = ['COMPLETED', 'FAILED', 'CANCELLED'];

/**
 * Check if a job status is terminal (no more updates expected)
 */
export function isTerminalStatus(status: string | undefined): boolean {
  return !!status && TERMINAL_STATUSES.includes(status.toUpperCase());
}

/**
 * Check if SSE should stay open (accounts for landing page generation on completed jobs)
 */
export function shouldKeepSSEOpen(job: { status: string; landingPageStatus?: string | null }): boolean {
  if (!isTerminalStatus(job.status)) return true;
  return job.landingPageStatus === 'QUEUED' || job.landingPageStatus === 'RUNNING';
}

/**
 * SSE connection options
 */
export interface SSEOptions {
  maxReconnectAttempts?: number;
  reconnectDelayMs?: number;
  onReconnecting?: (attempt: number, maxAttempts: number) => void;
  onMaxReconnectsReached?: () => void;
}

const DEFAULT_MAX_RECONNECT_ATTEMPTS = 10;
const DEFAULT_RECONNECT_DELAY_MS = 3000;

/**
 * Subscribe to job progress updates via SSE with automatic reconnection
 *
 * @param jobId - The job ID to subscribe to
 * @param onUpdate - Callback for job updates. Return the job status to help manage connection lifecycle.
 * @param onError - Optional error callback
 * @param options - Optional configuration for reconnection behavior
 * @returns Cleanup function to close the connection
 */
export function subscribeToProgress(
  jobId: string,
  onUpdate: (job: Job) => void,
  onError?: (error: Error) => void,
  options?: SSEOptions
): () => void {
  const maxAttempts = options?.maxReconnectAttempts ?? DEFAULT_MAX_RECONNECT_ATTEMPTS;
  const delayMs = options?.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY_MS;

  let eventSource: EventSource | null = null;
  let reconnectAttempts = 0;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  let isCleanedUp = false;
  let lastKnownStatus: string | undefined;
  let lastKnownLandingStatus: string | null | undefined;

  function connect() {
    if (isCleanedUp) return;

    // Don't connect if we know the job is in a terminal state with no landing in progress
    if (isTerminalStatus(lastKnownStatus) && lastKnownLandingStatus !== 'QUEUED' && lastKnownLandingStatus !== 'RUNNING') return;

    eventSource?.close();
    eventSource = new EventSource(`${SSE_BASE}/jobs/${jobId}/events`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Job;
        lastKnownStatus = data.status;
        lastKnownLandingStatus = data.landingPageStatus;
        reconnectAttempts = 0; // Reset on successful message
        onUpdate(data);

        // Close connection if job reached terminal state and no landing in progress
        if (!shouldKeepSSEOpen(data)) {
          eventSource?.close();
          eventSource = null;
        }
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource?.close();
      eventSource = null;

      // Don't reconnect if cleaned up or terminal with no landing in progress
      if (isCleanedUp || (isTerminalStatus(lastKnownStatus) && lastKnownLandingStatus !== 'QUEUED' && lastKnownLandingStatus !== 'RUNNING')) {
        return;
      }

      // Attempt reconnect with backoff
      if (reconnectAttempts < maxAttempts) {
        reconnectAttempts++;
        const delay = delayMs * Math.min(reconnectAttempts, 3);
        options?.onReconnecting?.(reconnectAttempts, maxAttempts);
        reconnectTimeout = setTimeout(connect, delay);
      } else {
        options?.onMaxReconnectsReached?.();
        onError?.(new Error('Max SSE reconnection attempts reached'));
      }
    };
  }

  // Start connection
  connect();

  // Return cleanup function
  return () => {
    isCleanedUp = true;
    eventSource?.close();
    eventSource = null;
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
  };
}

/**
 * Get lightweight report summary for preview cards
 */
export async function getReportSummary(jobId: string): Promise<ReportSummary> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/report-summary`);
  return handleResponse<ReportSummary>(response);
}

/**
 * Get materialized discovery evidence data (quotes, audience, influencers)
 * Returns null on 404 (old jobs without discovery data asset)
 */
export async function getDiscoveryData(jobId: string): Promise<import('$lib/types/discovery').DiscoveryData | null> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-data`);
  if (response.status === 404) return null;
  return handleResponse<import('$lib/types/discovery').DiscoveryData>(response);
}

/**
 * Get preview report data (Phase 1 materialized into Report-shaped JSON)
 * Returns null on 404 (old jobs without preview report asset)
 */
export async function getPreviewReport(jobId: string): Promise<import('$lib/types/previewReport').PreviewReport | null> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/preview-report`);
  if (response.status === 404) return null;
  return handleResponse<import('$lib/types/previewReport').PreviewReport>(response);
}

/**
 * Get download URL for report
 */
export function getReportUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/report`;
}

/**
 * Get URL for landing page
 */
export function getLandingPageUrl(jobId: string, download = false): string {
  const base = `${API_BASE}/jobs/${jobId}/landing`;
  return download ? `${base}?download=true` : base;
}

// ============================================
// Report Sharing
// ============================================

export interface ShareInfo {
  isShared: boolean;
  shareToken?: string;
  viewCount?: number;
}

/**
 * Get share status for a job
 */
export async function getShareStatus(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share`);
  return handleResponse<ShareInfo>(response);
}

/**
 * Enable sharing for a job
 */
export async function enableSharing(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share`, {
    method: 'POST',
  });
  return handleResponse<ShareInfo>(response);
}

/**
 * Disable sharing for a job
 */
export async function disableSharing(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share`, {
    method: 'DELETE',
  });
  return handleResponse<ShareInfo>(response);
}

/**
 * Regenerate share token (invalidates old link)
 */
export async function regenerateShareToken(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share/regenerate`, {
    method: 'POST',
  });
  return handleResponse<ShareInfo>(response);
}

// ============================================
// Discovery Sharing
// ============================================

export interface DiscoveryShareInfo {
  isShared: boolean;
  shareToken?: string;
  viewCount?: number;
  voteCount?: number;
  solutionVotes?: Record<string, number>;
}

export interface VoteSummary {
  totalVotes: number;
  solutionVotes: Record<string, number>;
  viewerVote?: { solutionName: string; comment: string | null } | null;
}

/**
 * Public subset of PreviewReport exposed on shared discovery endpoints.
 * Backed by `SharedPreviewReportSchema` on the server; if a field is
 * missing here it's because the server strips it from the payload.
 */
export interface SharedPreviewReport {
  niche?: string;
  niche_context?: {
    niche_input?: string;
    niche_description?: string;
    market_segments?: string[];
    industry_boundaries?: unknown;
    user_target_audience?: string | null;
    resolved_primary_audience?: string | null;
    audience_scope?: string | null;
  } | null;
  detailed_pain_points?: Array<{
    title: string;
    description?: string;
    mention_count?: number;
    severity_score?: number;
    commercial_intent?: number;
    opportunity_level?: 'high' | 'medium' | 'low';
    representative_quotes?: string[];
    source_platforms?: string[];
    categories?: string[];
    affected_segments?: string[];
    solution_approach?: string;
  }>;
  pain_point_analytics?: {
    total_pain_points?: number;
    high_severity_count?: number;
    high_opportunity_count?: number;
    quadrant_distribution?: {
      high_severity_high_wtp: number;
      high_severity_low_wtp: number;
      low_severity_high_wtp: number;
      low_severity_low_wtp: number;
    };
    avg_severity?: number;
    avg_commercial_intent?: number;
    top_pain_point_title?: string;
  } | null;
  audience_mapping?: {
    audience_segments?: Array<{
      segment_name: string;
      size_estimate?: string;
      pain_point_alignment?: string[];
      motivation_drivers?: string[];
      expertise_level?: string;
      budget_sensitivity?: string;
      discovery_channels?: string[];
    }>;
    primary_target_segment?: string;
    segment_prioritization_rationale?: string;
    community_hubs?: string[];
    common_vocabulary?: string[];
    content_preferences?: string;
    messaging_frameworks?: string[];
    tools_currently_used?: string[];
    frustrations_with_existing?: string[];
    recommended_channels?: string[];
    early_adopter_tactics?: string;
  } | null;
  research_metadata?: {
    reddit_posts_analyzed?: number;
    reddit_comments_analyzed?: number;
    generic_posts_analyzed?: number;
    top_subreddits?: { name: string; post_count: number }[];
  } | null;
  evidence_appendix?: {
    top_reddit_threads?: Array<{
      title: string;
      subreddit: string;
      score?: number;
      num_comments?: number;
      key_insight?: string;
      platform?: string;
    }>;
    pain_point_quote_sources?: Array<{
      pain_point_title: string;
      quotes_with_sources: Array<{
        quote: string;
        subreddit?: string;
        score?: string | number;
      }>;
    }>;
  } | null;
  /** Passed through by the sanitizer unless explicitly stripped (it isn't). */
  examined_ruled_out?: RuledOutFinding[];
  /** Passed through by the sanitizer unless explicitly stripped (it isn't). */
  overlap_groups?: OverlapGroup[];
  /** Passed through by the sanitizer unless explicitly stripped (it isn't). */
  market_reality?: MarketReality;
  /** Passed through by the sanitizer unless explicitly stripped (it isn't). */
  idea_portfolio_summary?: string | null;
  /** Passed through by the sanitizer unless explicitly stripped (it isn't). */
  niche_difficulty_verdict?: NicheDifficultyVerdict;
  /** Passed through by the sanitizer unless explicitly stripped (it isn't). */
  data_quality_summary?: DataQualitySummary | null;
}

/**
 * Public subset of DiscoveryData exposed on shared discovery endpoints.
 */
export interface SharedDiscoveryData {
  methodology?: {
    urls_searched: number;
    urls_relevant: number;
    filtering_rate: number;
    quality_tier: string;
    pain_point_quality_tier?: string;
    pain_point_confidence?: number;
    total_engagement?: number;
    avg_engagement?: number;
  };
  subreddit_names?: string[];
  subreddit_post_counts?: Record<string, number>;
  social_posts_sample?: Array<{
    title: string;
    subreddit?: string;
    score?: number;
    num_comments?: number;
    created_utc?: string;
  }>;
  sources_searched?: Record<string, { enabled: boolean; posts_found: number }>;
  discussion_trend?: { month: string; count: number }[];
  discussion_growth_pct?: number | null;
}

export interface DiscoveryShareData {
  shareType: 'discovery';
  niche: string;
  solutions: SolutionPreview[];
  /** @deprecated removed in next release — use previewReport + discoveryData */
  discoveryFindings?: Record<string, any>;
  discoveryData: SharedDiscoveryData | null;
  previewReport: SharedPreviewReport | null;
  voteSummary: VoteSummary;
  allowIndexing?: boolean;
}

export async function getDiscoveryShareStatus(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share`);
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function enableDiscoverySharing(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share`, {
    method: 'POST',
  });
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function disableDiscoverySharing(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share`, {
    method: 'DELETE',
  });
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function regenerateDiscoveryShareToken(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share/regenerate`, {
    method: 'POST',
  });
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function fetchSharedDiscovery(shareToken: string): Promise<DiscoveryShareData> {
  const response = await fetch(`${API_BASE}/shared/discovery/${shareToken}`);
  return handleResponse<DiscoveryShareData>(response);
}

export async function submitDiscoveryVote(
  shareToken: string,
  solutionName: string,
  viewerToken: string,
  comment?: string,
): Promise<VoteSummary> {
  const response = await fetch(`${API_BASE}/shared/discovery/${shareToken}/vote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ solutionName, viewerToken, comment }),
  });
  return handleResponse<VoteSummary>(response);
}

export async function getDiscoveryVotes(shareToken: string, viewerToken?: string): Promise<VoteSummary> {
  const url = viewerToken
    ? `${API_BASE}/shared/discovery/${shareToken}/votes?viewerToken=${viewerToken}`
    : `${API_BASE}/shared/discovery/${shareToken}/votes`;
  const response = await fetch(url);
  return handleResponse<VoteSummary>(response);
}

// ============================================
// Notification Preferences
// ============================================

export interface NotificationPreferences {
  emailEnabled: boolean;
  emailOnJobStart: boolean;
  emailOnJobComplete: boolean;
  emailOnJobError: boolean;
  emailOnSolutionsReady: boolean;
}

export type NotificationPreferencesUpdate = Partial<NotificationPreferences>;

/**
 * Get user's notification preferences
 */
export async function getNotificationPreferences(userId: string): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE}/users/${userId}/notification-preferences`);
  return handleResponse<NotificationPreferences>(response);
}

/**
 * Update user's notification preferences
 */
export async function updateNotificationPreferences(
  userId: string,
  prefs: NotificationPreferencesUpdate
): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE}/users/${userId}/notification-preferences`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  });
  return handleResponse<NotificationPreferences>(response);
}

// ============================================
// Password Management
// ============================================

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

export interface ChangePasswordResponse {
  message: string;
}

/**
 * Change user's password
 */
export async function changePassword(
  userId: string,
  request: ChangePasswordRequest
): Promise<ChangePasswordResponse> {
  const response = await fetch(`${API_BASE}/users/${userId}/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ChangePasswordResponse>(response);
}
