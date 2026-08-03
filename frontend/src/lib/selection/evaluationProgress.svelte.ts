/**
 * Shared wait model for a paid evaluation, so the Concept Forge overlay and the
 * live strip behind it never disagree about what is happening.
 *
 * The discriminator is already on the wire: `/chat/history` returns the job's
 * active dispatch with `createdAt` and `claimedAt` (backend/src/routes/chat.ts).
 * `claimedAt === null` means the request is still sitting in the Redis queue with
 * no worker on it; a timestamp means a worker picked it up. Those are very
 * different waits and were previously presented identically as "pending".
 */

export type EvaluationPhase = "queued" | "running" | "overdue";

export interface EvaluationOperation {
  state?: "AUTHORIZED" | "CLAIMED" | "RECOVERING" | string;
  createdAt?: string;
  claimedAt?: string | null;
}

export interface EvaluationProgress {
  phase: EvaluationPhase;
  elapsedMs: number;
  /** m:ss, or h:mm:ss past an hour. */
  elapsedLabel: string;
}

/**
 * When a wait stops being ordinary and the copy switches to reassurance.
 *
 * PLACEHOLDER: pick this from data before trusting it — the p50 of
 * `claimedAt → settledAt` over settled `JobDispatch` rows where `kind =
 * 'SEED_IDEA'`. Until then the copy deliberately never states a number, it only
 * says the wait is longer than usual, so an uncalibrated constant cannot make
 * the UI assert something false.
 */
export const EVALUATION_OVERDUE_MS = 8 * 60 * 1000;

function parseTime(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const seconds = total % 60;
  const minutes = Math.floor(total / 60) % 60;
  const hours = Math.floor(total / 3600);
  const pad = (n: number) => String(n).padStart(2, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`;
}

export function evaluationProgress(
  operation: EvaluationOperation | null | undefined,
  now: number,
  overdueMs: number = EVALUATION_OVERDUE_MS,
): EvaluationProgress {
  const startedAt = parseTime(operation?.createdAt);
  const claimedAt = parseTime(operation?.claimedAt);
  const elapsedMs = startedAt == null ? 0 : Math.max(0, now - startedAt);
  // Overdue outranks the claim state: once the wait is long the useful message is
  // "this is taking a while and here is what happens next", not which stage it is in.
  const phase: EvaluationPhase = elapsedMs >= overdueMs
    ? "overdue"
    : claimedAt != null
      ? "running"
      : "queued";
  return { phase, elapsedMs, elapsedLabel: formatElapsed(elapsedMs) };
}

export function phaseHeadline(phase: EvaluationPhase, title: string): string {
  if (phase === "queued") return `Waiting for a free worker — ${title}`;
  if (phase === "running") return `Scoring ${title}`;
  return `Still scoring ${title}`;
}

export function phaseNote(phase: EvaluationPhase): string {
  if (phase === "queued") {
    return "Your request is in the queue. Your candidates and other directions are unchanged.";
  }
  if (phase === "running") {
    return "Your candidates and other directions stay unchanged until this direction qualifies.";
  }
  // Never promises a duration; states the guarantee the durable-receipt work made true.
  return "This is taking longer than usual. It will finish or refund on its own — "
    + "you can leave this page and the result will be here when you return.";
}

/**
 * One shared 1s clock for every elapsed timer on the page. Ref-counted so it stops
 * when the last waiting surface unmounts instead of ticking for the whole session.
 */
let _now = $state(Date.now());
let _timer: ReturnType<typeof setInterval> | null = null;
let _refs = 0;

export const elapsedClock = {
  get now() {
    return _now;
  },
  start(): void {
    _refs += 1;
    if (_timer) return;
    _now = Date.now();
    _timer = setInterval(() => {
      _now = Date.now();
    }, 1000);
  },
  stop(): void {
    _refs = Math.max(0, _refs - 1);
    if (_refs > 0 || !_timer) return;
    clearInterval(_timer);
    _timer = null;
  },
};
