// Suggested questions for the analyst thread.
//
// These are not decoration: a suggestion is only worth showing if it names
// something REAL on screen (this checkpoint's actual pains, segments, ideas) and
// leads to an action the user can actually take right now (propose a change,
// exclude a pain, regenerate, continue). So they're derived from three inputs —
// the artifact, the available actions, and the conversation so far — and they
// change as any of those change.
//
// Deliberately deterministic: an extra LLM round-trip per turn would cost money
// and latency to produce chips the state already knows.
import type {
  GateArtifact,
  GateG1Artifact,
  GateG2Artifact,
  SolutionPreview,
} from "$lib/types/job";
import type { LedgerMessage } from "$lib/stores/chatLedger.svelte";
import { isGatePatch, isLedgerEvent } from "$lib/api";
import { displayCompositeScore, solutionDisplayTitle } from "$lib/utils/solution-utils";

const MAX_SUGGESTIONS = 3;

/** Truncate a real name so a chip stays a chip. */
function short(name: string, max = 34): string {
  const t = name.trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

/** Has the user already asked something like this? (Don't suggest it twice.) */
function alreadyAsked(messages: LedgerMessage[], chip: string): boolean {
  const asked = messages.filter((m) => m.role === "user").map((m) => m.content.toLowerCase());
  const needle = chip.toLowerCase().replace(/[?"“”]/g, "").trim();
  return asked.some((a) => a.replace(/[?"“”]/g, "").trim().includes(needle));
}

/** The newest assistant turn — what the conversation is currently "on". */
function lastAssistant(messages: LedgerMessage[]): LedgerMessage | undefined {
  return [...messages].reverse().find((m) => m.role === "assistant");
}

/** An un-applied, un-dismissed change the analyst has put on the table. */
function hasOpenProposal(messages: LedgerMessage[], appliedIds: ReadonlySet<string>): boolean {
  const last = lastAssistant(messages);
  if (!last?.patchJson || last.dismissed) return false;
  if (isLedgerEvent(last.patchJson)) return false;
  return !appliedIds.has(last.id);
}

function take(candidates: string[], messages: LedgerMessage[]): string[] {
  const seen = new Set<string>();
  return candidates
    .filter((c) => c && !seen.has(c) && (seen.add(c), true))
    .filter((c) => !alreadyAsked(messages, c))
    .slice(0, MAX_SUGGESTIONS);
}

export interface GateSuggestionContext {
  gateStage: 1 | 4;
  artifact: GateArtifact | null;
  messages: LedgerMessage[];
  appliedPatchIds: ReadonlySet<string>;
  /** No more applies allowed at this checkpoint — steer to the exit, not to more edits. */
  applyCapReached: boolean;
  /** At least one change already landed on this checkpoint's framing. */
  hasAppliedChange: boolean;
}

/** G1 (niche framing) / G2 (audience + pains) checkpoint suggestions. */
export function gateSuggestions(ctx: GateSuggestionContext): string[] {
  const { gateStage, artifact, messages, appliedPatchIds, applyCapReached, hasAppliedChange } = ctx;

  // A proposal is on the table: the only useful next questions are about IT.
  if (hasOpenProposal(messages, appliedPatchIds)) {
    return take(
      ["Why is this better?", "What would it exclude?", "Suggest a different change"],
      messages,
    );
  }

  // Out of edits — the remaining action is to move the run forward.
  if (applyCapReached) {
    return take(
      ["What happens next?", "Is this framing good enough to run?"],
      messages,
    );
  }

  if (gateStage === 1) {
    const g1 = artifact as GateG1Artifact | null;
    const segment = g1?.market_segments?.[0];
    const audience = g1?.user_target_audience;
    return take(
      [
        ...(hasAppliedChange ? ["Anything else worth fixing here?"] : []),
        "Is this niche too broad?",
        ...(segment ? [`Should we drop "${short(segment)}"?`] : []),
        ...(audience ? ["Is this the right audience?"] : ["Who exactly are we researching?"]),
        "What will the search look for?",
      ],
      messages,
    );
  }

  // G2 — the pains and segments are the material; name them.
  const g2 = artifact as GateG2Artifact | null;
  const pains = g2?.pains ?? [];
  const weakestPain = [...pains].sort((a, b) => (a.severity ?? 0) - (b.severity ?? 0))[0];
  const topPain = [...pains].sort((a, b) => (b.severity ?? 0) - (a.severity ?? 0))[0];
  const segment = g2?.segments?.[0]?.segment_name;

  return take(
    [
      ...(hasAppliedChange ? ["Anything else worth fixing here?"] : []),
      ...(weakestPain && pains.length > 1
        ? [`Is "${short(weakestPain.title)}" worth keeping?`]
        : []),
      ...(topPain ? [`Why is "${short(topPain.title)}" the top pain?`] : []),
      ...(segment ? [`Should we focus only on ${short(segment)}?`] : []),
      "Which pains would people pay to fix?",
    ],
    messages,
  );
}

export interface SelectionSuggestionContext {
  solutions: SolutionPreview[];
  messages: LedgerMessage[];
  /** Free-culture wallet + no idea cleared a strong market-fit bar. */
  weakPool: boolean;
  /** A regenerate is still affordable/allowed — "give me different ideas" is actionable. */
  canRegenerate: boolean;
  /** The user has already shortlisted at least one candidate. */
  hasSelection: boolean;
  /** Private rationales left by shared-report voters. */
  collaboratorRationaleCount?: number;
  /** A paid pool-mutation op (regenerate, or a chat-composed idea seed being
   *  evaluated) is in flight — the backend only allows one at a time. Suppresses
   *  prompts that would invite a second one, or ask about a shortlist/pool that's
   *  about to change underneath the answer. */
  poolMutationBusy?: boolean;
}

/** G3 (candidate selection) suggestions. */
export function selectionSuggestions(ctx: SelectionSuggestionContext): string[] {
  const { solutions, messages, weakPool, canRegenerate, hasSelection, collaboratorRationaleCount = 0, poolMutationBusy } = ctx;
  // Hosts may pin a seed or analyst pick for visibility. A chip that says "ranked"
  // must derive its own score order instead of turning that presentation order into
  // a research claim.
  const ranked = solutions
    .map((solution) => ({ solution, score: displayCompositeScore(solution) }))
    .filter((entry): entry is { solution: SolutionPreview; score: number } => entry.score !== null)
    .sort((a, b) => {
    const scoreDelta = b.score - a.score;
    return scoreDelta || solutionDisplayTitle(a.solution).localeCompare(solutionDisplayTitle(b.solution));
  });
  const uniqueLeader = ranked[0] && (!ranked[1] || ranked[0].score > ranked[1].score)
    ? ranked[0].solution
    : null;
  const top = uniqueLeader ? solutionDisplayTitle(uniqueLeader) : undefined;
  const comparisonTop = ranked[0] ? solutionDisplayTitle(ranked[0].solution) : undefined;
  const runnerUp = ranked[1] ? solutionDisplayTitle(ranked[1].solution) : undefined;

  return take(
    [
      // The honest question first when the pool itself is the problem.
      ...(weakPool ? ["Should I even proceed with this niche?"] : []),
      ...(collaboratorRationaleCount > 0 ? ["What do collaborators agree or disagree on?"] : []),
      ...(hasSelection && !poolMutationBusy ? ["Is my shortlist the right bet?"] : []),
      ...(top ? [`Why is "${short(top)}" ranked first?`] : []),
      ...(comparisonTop && runnerUp ? [`Compare "${short(comparisonTop, 20)}" and "${short(runnerUp, 20)}"`] : []),
      ...(canRegenerate && !poolMutationBusy ? ["What's missing from these ideas?"] : []),
      ...(top && !poolMutationBusy ? [`How would you narrow "${short(top)}"?`] : []),
      "Which of these is easiest to build?",
    ],
    messages,
  );
}
