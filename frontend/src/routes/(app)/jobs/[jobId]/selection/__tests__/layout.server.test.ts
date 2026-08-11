import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchBackend: vi.fn(),
}));

vi.mock("$lib/backend", () => ({
  fetchBackend: mocks.fetchBackend,
}));

import { load } from "../+layout.server";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function event(route = "compare", decisionTools = true) {
  return {
    params: { jobId: "job-1" },
    locals: {
      auth: vi.fn().mockResolvedValue({ user: { id: "user-1" } }),
    },
    url: new URL(`https://nicheiq.test/jobs/job-1/selection/${route}`),
    // The (app) layout resolves the admin-granted feature flags.
    parent: vi.fn().mockResolvedValue({ featureAccess: { analyst: true, decisionTools } }),
  } as never;
}

function job() {
  return {
    id: "job-1",
    status: "AWAITING_SELECTION",
    solutionIdeas: [],
    assets: [],
  };
}

function validDecisionState(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 1,
    jobId: "job-1",
    status: "AWAITING_SELECTION",
    shortlist: {
      version: 7,
      fingerprint: "opaque-shortlist-fingerprint",
      items: [],
      staleItems: [],
    },
    profile: null,
    founderFit: null,
    challenges: [],
    ownerEvidence: [],
    assumptions: [],
    experiments: [],
    conclusions: [],
    staleCounts: {
      shortlist: 0,
      profile: 0,
      founderFit: 0,
      challenges: 0,
      ownerEvidence: 0,
      assumptions: 0,
      experiments: 0,
      conclusions: 0,
      total: 0,
    },
    deepResearch: {
      eligible: true,
      optionalWorkRequired: false,
      blockers: [],
    },
    nextAction: {
      kind: "start_deep_research",
      target: "deep_research",
      reason: "The saved shortlist is ready.",
      required: false,
      ideas: [],
      lens: null,
      records: [],
    },
    ...overrides,
  };
}

function founderFitArtifact() {
  return {
    version: 1,
    inputFingerprint: "founder-fit-fingerprint",
    profileSnapshot: {
      preset: "balanced",
      weeklyTime: "10_20",
      budget: "under_1k",
      team: "solo",
      revenueHorizon: "90_days",
      distributionAdvantages: ["community"],
      strengths: "Domain expertise",
      hardConstraints: "No enterprise sales",
    },
    ideaSnapshots: [{ idea_id: "idea-a", idea_revision: 3 }],
    model: "test-model",
    createdAt: "2026-08-09T12:00:00.000Z",
    results: [{
      ideaId: "idea-a",
      ideaRevision: 3,
      ideaTitle: "Signal desk",
      verdict: "needs_reshape",
      summary: "The full scope exceeds the saved time budget.",
      strongestAdvantage: "The founder already reaches the target buyers.",
      blockingConflict: "The weekly workload is too high.",
      decisionChangingUnknown: "Whether a narrower brief retains enough value.",
      sensitivity: "A smaller scope would improve the fit.",
      dimensions: [{
        dimension: "time",
        status: "conflict",
        summary: "The current scope needs more than the available time.",
        profileFields: ["weeklyTime"],
        ideaFields: ["estimated_development_time"],
      }],
      suggestedExperiment: {
        ideaId: "idea-a",
        ideaRevision: 3,
        originChallengeId: null,
        originQuestionId: null,
        assumptionId: null,
        assumptionType: "DESIRABILITY",
        assumption: "Buyers value a narrower weekly brief.",
        whyCritical: "The narrower scope is the only feasible version.",
        currentEvidence: "",
        method: "CUSTOMER_INTERVIEWS",
        evidenceSignal: "LANGUAGE",
        stimulus: "Show a sample narrow brief.",
        audience: "Five target buyers",
        channel: "Existing community",
        primaryMetric: "Buyers asking for the next brief",
        passThreshold: "Three of five ask for another",
        failThreshold: "Fewer than two ask for another",
        measurementWindow: "One week",
        sampleTarget: 5,
        costEstimate: "0 credits",
        passAction: "Proceed with the narrow scope.",
        failAction: "Drop the idea.",
        flatAction: "Interview a second segment.",
        invalidAction: "Recruit a qualified sample.",
      },
    }],
  };
}

function mockDecisionStateResponse(body: unknown) {
  mocks.fetchBackend.mockImplementation((path: string) => {
    if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
    if (path === "/api/jobs/job-1/solutions") {
      return Promise.resolve(response({ solutionIdeas: [] }));
    }
    if (path === "/api/jobs/job-1/selection-decision-state") {
      return Promise.resolve(response(body));
    }
    return Promise.resolve(response(null, 404));
  });
}

function deeplyMalformedDecisionState() {
  return validDecisionState({
    nextAction: {
      kind: "start_deep_research",
      target: "deep_research",
      reason: "The saved shortlist is ready.",
      required: false,
      ideas: [],
      lens: null,
      records: [{ kind: "challenge", id: "challenge-1", version: "one" }],
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("selection layout Discovery navigation", () => {
  it("resolves Review from the verified saved draft when the generic job omits selection data", async () => {
    const seed = {
      idea_id: "idea-seed",
      idea_revision: 1,
      solution_name: "AccreditedVetMapper",
      description: "The submitted idea.",
      value_proposition: "Validate the submitted workflow.",
      source_frame: "user_seed",
      generation_operation_id: "validate",
    };
    const alternative = {
      idea_id: "idea-alt",
      idea_revision: 2,
      solution_name: "Same-Day Careboard",
      description: "A current alternative.",
      value_proposition: "Coordinate same-day care.",
    };
    const shortlist = {
      version: 8,
      fingerprint: "alternative-fingerprint",
      items: [{ ideaId: "idea-alt", ideaRevision: 2, title: "Same-Day Careboard" }],
      staleItems: [],
    };

    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        // Production selection shape: the generic endpoint intentionally omits
        // both solutionIdeas and selectionDraft.
        return Promise.resolve(response({
          id: "job-1",
          status: "AWAITING_SELECTION",
          entryMode: "validate_idea",
          assets: [],
        }));
      }
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [seed, alternative],
          selectionDraft: {
            version: 8,
            items: [{ ideaId: "idea-alt", ideaRevision: 2 }],
          },
          artifactVerification: "verified",
          artifactReason: null,
          previewReport: { detailed_pain_points: [] },
        }));
      }
      if (path === "/api/jobs/job-1/selection-decision-state") {
        return Promise.resolve(response(validDecisionState({ shortlist })));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.job).not.toHaveProperty("solutionIdeas");
    expect(result.job.selectionDraft).toEqual({
      version: 8,
      items: [{ ideaId: "idea-alt", ideaRevision: 2 }],
    });
    expect(result.workspace.scopeSource).toBe("draft");
    expect(result.workspace.ideas.map(
      (entry: Record<string, unknown>) => entry.idea_id,
    )).toEqual(["idea-alt"]);
  });

  it("fails closed when the authoritative saved draft is malformed", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response({
          id: "job-1",
          status: "AWAITING_SELECTION",
          entryMode: "validate_idea",
          assets: [],
        }));
      }
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [],
          selectionDraft: { version: "wrong", items: [] },
          artifactVerification: "verified",
          previewReport: { detailed_pain_points: [] },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    await expect(load(event("review"))).rejects.toMatchObject({ status: 502 });
  });

  it("prefetches saved directions with the Compare route's parallel data", async () => {
    const sets = [{ id: "set-1" }];
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      if (path === "/api/jobs/job-1/selection-concept-sets") {
        return Promise.resolve(response({ sets }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event());
    if (!result) throw new Error("Expected selection layout data");

    expect(result.conceptSets).toEqual(sets);
  });

  it("does not fetch saved directions for unrelated selection routes", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("risks"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.conceptSets).toBeNull();
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/selection-concept-sets",
      expect.anything(),
    );
  });

  it("keeps overlap warnings and section navigation from the verified selection snapshot", async () => {
    const overlapGroups = [{
      group_id: "group-1",
      idea_names: ["Signal desk", "Signal monitor"],
      overlap_type: "same_product",
      explanation: "Both ideas solve the same buyer workflow.",
    }];
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [],
          artifactVerification: "verified",
          previewReport: {
            detailed_pain_points: [{ title: "Pain", severity_score: 0.8 }],
            overlap_groups: overlapGroups,
          },
        }));
      }
      if (path === "/api/jobs/job-1/discovery-data") {
        return Promise.resolve(response(null, 404));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event());
    if (!result) throw new Error("Expected selection layout data");

    expect(result.overlapGroups).toEqual(overlapGroups);
    expect(result.availableSectionIds).toEqual(["overview", "pain-points"]);
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/preview-report",
      expect.anything(),
    );
  });

  // Finding D2, tertiary defect: seven untrusted-artifact states emptied overlapGroups
  // and availableSectionIds with zero user-visible signal, while the job page showed a
  // banner for the SAME job. /selection/review is the worst case: its duplicate-idea gate
  // charges on `overlapGroups`, so a legacy job lost it permanently and silently.
  it("reports the untrusted artifact state instead of degrading silently", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [{
            idea_id: "idea-signal",
            idea_revision: 1,
            solution_name: "Signal desk",
            description: "Watches the queue",
            value_proposition: "Fewer missed handoffs",
          }],
          artifactVerification: "untrusted",
          artifactReason: "legacy_missing_version",
          previewReport: null,
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.artifactVerification).toBe("untrusted");
    expect(result.artifactReason).toBe("legacy_missing_version");
    expect(result.selectionLoadState.evidenceFramingWithheld).toBe(true);
    expect(result.selectionLoadState.solutionsUnavailable).toBe(false);
    // The candidate list itself stays current and usable; only claims about it are gone.
    expect(result.solutions).toHaveLength(1);
    expect(result.overlapGroups).toEqual([]);
    expect(result.availableSectionIds).toBeUndefined();
  });

  it("leaves the withheld flag down on a verified snapshot", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [],
          artifactVerification: "verified",
          artifactReason: null,
          previewReport: { detailed_pain_points: [] },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event());
    if (!result) throw new Error("Expected selection layout data");

    expect(result.artifactVerification).toBe("verified");
    expect(result.selectionLoadState.evidenceFramingWithheld).toBe(false);
    expect(result.selectionLoadState.solutionsUnavailable).toBe(false);
  });

  // The backend OMITS job.solutionIdeas during selection states (jobs.ts), so a failed
  // /solutions read leaves an EMPTY list that renders as a finished, candidate-free run.
  it("flags a failed candidate request rather than presenting an empty pool", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.reject(new Error("network unavailable"));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.solutions).toEqual([]);
    expect(result.selectionLoadState.solutionsUnavailable).toBe(true);
    expect(result.artifactVerification).toBeNull();
  });

  it("flags a malformed candidate payload the same way as a transport failure", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ unexpected: true }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.selectionLoadState.solutionsUnavailable).toBe(true);
  });

  it("rejects a non-array candidate catalog before accepting its saved draft", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: null,
          selectionDraft: {
            version: 7,
            items: [{ ideaId: "seed-1", ideaRevision: 1 }],
          },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.solutions).toEqual([]);
    expect(result.job.selectionDraft).toBeNull();
    expect(result.selectionLoadState.solutionsUnavailable).toBe(true);
  });

  it("blocks Review when normalization discards any authoritative candidate row", async () => {
    const seed = {
      idea_id: "seed-1",
      idea_revision: 1,
      solution_name: "Submitted Idea",
      description: "The submitted idea.",
      source_frame: "user_seed",
      generation_operation_id: "validate",
    };
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response({ ...job(), entryMode: "validate_idea" }));
      }
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [
            seed,
            { idea_id: "seed-1", idea_revision: 1, description: "Malformed collision." },
          ],
          selectionDraft: {
            version: 7,
            items: [{ ideaId: "seed-1", ideaRevision: 1 }],
          },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.solutions).toEqual([]);
    expect(result.job.selectionDraft).toBeNull();
    expect(result.selectionLoadState.invalidSolutionCount).toBe(1);
    expect(result.selectionLoadState.solutionsUnavailable).toBe(true);
  });

  it("rejects a generic job projection for a different route identity", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response({ ...job(), id: "job-2" }));
      }
      return Promise.resolve(response(null, 404));
    });

    await expect(load(event("review"))).rejects.toMatchObject({ status: 502 });
  });

  it("rejects a strict validation seed when the job omits validation entry mode", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [{
            idea_id: "seed-1",
            idea_revision: 1,
            solution_name: "Submitted Idea",
            source_frame: "user_seed",
            generation_operation_id: "validate",
          }],
          selectionDraft: { version: 7, items: [{ ideaId: "seed-1", ideaRevision: 1 }] },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    await expect(load(event("review"))).rejects.toMatchObject({ status: 502 });
  });

  it("blocks Review instead of trimming whitespace in candidate identity", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response({ ...job(), entryMode: "validate_idea" }));
      }
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [
            { idea_id: "seed-1", idea_revision: 1, solution_name: "Submitted seed" },
            { idea_id: "seed-1 ", idea_revision: 1, solution_name: "Different product" },
          ],
          selectionDraft: { version: 7, items: [{ ideaId: "seed-1 ", ideaRevision: 1 }] },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");
    expect(result.job.selectionDraft).toBeNull();
    expect(result.selectionLoadState.solutionsUnavailable).toBe(true);
    expect(result.selectionLoadState.invalidSolutionCount).toBeGreaterThan(0);
  });

  it("rejects revisions outside JavaScript's exact integer range", async () => {
    const unsafeRevision = Number.MAX_SAFE_INTEGER + 1;
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [{
            idea_id: "idea-unsafe",
            idea_revision: unsafeRevision,
            solution_name: "Unsafe revision",
          }],
          selectionDraft: {
            version: 7,
            items: [{ ideaId: "idea-unsafe", ideaRevision: unsafeRevision }],
          },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");
    expect(result.job.selectionDraft).toBeNull();
    expect(result.selectionLoadState.solutionsUnavailable).toBe(true);
    expect(result.selectionLoadState.invalidSolutionCount).toBeGreaterThan(0);
  });

  it("does not treat a failed verified selection request as an empty dossier", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.reject(new Error("network unavailable"));
      }
      if (path === "/api/jobs/job-1/discovery-data") {
        return Promise.resolve(response(null, 404));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event());
    if (!result) throw new Error("Expected selection layout data");

    expect(result.availableSectionIds).toBeUndefined();
  });
});

describe("selection layout decision-tools gate", () => {
  it("redirects /risks to /compare without the grant", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      return Promise.resolve(response(null, 404));
    });

    await expect(load(event("risks", false))).rejects.toMatchObject({
      status: 307,
      location: "/jobs/job-1/selection/compare",
    });
  });

  it("serves /compare without the grant, skipping creation-tool fetches", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("compare", false));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionTools).toBe(false);
    expect(result.founderFit).toBeNull();
    expect(result.conceptSets).toBeNull();
    // Not fetched means not failed: the banner must stay down.
    expect(result.selectionLoadState.founderFitUnavailable).toBe(false);
    for (const gated of ["/api/jobs/job-1/selection-concept-sets"]) {
      expect(mocks.fetchBackend).not.toHaveBeenCalledWith(gated, expect.anything());
    }
  });

  it("reads the full historical founder-fit receipt after the grant is revoked", async () => {
    const artifact = founderFitArtifact();
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      if (path === "/api/jobs/job-1/selection-decision-state") {
        return Promise.resolve(response(validDecisionState({
          founderFitReceipt: { analysis: artifact, stale: false },
        })));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("review", false));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionTools).toBe(false);
    expect(result.founderFit).toEqual({ analysis: artifact, stale: false });
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/founder-fit",
      expect.anything(),
    );
  });

  it("uses the decision-state receipt for a granted owner too", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      if (path === "/api/jobs/job-1/selection-decision-state") {
        return Promise.resolve(response(validDecisionState({
          founderFitReceipt: { analysis: null, stale: false },
        })));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("compare", true));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionTools).toBe(true);
    expect(result.founderFit).toEqual({ analysis: null, stale: false });
    expect(result.selectionLoadState.founderFitUnavailable).toBe(false);
  });
});

describe("selection decision-state boundary validation", () => {
  it("preserves a valid decision-state projection", async () => {
    const payload = validDecisionState();
    mockDecisionStateResponse(payload);

    const result = await load(event("compare"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionState).toEqual(payload);
    expect(result.selectionLoadState.decisionStateUnavailable).toBe(false);
  });

  it("marks a malformed non-null payload as a load failure", async () => {
    mockDecisionStateResponse({ schemaVersion: 1, decisionState: "not-a-projection" });

    const result = await load(event("compare"));
    if (!result) throw new Error("Expected selection layout data");

    expect(
      result.decisionState,
      "boundary validation must reject malformed non-null decision state",
    ).toBeNull();
    expect(result.selectionLoadState.decisionStateUnavailable).toBe(true);
  });

  it("fails closed when shortlist is missing", async () => {
    const { shortlist: _shortlist, ...payload } = validDecisionState();
    mockDecisionStateResponse(payload);

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionState).toBeNull();
    expect(result.selectionLoadState.decisionStateUnavailable).toBe(true);
  });

  it("fails closed when deepResearch is missing", async () => {
    const { deepResearch: _deepResearch, ...payload } = validDecisionState();
    mockDecisionStateResponse(payload);

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionState).toBeNull();
    expect(result.selectionLoadState.decisionStateUnavailable).toBe(true);
  });

  it("fails closed when deepResearch eligibility has the wrong type", async () => {
    const payload = validDecisionState({
      deepResearch: {
        eligible: "yes",
        optionalWorkRequired: false,
        blockers: [],
      },
    });
    mockDecisionStateResponse(payload);

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionState).toBeNull();
    expect(result.selectionLoadState.decisionStateUnavailable).toBe(true);
  });

  it("rejects a deeply nested wrong-type record version that a boundary cast would accept", async () => {
    mockDecisionStateResponse(deeplyMalformedDecisionState());

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(
      result.decisionState,
      "replacing boundary validation with a cast would expose the malformed projection",
    ).toBeNull();
    expect(result.selectionLoadState.decisionStateUnavailable).toBe(true);
  });

  it("treats a null body as unavailable without throwing", async () => {
    mockDecisionStateResponse(null);

    const result = await load(event("review"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionState).toBeNull();
    expect(result.selectionLoadState.decisionStateUnavailable).toBe(true);
  });
});
