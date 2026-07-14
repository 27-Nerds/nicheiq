/**
 * Durable ledger rows (continuous-analyst-ledger plan, Phase 2).
 *
 * The analyst thread is the record of a guided run, so an applied change must
 * survive a reload — not live only in the browser session that made it. These
 * rows go in the EXISTING ChatMessage table under non-conversational roles
 * ('receipt' today; 'system' markers later). `role` is a varchar, so no
 * migration is needed.
 *
 * HARD CONSTRAINT: chat.ts's prompt-history query filters
 * `role IN ('user','assistant')`. Any new role added here MUST stay outside
 * that set, or the row is injected into the model's context as if the user had
 * said it. The 30-turn cap counts `role='user'` only, so these rows are
 * likewise free.
 */

/** Applied-change receipts are written in two phases so a failed apply never
 *  leaves a lie in the ledger: `submitted` at gate-action (inside the status
 *  flip, deleted if the enqueue compensates), promoted to `applied` when the
 *  worker re-arrives at the same gate with a refreshed artifact.
 *
 *  `seed_submitted`/`seed_settled` are the SAME two-phase idiom for a user-composed idea
 *  seed (plans/eager-meandering-feather.md Phase 5/6): `seed_submitted` is written by
 *  POST /:jobId/seed-idea inside the charge+flip+openDispatch transaction (deleted if the
 *  enqueue compensates, mirroring the gate-patch receipt); `seed_settled` is a SEPARATE row
 *  written by /api/workers/seed-complete or /seed-failed carrying the terminal `outcome`.
 *  Unlike gate_patch_applied, settled is never a promotion-in-place of the submitted row —
 *  the frontend layers both onto the same `sourceMessageId` key and lets the later row win. */
export interface SeedResultSummary {
  solution_name: string;
  short_description?: string;
  market_fit_score?: number;
}

export type LedgerEventName =
  | 'gate_patch_submitted' | 'gate_patch_applied'
  | 'seed_submitted' | 'seed_settled';

export interface LedgerEventEnvelope {
  kind: 'ledger_event';
  version: 1;
  event: LedgerEventName;
  /** The whitelisted patch the user approved (G1 or G2 field diff). Empty for seed events —
   *  a seed has no field diff, just free text + optional refs. */
  patch: Record<string, unknown>;
  /** Rendered field rows — the frontend shows these verbatim, so the wording is
   *  decided once, server-side, and stays stable across clients. Empty for seed events. */
  rows: { label: string; value: string }[];
  /** Chat message that proposed this patch/seed, when it came from the analyst (the
   *  inline exclude-pain chips have no proposing message). Lets the UI show that
   *  proposal card in its terminal state after a reload — REQUIRED for seed events (card
   *  identity IS this id), optional for gate-patch events. */
  sourceMessageId?: string;
  /** `seed_settled` only — the seed's terminal outcome. 'failed' means the pipeline never
   *  produced anything (refunded); 'accepted'/'demoted' mean it did (never refunded). */
  outcome?: 'accepted' | 'demoted' | 'failed' | 'refunded';
  /** Compact evaluated result for the proposal card; full details live elsewhere. */
  idea?: SeedResultSummary;

}

/** Mirrors the frontend's gateFields.ts labels — same words on both sides. */
const GATE_FIELD_LABEL: Record<string, string> = {
  niche_description: 'Niche description',
  market_segments: 'Market segments',
  industry_boundaries: 'Industry boundaries',
  user_target_audience: 'Target audience',
  primary_target_segment: 'Primary segment',
  excluded_segments: 'Excluded segments',
  segment_emphasis: 'Segment emphasis',
  pain_scope: 'Pain scope',
};

export function formatGateFieldValue(field: string, value: unknown): string {
  if (value == null || value === '') return '(not set)';
  if (field === 'pain_scope' && typeof value === 'object') {
    const v = value as { excluded_titles?: string[]; pinned_titles?: string[] };
    const parts: string[] = [];
    if (v.excluded_titles?.length) parts.push(`exclude: ${v.excluded_titles.join(', ')}`);
    if (v.pinned_titles?.length) parts.push(`pin: ${v.pinned_titles.join(', ')}`);
    return parts.length ? parts.join(' · ') : '(no change)';
  }
  if (field === 'segment_emphasis' && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, string>);
    return entries.length ? entries.map(([k, v2]) => `${k}: ${v2}`).join(', ') : '(none)';
  }
  if (Array.isArray(value)) return value.length ? value.join(', ') : '(none)';
  return String(value);
}

export function buildPatchRows(patch: Record<string, unknown>): { label: string; value: string }[] {
  return Object.entries(patch).map(([field, value]) => ({
    label: GATE_FIELD_LABEL[field] ?? field,
    value: formatGateFieldValue(field, value),
  }));
}

/** One-line human summary stored on the row's `content` (what a transcript reader
 *  sees even without the structured rows). */
export function buildReceiptContent(patch: Record<string, unknown>): string {
  const fields = Object.keys(patch).map((f) => GATE_FIELD_LABEL[f] ?? f);
  return fields.length ? `Applied changes to ${fields.join(', ')}` : 'Applied changes';
}

export function buildPatchEnvelope(
  event: LedgerEventName,
  patch: Record<string, unknown>,
  sourceMessageId?: string
): LedgerEventEnvelope {
  return {
    kind: 'ledger_event',
    version: 1,
    event,
    patch,
    rows: buildPatchRows(patch),
    ...(sourceMessageId ? { sourceMessageId } : {}),
  };
}

/** One-line human summary for a seed receipt row — chrome only (the frontend never renders
 *  this row directly, see LedgerEventEnvelope's doc comment), but kept honest for anyone
 *  reading the raw transcript/audit trail. */
export function buildSeedReceiptContent(
  event: 'seed_submitted' | 'seed_settled',
  outcome?: LedgerEventEnvelope['outcome'],
): string {
  if (event === 'seed_submitted') return 'Evaluating your idea…';
  if (outcome === 'accepted') return 'Evaluation complete — the result was added to ranked candidates.';
  if (outcome === 'demoted') return "We tested your idea — it didn't clear the market-fit bar.";
  return 'Your idea could not be evaluated — credits refunded.';
}

/** Builds the seed envelope — always REQUIRES sourceMessageId (unlike buildPatchEnvelope's
 *  optional one): a seed's card identity IS this id, so a row without one can never be
 *  resolved back to a card. `patch`/`rows` are empty — a seed has no field diff. */
export function buildSeedEnvelope(
  event: 'seed_submitted' | 'seed_settled',
  sourceMessageId: string,
  outcome?: LedgerEventEnvelope['outcome'],
  idea?: Record<string, unknown>,
): LedgerEventEnvelope {
  const result = idea && typeof idea.solution_name === 'string'
    ? {
        solution_name: idea.solution_name,
        ...(typeof idea.short_description === 'string'
          ? { short_description: idea.short_description }
          : {}),
        ...(typeof idea.market_fit_score === 'number'
          ? { market_fit_score: idea.market_fit_score }
          : {}),
      }
    : undefined;

  return {
    kind: 'ledger_event',
    version: 1,
    event,
    patch: {},
    rows: [],
    sourceMessageId,
    ...(outcome ? { outcome } : {}),
    ...(result ? { idea: result } : {}),
  };
}
