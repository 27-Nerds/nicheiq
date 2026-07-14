// Per-job analyst-ledger store (continuous-analyst-ledger plan, Phase 1).
// Owns the FULL chat history for one job across all gate stages (1=G1 niche,
// 4=G2 audience, 5=G3 selection), so every surface — checkpoint page, selection
// rail, run shell, completed transcript — reads the same cached thread and
// remounts without a "Loading conversation…" flash. One job page is on screen
// at a time, so this is a singleton keyed by jobId: `init` with a new jobId
// resets state; `init` with the same jobId is a no-op (cache hit).
import { getChatHistory, isLedgerEvent, type ChatMessageDTO, type ChatPatch, type ChatToolCall, type SeedResultSummary } from "$lib/api";

/** Ledger row — a persisted ChatMessage plus session-local rows (optimistic user
 *  turns, streamed assistant turns, apply receipts) appended by the active surface. */
export interface LedgerMessage {
  id: string;
  gateStage: number;
  role: "user" | "assistant" | "receipt" | "system";
  content: string;
  patchJson?: ChatPatch | null;
  toolCallsJson?: ChatToolCall[] | null;
  /** Analyst-authored follow-up chips for this turn (assistant rows only). */
  suggestionsJson?: string[] | null;
  truncated?: boolean;
  dismissed?: boolean;
  createdAt?: string;
  /** Session receipts (GateWorkbench apply flow) carry structured rows; persisted
   *  'receipt' rows (Phase 2) carry the same shape inside patchJson instead. */
  receipt?: { rows: { label: string; value: string }[]; note: string };
}

export interface LedgerSegment {
  gateStage: number;
  messages: LedgerMessage[];
}

/** Display order of segments — pipeline order, not numeric quirks. */
const SEGMENT_ORDER = [1, 4, 5];

const MAX_TURNS = 30;

/** "Keep as is" is local-only server-side (no dismiss endpoint), and `fetchHistory`
 *  rebuilds every persisted row from scratch on each reload — so without a durable
 *  copy here, ANY reload (including one an unrelated apply triggers) resurrects a
 *  dismissed proposal's live Apply button. Keyed by job id so dismissals from one
 *  job never bleed into another's ledger. */
const DISMISSED_KEY_PREFIX = "nicheiq.dismissedPatches.";

function dismissedStorageKey(jobId: string): string {
  return `${DISMISSED_KEY_PREFIX}${jobId}`;
}

function loadDismissedIds(jobId: string): Set<string> {
  if (typeof localStorage === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(dismissedStorageKey(jobId));
    if (!raw) return new Set();
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? new Set(parsed.filter((id): id is string => typeof id === "string"))
      : new Set();
  } catch {
    return new Set();
  }
}

function saveDismissedIds(jobId: string, ids: Set<string>): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(dismissedStorageKey(jobId), JSON.stringify([...ids]));
  } catch {
    // Private mode / quota — the dismissal still works for this session, it just
    // won't survive a reload.
  }
}

/** A seed's lifecycle, keyed by the assistant ChatMessage id that proposed it
 *  (`sourceMessageId` on the durable receipt — same identity idiom as `appliedPatchIds`).
 *  'pending' comes from a durable `seed_submitted` receipt (evaluation in flight —
 *  survives a reload so a submitted card never re-arms Evaluate/Dismiss); the terminal
 *  states come from `seed_settled`. */
export type SeedOutcome = 'pending' | 'accepted' | 'demoted' | 'failed' | 'refunded';

let _jobId = $state<string | null>(null);
let _messages = $state<LedgerMessage[]>([]);
let _historyLoaded = $state(false);
let _loadFailed = $state(false);
let _weakPool = $state(false);
/** Evaluated seed summaries, keyed like _seedOutcomes and rebuilt from settlement receipts. */
let _seedResults = $state<Map<string, SeedResultSummary>>(new Map());
let _appliedPatchIds = $state<Set<string>>(new Set());
/** Persisted "Keep as is" dismissals for the current job — see DISMISSED_KEY_PREFIX. */
let _dismissedIds = $state<Set<string>>(new Set());
/** Server-reported global turn usage (Phase 2 history response); null → derive locally. */
let _serverUsedTurns = $state<number | null>(null);
/** Seed card state, rebuilt fresh from durable receipts on every fetch — see SeedOutcome. */
let _seedOutcomes = $state<Map<string, SeedOutcome>>(new Map());
let _loadPromise: Promise<void> | null = null;

const _segments = $derived.by((): LedgerSegment[] => {
  const byStage = new Map<number, LedgerMessage[]>();
  for (const m of _messages) {
    const list = byStage.get(m.gateStage);
    if (list) list.push(m);
    else byStage.set(m.gateStage, [m]);
  }
  const ordered = SEGMENT_ORDER.filter((s) => byStage.has(s));
  // Unknown future stages render after the known ones rather than vanishing.
  const extras = [...byStage.keys()].filter((s) => !SEGMENT_ORDER.includes(s)).sort((a, b) => a - b);
  return [...ordered, ...extras].map((gateStage) => ({ gateStage, messages: byStage.get(gateStage)! }));
});

const _usedTurns = $derived(
  _serverUsedTurns ?? _messages.filter((m) => m.role === "user").length,
);

async function fetchHistory(): Promise<void> {
  const jobId = _jobId;
  if (!jobId) return;
  try {
    const res = await getChatHistory(jobId);
    if (_jobId !== jobId) return; // job changed mid-flight — drop stale response
    const persisted: LedgerMessage[] = (res.messages as ChatMessageDTO[])
      // A 'submitted' receipt is an apply still in flight (or one whose enqueue was
      // compensated and is about to be deleted) — the ledger only shows changes the
      // pipeline actually re-derived with.
      .filter((m) => !(m.role === "receipt" && m.patchJson && isLedgerEvent(m.patchJson) && m.patchJson.event !== "gate_patch_applied"))
      .map((m) => ({
        id: m.id,
        gateStage: m.gateStage,
        role: m.role,
        content: m.content,
        patchJson: m.patchJson ?? null,
        toolCallsJson: m.toolCallsJson ?? null,
        suggestionsJson: m.suggestionsJson ?? null,
        truncated: m.truncated,
        createdAt: m.createdAt,
        // Re-apply persisted "Keep as is" dismissals — this row was just rebuilt
        // from scratch and knows nothing of the local decision otherwise.
        dismissed: _dismissedIds.has(m.id),
        // Persisted receipts render through the same rows/note shape the session
        // receipts use, so there is ONE receipt renderer.
        ...(m.role === "receipt" && m.patchJson && isLedgerEvent(m.patchJson)
          ? { receipt: { rows: m.patchJson.rows ?? [], note: m.content } }
          : {}),
      }));

    // Applied patches come back from the server now — a reload no longer re-offers
    // an Apply button on a proposal the user already applied.
    const appliedFromServer = (res.messages as ChatMessageDTO[])
      .filter((m) => m.role === "receipt" && m.patchJson && isLedgerEvent(m.patchJson) && m.patchJson.event === "gate_patch_applied")
      .map((m) => (m.patchJson as { sourceMessageId?: string }).sourceMessageId)
      .filter((id): id is string => !!id);
    if (appliedFromServer.length) {
      _appliedPatchIds = new Set([..._appliedPatchIds, ...appliedFromServer]);
    }

    // Seed-card state (plans/eager-meandering-feather.md Phase 6/8) — derived from the
    // SAME durable-receipt idiom as appliedPatchIds, not a parallel client store. A
    // 'seed_submitted' receipt means the worker is still evaluating (durable across a
    // reload, so a submitted card never re-arms); 'seed_settled' carries the terminal
    // outcome. Settled must win over submitted for the same message — process submitted
    // first, then let settled overwrite. Server truth is layered ONTO the existing map
    // (not replacing it) so an optimistic `markSeedPending` call survives until the
    // server actually confirms/settles it.
    const seedResultsFromServer = new Map<string, SeedResultSummary>();
    const seedFromServer = new Map<string, SeedOutcome>();
    for (const m of res.messages as ChatMessageDTO[]) {
      if (m.role !== "receipt" || !m.patchJson || !isLedgerEvent(m.patchJson)) continue;
      const sourceMessageId = m.patchJson.sourceMessageId;
      if (!sourceMessageId) continue;
      if (m.patchJson.event === "seed_submitted") {
        seedFromServer.set(sourceMessageId, "pending");
      } else if (m.patchJson.event === "seed_settled" && m.patchJson.outcome) {
        seedFromServer.set(sourceMessageId, m.patchJson.outcome);
        if (m.patchJson.idea) seedResultsFromServer.set(sourceMessageId, m.patchJson.idea);
      }
    }
    if (seedFromServer.size) {
      _seedOutcomes = new Map([..._seedOutcomes, ...seedFromServer]);
    }
    if (seedResultsFromServer.size) {
      _seedResults = new Map([..._seedResults, ...seedResultsFromServer]);
    }
    // Keep session-local rows (optimistic turns, receipts) the server doesn't know
    // yet. A local receipt is the optimistic twin of a durable one — once the gate
    // re-arrival persists the real row for that stage, drop the twin or the applied
    // change would appear twice.
    const persistedReceiptStages = new Set(
      persisted.filter((m) => m.role === "receipt").map((m) => m.gateStage),
    );
    const persistedIds = new Set(persisted.map((m) => m.id));
    const locals = _messages.filter(
      (m) =>
        m.id.startsWith("local-") &&
        !persistedIds.has(m.id) &&
        !(m.role === "receipt" && persistedReceiptStages.has(m.gateStage)),
    );
    _messages = [...persisted, ...locals];
    _weakPool = res.weakPool ?? false;
    const used = (res as { usedTurns?: number }).usedTurns;
    _serverUsedTurns = typeof used === "number" ? used : null;
    _loadFailed = false;
  } catch {
    // GET /chat/history is auth+ownership only — any failure is a genuine load
    // failure, not entitlement. Existing cached messages are kept; surfaces show
    // a retry affordance instead of a blank panel.
    _loadFailed = true;
  } finally {
    _historyLoaded = true;
  }
}

export const chatLedger = {
  get jobId() { return _jobId; },
  get messages() { return _messages; },
  get segments() { return _segments; },
  get historyLoaded() { return _historyLoaded; },
  get loadFailed() { return _loadFailed; },
  get weakPool() { return _weakPool; },
  get appliedPatchIds() { return _appliedPatchIds; },
  get usedTurns() { return _usedTurns; },
  get maxTurns() { return MAX_TURNS; },
  /** True while ANY seed for this job is still being evaluated. Durable (rebuilt from
   *  the server's `seed_submitted`/`seed_settled` receipts on every fetch), so it's
   *  true immediately after a page reload mid-evaluation — even before SelectionWorkbench
   *  itself has mounted — which is what lets the job page's mount guard stay broad
   *  enough to show a still-evaluating (or just-demoted) seed instead of nothing. */
  get hasPendingSeed() {
    for (const outcome of _seedOutcomes.values()) {
      if (outcome === "pending") return true;
    }
    return false;
  },

  /** Messages for one gate stage — the slice an active conversation renders. */
  segmentMessages(gateStage: number): LedgerMessage[] {
    return _messages.filter((m) => m.gateStage === gateStage);
  },

  /** Terminal/in-flight state of a seed card, keyed by the proposing assistant
   *  message id — undefined means "not yet acted on" (the card still offers
   *  Evaluate/Dismiss). Derived from durable receipts (see fetchHistory above),
   *  so a reload reflects the true outcome instead of resetting to undecided. */
  seedOutcome(sourceMessageId: string): SeedOutcome | undefined {
    return _seedOutcomes.get(sourceMessageId);
  },

  /** Compact evaluated result carried by the durable settlement receipt. */
  seedResult(sourceMessageId: string): SeedResultSummary | undefined {
    return _seedResults.get(sourceMessageId);
  },

  /** Optimistic local mark right after `seedIdea()` succeeds — the durable
   *  `seed_submitted` receipt won't be visible until the next reload, and the
   *  card must flip to "Evaluating…" immediately, not after a round-trip. A
   *  later reload's server truth (see fetchHistory) layers on top of this. */
  markSeedPending(sourceMessageId: string): void {
    _seedOutcomes = new Map(_seedOutcomes).set(sourceMessageId, "pending");
  },

  /** Idempotent per job: first call fetches, repeat calls are cache hits. A new
   *  jobId resets everything (the store is page-scoped, one job at a time). */
  init(jobId: string): Promise<void> {
    if (_jobId === jobId && _loadPromise) return _loadPromise;
    _jobId = jobId;
    _messages = [];
    _historyLoaded = false;
    _loadFailed = false;
    _weakPool = false;
    _appliedPatchIds = new Set();
    _serverUsedTurns = null;
    _seedOutcomes = new Map();
    _seedResults = new Map();
    _dismissedIds = loadDismissedIds(jobId);
    _loadPromise = fetchHistory();
    return _loadPromise;
  },

  /** Re-fetch and reconcile (SSE status transitions, retry affordance). */
  reload(): Promise<void> {
    if (!_jobId) return Promise.resolve();
    _loadPromise = fetchHistory();
    return _loadPromise;
  },

  /** Append a session-local row (optimistic user turn, streamed assistant turn,
   *  apply receipt). Callers use `local-` prefixed ids for rows the server does
   *  not know; server-issued ids (streamed `done` messages) pass through as-is.
   *
   *  `jobId` is the job THIS row belongs to (the id the caller captured when the turn
   *  started), not necessarily the job currently loaded — a `send()` in flight when the
   *  user navigates to another job's page can still resolve after `init()` has already
   *  reset the store for the new job. Reject a stale caller (`jobId !== _jobId`) rather
   *  than silently appending job A's reply into job B's ledger. */
  appendLocal(jobId: string, msg: LedgerMessage): void {
    if (jobId !== _jobId) return;
    _messages = [..._messages, msg];
  },

  /** Retract an optimistic row after a transport failure. Same stale-job guard as
   *  `appendLocal` — see there. */
  retractLocal(jobId: string, id: string): void {
    if (jobId !== _jobId) return;
    _messages = _messages.filter((m) => m.id !== id);
  },

  updateLocal(jobId: string, id: string, patch: Partial<LedgerMessage>): void {
    if (jobId !== _jobId) return;
    _messages = _messages.map((m) => (m.id === id ? { ...m, ...patch } : m));
  },

  /** Swap an optimistic user row's temporary `local-…` id for the persisted one the server
   *  returns on `done`.
   *
   *  Without this the row is a permanent orphan: reconciliation keeps every `local-` row whose id
   *  is not in the server set (see fetchHistory), and the server's id is a UUID — so the next
   *  reload renders the user's question TWICE, once from each copy. Promoting the id makes the
   *  two rows the same row. Same stale-job guard as `appendLocal` — see there. */
  promoteUserMessage(jobId: string, localId: string, serverId: string): void {
    if (jobId !== _jobId) return;
    if (!serverId || localId === serverId) return;
    _messages = _messages.map((m) => (m.id === localId ? { ...m, id: serverId } : m));
  },

  /** Trust the server's turn count.
   *
   *  `usedTurns` was only ever computed by the history GET, and once set it PINNED the display —
   *  locally-sent turns never incremented it. So the counter under-reported for the whole session
   *  and a user could hit the wall while the UI still read 24/30. The stream now reports the count
   *  with every turn. Same stale-job guard as `appendLocal` — a `done`/`error` event that resolves
   *  for a job the user has since navigated away from must not overwrite the count for the job
   *  actually on screen. */
  setUsedTurns(jobId: string, used: number | null | undefined): void {
    if (jobId !== _jobId) return;
    if (typeof used === "number") _serverUsedTurns = used;
  },

  /** Mark a patch-proposal message as applied (terminal card state). */
  markApplied(messageId: string): void {
    _appliedPatchIds = new Set([..._appliedPatchIds, messageId]);
  },

  /** "Keep as is" on a proposal — persisted to localStorage (keyed by job id) so it
   *  survives ANY reload, including one an unrelated apply triggers, not just the
   *  in-memory flag `fetchHistory` would otherwise wipe on its next rebuild. */
  dismissPatch(messageId: string): void {
    _dismissedIds = new Set([..._dismissedIds, messageId]);
    if (_jobId) saveDismissedIds(_jobId, _dismissedIds);
    _messages = _messages.map((m) => (m.id === messageId ? { ...m, dismissed: true } : m));
  },

  /** Full reset — page teardown and tests (the singleton otherwise caches across
   *  same-jobId mounts, which is exactly what production wants and tests don't).
   *  Only the in-memory copy of dismissed ids is cleared — the localStorage record
   *  survives by design, and is reloaded fresh (per job id) on the next `init`. */
  reset(): void {
    _jobId = null;
    _messages = [];
    _historyLoaded = false;
    _loadFailed = false;
    _weakPool = false;
    _appliedPatchIds = new Set();
    _serverUsedTurns = null;
    _seedOutcomes = new Map();
    _seedResults = new Map();
    _dismissedIds = new Set();
    _loadPromise = null;
  },
};
