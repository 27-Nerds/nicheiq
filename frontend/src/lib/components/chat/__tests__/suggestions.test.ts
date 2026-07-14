import { describe, it, expect } from "vitest";
import { gateSuggestions, selectionSuggestions } from "../suggestions";
import type { LedgerMessage } from "$lib/stores/chatLedger.svelte";
import type { GateG1Artifact, GateG2Artifact, SolutionPreview } from "$lib/types/job";

const NONE = new Set<string>();

const g1: GateG1Artifact = {
  type: "niche_validation",
  niche_description: "Solo consultants juggling client invoices",
  market_segments: ["Independent consultants", "Boutique agencies"],
  industry_boundaries: null,
  user_target_audience: "Solo consultants",
};

const g2: GateG2Artifact = {
  type: "audience_mapping_gate",
  pains: [
    { title: "Chasing late invoices", severity: 0.9, opportunity: null },
    { title: "Formatting PDFs by hand", severity: 0.3, opportunity: null },
  ],
  segments: [
    { segment_name: "Solo consultants", size_estimate: "Large", payability_class: "high", payability_score: 0.8 },
  ],
  primary_target: "Solo consultants",
};

function userTurn(content: string): LedgerMessage {
  return { id: `u-${content}`, gateStage: 4, role: "user", content };
}

function proposal(id = "a1"): LedgerMessage {
  return {
    id,
    gateStage: 4,
    role: "assistant",
    content: "Here's a change.",
    patchJson: {
      gateStage: 4,
      patch: { pain_scope: { excluded_titles: ["x"], pinned_titles: [] } },
      rationale: "why",
    },
  };
}

const baseGate = { appliedPatchIds: NONE, applyCapReached: false, hasAppliedChange: false };

describe("gateSuggestions — grounded in this checkpoint's real content", () => {
  it("names the actual market segment at the niche checkpoint", () => {
    const out = gateSuggestions({ ...baseGate, gateStage: 1, artifact: g1, messages: [] });
    expect(out).toContain('Should we drop "Independent consultants"?');
    expect(out.length).toBeLessThanOrEqual(3);
  });

  it("names the real pains at the audience checkpoint — top one and the weakest", () => {
    const out = gateSuggestions({ ...baseGate, gateStage: 4, artifact: g2, messages: [] });
    // The weakest pain is the one worth questioning; the strongest is worth understanding.
    expect(out).toContain('Is "Formatting PDFs by hand" worth keeping?');
    expect(out).toContain('Why is "Chasing late invoices" the top pain?');
  });

  it("pivots to the proposal on the table instead of unrelated openers", () => {
    const out = gateSuggestions({
      ...baseGate,
      gateStage: 4,
      artifact: g2,
      messages: [userTurn("exclude the PDF pain"), proposal()],
    });
    expect(out).toEqual(["Why is this better?", "What would it exclude?", "Suggest a different change"]);
  });

  it("stops suggesting edits once the change budget is spent — steers to the exit", () => {
    const out = gateSuggestions({
      ...baseGate,
      gateStage: 4,
      artifact: g2,
      messages: [],
      applyCapReached: true,
    });
    expect(out).toEqual(["What happens next?", "Is this framing good enough to run?"]);
  });

  it("offers a follow-up sweep once a change has landed", () => {
    const out = gateSuggestions({ ...baseGate, gateStage: 4, artifact: g2, messages: [], hasAppliedChange: true });
    expect(out[0]).toBe("Anything else worth fixing here?");
  });

  it("never re-suggests something the user already asked", () => {
    const out = gateSuggestions({
      ...baseGate,
      gateStage: 4,
      artifact: g2,
      messages: [userTurn('Why is "Chasing late invoices" the top pain?')],
    });
    expect(out).not.toContain('Why is "Chasing late invoices" the top pain?');
  });

  it("degrades gracefully when the artifact is missing", () => {
    const out = gateSuggestions({ ...baseGate, gateStage: 1, artifact: null, messages: [] });
    expect(out.length).toBeGreaterThan(0);
    expect(out.every((s) => typeof s === "string" && s.length > 0)).toBe(true);
  });
});

const solutions = [
  { solution_name: "Invoice Chaser" },
  { solution_name: "PDF Formatter" },
] as unknown as SolutionPreview[];

const baseSel = { messages: [], weakPool: false, canRegenerate: false, hasSelection: false };

describe("selectionSuggestions — grounded in the actual ranking and open actions", () => {
  it("names the top-ranked candidate", () => {
    const out = selectionSuggestions({ ...baseSel, solutions });
    expect(out).toContain('Why is "Invoice Chaser" ranked first?');
  });

  it("leads with the honest question when the pool itself is weak", () => {
    const out = selectionSuggestions({ ...baseSel, solutions, weakPool: true });
    expect(out[0]).toBe("Should I even proceed with this niche?");
  });

  it("asks what's missing only when a regenerate is actually available", () => {
    const without = selectionSuggestions({ ...baseSel, solutions });
    const with_ = selectionSuggestions({ ...baseSel, solutions, canRegenerate: true });
    expect(without).not.toContain("What's missing from these ideas?");
    expect(with_).toContain("What's missing from these ideas?");
  });

  it("asks about the shortlist once the user has made one", () => {
    const out = selectionSuggestions({ ...baseSel, solutions, hasSelection: true });
    expect(out).toContain("Is my shortlist the right bet?");
  });

  it("works with an empty candidate list", () => {
    const out = selectionSuggestions({ ...baseSel, solutions: [] });
    expect(out).toEqual(["Which of these is easiest to build?"]);
  });

  it("suppresses the regenerate invite while a paid pool-mutation op is in flight", () => {
    const out = selectionSuggestions({ ...baseSel, solutions, canRegenerate: true, poolMutationBusy: true });
    expect(out).not.toContain("What's missing from these ideas?");
  });

  it("suppresses the shortlist question too — the pool it's about may be about to change", () => {
    const out = selectionSuggestions({ ...baseSel, solutions, hasSelection: true, poolMutationBusy: true });
    expect(out).not.toContain("Is my shortlist the right bet?");
  });

  it("still asks the honest weak-pool question even while busy — that one isn't misleading", () => {
    const out = selectionSuggestions({ ...baseSel, solutions, weakPool: true, poolMutationBusy: true });
    expect(out[0]).toBe("Should I even proceed with this niche?");
  });
});
