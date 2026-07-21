import { describe, it, expect } from 'vitest';
import {
  isGatePatch,
  isLedgerEvent,
  isIdeaSynthesisPatch,
  isNewIdeaSeedPatch,
  isIdeaFocusPatch,
  type ChatPatch,
} from '../api';

// The four ChatPatch narrowers must partition the union exhaustively — a patch that
// slips past all four (and would previously have silently rendered as an idea-focus
// proposal) is the bug plans/eager-meandering-feather.md's "exhaustive dispatch"
// fix closes. `assertNever` callers (ChatThread's proposalRows/applyPatch) rely on
// exactly one narrower matching per patch.
const gatePatch: ChatPatch = {
  gateStage: 1,
  patch: { niche_description: 'Solo consultants' },
  rationale: 'Too broad',
};

const ideaFocusPatch: ChatPatch = {
  idea_focus: 'novelty',
  rationale: 'More novel angles',
};

const ledgerEventPatch: ChatPatch = {
  kind: 'ledger_event',
  version: 1,
  event: 'gate_patch_applied',
  patch: { niche_description: 'Solo consultants' },
  rows: [{ label: 'Niche description', value: 'Solo consultants' }],
  sourceMessageId: 'asst-1',
};

const seedPatch: ChatPatch = {
  kind: 'new_idea_seed',
  free_text: 'A tool that reconciles invoices automatically',
  pain_ref: 'Chasing late invoices',
  rationale: 'Matches a validated pain with no direct incumbent',
};

const synthesisPatch: ChatPatch = {
  kind: 'idea_synthesis',
  operation: 'narrow',
  proposedTitle: 'Focused reconciler',
  proposedBrief: 'Invoice reconciliation for solo agencies.',
  changeSummary: 'Narrows the buyer.',
  rationale: 'The source candidate is too broad.',
  parents: [{
    ideaId: 'idea-1',
    ideaRevision: 1,
    solutionName: 'Invoice reconciler',
    contribution: 'Keep automatic reconciliation.',
  }],
  evidence: {
    sourceAnchors: [{ ideaId: 'idea-1', ideaRevision: 1, candidateSnapshotSha256: 'a'.repeat(64), pain: 'Late invoices' }],
    requiresValidation: ['Validate solo-agency demand.'],
  },
  newAssumptions: ['Solo agencies will pay.'],
};

describe('ChatPatch narrowers — exhaustive partition', () => {
  it('isGatePatch matches only the gate patch', () => {
    expect(isGatePatch(gatePatch)).toBe(true);
    expect(isGatePatch(ideaFocusPatch)).toBe(false);
    expect(isGatePatch(ledgerEventPatch)).toBe(false);
    expect(isGatePatch(seedPatch)).toBe(false);
    expect(isGatePatch(synthesisPatch)).toBe(false);
  });

  it('isLedgerEvent matches only the ledger-event envelope', () => {
    expect(isLedgerEvent(ledgerEventPatch)).toBe(true);
    expect(isLedgerEvent(gatePatch)).toBe(false);
    expect(isLedgerEvent(ideaFocusPatch)).toBe(false);
    expect(isLedgerEvent(seedPatch)).toBe(false);
    expect(isLedgerEvent(synthesisPatch)).toBe(false);
  });

  it('isNewIdeaSeedPatch matches only the new_idea_seed patch', () => {
    expect(isNewIdeaSeedPatch(seedPatch)).toBe(true);
    expect(isNewIdeaSeedPatch(gatePatch)).toBe(false);
    expect(isNewIdeaSeedPatch(ideaFocusPatch)).toBe(false);
    expect(isNewIdeaSeedPatch(ledgerEventPatch)).toBe(false);
    expect(isNewIdeaSeedPatch(synthesisPatch)).toBe(false);
  });

  it('isIdeaSynthesisPatch matches only the synthesis proposal', () => {
    expect(isIdeaSynthesisPatch(synthesisPatch)).toBe(true);
    expect(isIdeaSynthesisPatch(seedPatch)).toBe(false);
    expect(isIdeaSynthesisPatch(gatePatch)).toBe(false);
    expect(isIdeaSynthesisPatch(ideaFocusPatch)).toBe(false);
  });

  it('isIdeaFocusPatch matches only the idea-focus patch — the one that used to be an implicit `else`', () => {
    expect(isIdeaFocusPatch(ideaFocusPatch)).toBe(true);
    expect(isIdeaFocusPatch(gatePatch)).toBe(false);
    expect(isIdeaFocusPatch(ledgerEventPatch)).toBe(false);
    expect(isIdeaFocusPatch(seedPatch)).toBe(false);
    expect(isIdeaFocusPatch(synthesisPatch)).toBe(false);
  });

  it('every patch matches EXACTLY one narrower — the exhaustiveness property the assertNever dispatch depends on', () => {
    const narrowers = [isGatePatch, isLedgerEvent, isNewIdeaSeedPatch, isIdeaSynthesisPatch, isIdeaFocusPatch];
    for (const patch of [gatePatch, ideaFocusPatch, ledgerEventPatch, seedPatch, synthesisPatch]) {
      const matches = narrowers.filter((fn) => fn(patch)).length;
      expect(matches).toBe(1);
    }
  });
});
