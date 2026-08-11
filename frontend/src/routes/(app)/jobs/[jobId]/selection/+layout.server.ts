import { error, redirect } from "@sveltejs/kit";
import { fetchBackend } from "$lib/backend";
import type { Job, SolutionPreview } from "$lib/types/job";
import type { SelectionDecisionState } from "$lib/types/selectionDecisionState";
import type { SelectionMetricExplanationsResponse } from "$lib/types/selectionMetricExplanation";
import type { FounderFitLoadResponse } from "$lib/types/founderFit";
import type { DiscoveryData } from "$lib/types/discovery";
import type { PreviewReport } from "$lib/types/previewReport";
import type { SelectionConceptSet } from "$lib/types/selectionConceptSet";
import { createDiscoveryDisplayModel } from "$lib/discovery/discoveryDisplay";
import { normalizeSolutionPreviews } from "$lib/utils/displayGuards";
import type { LayoutServerLoad } from "./$types";
import { resolveSelectionWorkspace } from "./selectionWorkspace";

type OptionalArtifact<T> = {
  known: boolean;
  value: T | null;
};

type DecisionStateWithReceipt = SelectionDecisionState & {
  founderFitReceipt?: FounderFitLoadResponse;
};

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function isInteger(value: unknown, minimum = 0): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= minimum;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isOneOf(value: unknown, options: readonly string[]): value is string {
  return typeof value === "string" && options.includes(value);
}

function hasStringFields(record: Record<string, unknown>, fields: readonly string[]): boolean {
  return fields.every((field) => typeof record[field] === "string");
}

function isIdeaReference(value: unknown): boolean {
  const record = objectRecord(value);
  return Boolean(record)
    && typeof record?.ideaId === "string"
    && isInteger(record.ideaRevision, 1)
    && typeof record.title === "string";
}

const challengeLenses = ["demand", "competition", "distribution", "dependencies"] as const;

function isDecisionProfile(value: unknown): boolean {
  const record = objectRecord(value);
  return Boolean(record)
    && isOneOf(record?.preset, ["balanced", "fast_revenue", "solo_bootstrap", "audience_first"])
    && isOneOf(record.weeklyTime, ["under_10", "10_20", "20_40", "full_time"])
    && isOneOf(record.budget, ["under_1k", "1k_5k", "5k_20k", "20k_plus"])
    && isOneOf(record.team, ["solo", "small_team", "funded_team"])
    && (record.buildModel === undefined || isOneOf(record.buildModel, ["self", "contractor"]))
    && isOneOf(record.revenueHorizon, ["30_days", "90_days", "6_months", "patient"])
    && Array.isArray(record.distributionAdvantages)
    && record.distributionAdvantages.every((item) => isOneOf(
      item,
      ["seo", "community", "existing_audience", "outbound", "paid", "partnerships"],
    ))
    && typeof record.strengths === "string"
    && typeof record.hardConstraints === "string";
}

function isExperimentDraft(value: unknown): boolean {
  const record = objectRecord(value);
  if (!record || !hasStringFields(record, [
    "ideaId", "assumption", "whyCritical", "currentEvidence", "stimulus", "audience",
    "channel", "primaryMetric", "passThreshold", "failThreshold", "measurementWindow",
    "costEstimate", "passAction", "failAction", "flatAction", "invalidAction",
  ])) return false;

  return isInteger(record.ideaRevision, 1)
    && (record.originChallengeId === undefined || record.originChallengeId === null || typeof record.originChallengeId === "string")
    && (record.originQuestionId === undefined || record.originQuestionId === null || typeof record.originQuestionId === "string")
    && (record.assumptionId === undefined || record.assumptionId === null || typeof record.assumptionId === "string")
    && isOneOf(record.assumptionType, ["DESIRABILITY", "USABILITY", "FEASIBILITY", "VIABILITY", "ETHICS"])
    && isOneOf(record.method, [
      "CUSTOMER_INTERVIEWS", "SURVEY", "CTA_SMOKE_TEST", "BOOKED_CALL", "PREORDER",
      "CONCIERGE", "PROTOTYPE", "TECHNICAL_SPIKE", "OTHER",
    ])
    && isOneOf(record.evidenceSignal, [
      "LANGUAGE", "STATED_PREFERENCE", "CTA_INTEREST", "SMALL_COMMITMENT", "PAYMENT_INTENT", "USAGE",
    ])
    && (record.sampleTarget === null || isInteger(record.sampleTarget, 1));
}

function isFounderFitArtifact(value: unknown): boolean {
  const artifact = objectRecord(value);
  if (!artifact
    || artifact.version !== 1
    || !hasStringFields(artifact, ["inputFingerprint", "model", "createdAt"])
    || !isDecisionProfile(artifact.profileSnapshot)
    || !Array.isArray(artifact.ideaSnapshots)
    || !artifact.ideaSnapshots.every((item) => objectRecord(item) !== null)
    || !Array.isArray(artifact.results)) return false;

  return artifact.results.every((candidate) => {
    const result = objectRecord(candidate);
    if (!result || !hasStringFields(result, [
      "ideaId", "ideaTitle", "summary", "strongestAdvantage", "decisionChangingUnknown", "sensitivity",
    ])) return false;

    return isInteger(result.ideaRevision, 1)
      && isOneOf(result.verdict, ["fits", "needs_reshape", "blocked", "insufficient_evidence"])
      && (result.blockingConflict === null || typeof result.blockingConflict === "string")
      && Array.isArray(result.dimensions)
      && result.dimensions.every((candidateDimension) => {
        const dimension = objectRecord(candidateDimension);
        return Boolean(dimension)
          && isOneOf(dimension?.dimension, [
            "time", "budget", "team", "revenue_horizon", "distribution", "strengths", "hard_constraints",
          ])
          && isOneOf(dimension.status, ["aligned", "conflict", "unknown", "irrelevant"])
          && typeof dimension.summary === "string"
          && isStringArray(dimension.profileFields)
          && isStringArray(dimension.ideaFields);
      })
      && isExperimentDraft(result.suggestedExperiment);
  });
}

function isFounderFitReceipt(value: unknown): boolean {
  const receipt = objectRecord(value);
  return Boolean(receipt)
    && typeof receipt?.stale === "boolean"
    && (receipt.analysis === null || isFounderFitArtifact(receipt.analysis));
}

function isNextAction(value: unknown): boolean {
  const action = objectRecord(value);
  if (!action) return false;
  return isOneOf(action.kind, [
    "select_candidate", "add_decision_context", "analyze_founder_fit", "stress_test_evidence",
    "capture_assumption", "draft_test", "review_test_brief", "launch_test", "monitor_test",
    "record_conclusion", "start_deep_research",
  ])
    && isOneOf(action.target, [
      "shortlist", "profile", "founder_fit", "challenges", "assumptions", "experiments", "deep_research",
    ])
    && typeof action.reason === "string"
    && typeof action.required === "boolean"
    && (action.variant === undefined || isOneOf(action.variant, ["rerun", "refresh"]))
    && Array.isArray(action.ideas)
    && action.ideas.every(isIdeaReference)
    && (action.lens === null || isOneOf(action.lens, challengeLenses))
    && Array.isArray(action.records)
    && action.records.every((candidate) => {
      const record = objectRecord(candidate);
      return Boolean(record)
        && isOneOf(record?.kind, ["challenge", "owner_evidence", "assumption", "experiment", "conclusion"])
        && typeof record.id === "string"
        && (record.version === undefined || isInteger(record.version, 1));
    });
}

function isDecisionStateWithReceipt(value: unknown): value is DecisionStateWithReceipt {
  const state = objectRecord(value);
  const shortlist = objectRecord(state?.shortlist);
  const founderFit = objectRecord(state?.founderFit);
  const staleCounts = objectRecord(state?.staleCounts);
  const deepResearch = objectRecord(state?.deepResearch);
  if (!state
    || state.schemaVersion !== 1
    || typeof state.jobId !== "string"
    || typeof state.status !== "string"
    || !shortlist
    || !isInteger(shortlist.version)
    || (shortlist.fingerprint !== undefined && typeof shortlist.fingerprint !== "string")
    || !Array.isArray(shortlist.items)
    || !shortlist.items.every(isIdeaReference)
    || (shortlist.staleItems !== undefined && (
      !Array.isArray(shortlist.staleItems)
      || !shortlist.staleItems.every((candidate) => {
        const item = objectRecord(candidate);
        return Boolean(item)
          && typeof item?.ideaId === "string"
          && isInteger(item.ideaRevision, 1)
          && (item.titleSnapshot === undefined || typeof item.titleSnapshot === "string");
      })
    ))
    || (state.profile !== null && !isDecisionProfile(state.profile))
    || (state.founderFit !== null && (
      !founderFit
      || typeof founderFit.inputFingerprint !== "string"
      || !Array.isArray(founderFit.results)
      || !founderFit.results.every((candidate) => {
        const result = objectRecord(candidate);
        if (!result) return false;
        return isIdeaReference(result.idea)
          && isOneOf(result.verdict, ["fits", "needs_reshape", "blocked", "insufficient_evidence"]);
      })
    ))
    || !Array.isArray(state.challenges)
    || !state.challenges.every((candidate) => {
      const challenge = objectRecord(candidate);
      return Boolean(challenge)
        && typeof challenge?.id === "string"
        && isIdeaReference(challenge.idea)
        && isOneOf(challenge.lens, challengeLenses)
        && isOneOf(challenge.overall, ["withstands", "weakened", "contradicted", "disputed", "insufficient_evidence"])
        && isStringArray(challenge.gapQuestionIds);
    })
    || !Array.isArray(state.ownerEvidence)
    || !state.ownerEvidence.every((candidate) => {
      const evidence = objectRecord(candidate);
      if (!evidence) return false;
      return hasStringFields(evidence, ["id", "kind", "position", "title"])
        && isIdeaReference(evidence.idea)
        && isOneOf(evidence.lens, challengeLenses);
    })
    || !Array.isArray(state.assumptions)
    || !state.assumptions.every((candidate) => {
      const assumption = objectRecord(candidate);
      if (!assumption) return false;
      return hasStringFields(assumption, ["id", "statement", "impact", "ownerState"])
        && isIdeaReference(assumption.idea)
        && isOneOf(assumption.lens, challengeLenses)
        && isInteger(assumption.version, 1)
        && (assumption.originChallengeId === null || typeof assumption.originChallengeId === "string")
        && (assumption.originQuestionId === null || typeof assumption.originQuestionId === "string")
        && isStringArray(assumption.experimentIds);
    })
    || !Array.isArray(state.experiments)
    || !state.experiments.every((candidate) => {
      const experiment = objectRecord(candidate);
      if (!experiment) return false;
      return hasStringFields(experiment, ["id", "status"])
        && isIdeaReference(experiment.idea)
        && (experiment.assumptionId === null || typeof experiment.assumptionId === "string")
        && (experiment.runStatus === null || typeof experiment.runStatus === "string")
        && (experiment.conclusionId === null || typeof experiment.conclusionId === "string");
    })
    || !Array.isArray(state.conclusions)
    || !state.conclusions.every((candidate) => {
      const conclusion = objectRecord(candidate);
      return Boolean(conclusion)
        && hasStringFields(conclusion!, ["id", "experimentId", "outcome"])
        && isIdeaReference(conclusion?.idea);
    })
    || !staleCounts
    || !["shortlist", "profile", "founderFit", "challenges", "ownerEvidence", "assumptions", "experiments", "conclusions", "total"]
      .every((field) => isInteger(staleCounts[field]))
    || !deepResearch
    || typeof deepResearch.eligible !== "boolean"
    || deepResearch.optionalWorkRequired !== false
    || !Array.isArray(deepResearch.blockers)
    || !deepResearch.blockers.every((blocker) => isOneOf(blocker, [
      "JOB_NOT_AWAITING_SELECTION", "NO_CURRENT_SHORTLIST", "STALE_SHORTLIST",
    ]))
    || !isNextAction(state.nextAction)
    || (state.founderFitReceipt !== undefined && !isFounderFitReceipt(state.founderFitReceipt))) {
    return false;
  }
  return true;
}

async function loadOptionalArtifact<T>(request: Promise<Response>): Promise<OptionalArtifact<T>> {
  try {
    const response = await request;
    if (response.status === 204 || response.status === 404) {
      return { known: true, value: null };
    }
    if (!response.ok) {
      return { known: false, value: null };
    }
    try {
      return { known: true, value: await response.json() as T };
    } catch {
      return { known: false, value: null };
    }
  } catch {
    return { known: false, value: null };
  }
}

export const load: LayoutServerLoad = async ({ params, locals, url, parent }) => {
  const session = await locals.auth();
  if (!session?.user) throw error(401, "Unauthorized");

  // Grant comes from the (app) layout load, which fetches it fresh per navigation.
  const { featureAccess } = await parent();
  const decisionTools = featureAccess?.decisionTools === true;
  // /selection/risks IS the evidence-check tool. Without the grant it has nothing to
  // render and every fetch on it 403s, so send the owner to the compare view instead
  // of a half-empty page. Deep links and stale bookmarks both land here.
  if (!decisionTools && url.pathname.endsWith("/selection/risks")) {
    redirect(307, `/jobs/${params.jobId}/selection/compare${url.search}`);
  }

  const headers = { "X-User-ID": session.user.id };
  const jobResponse = await fetchBackend(`/api/jobs/${params.jobId}`, { headers });
  if (!jobResponse.ok) {
    if (jobResponse.status === 404) throw error(404, "Job not found");
    const payload = await jobResponse.json().catch(() => ({ error: "Failed to load research" }));
    throw error(jobResponse.status, payload.error || "Failed to load research");
  }

  const job = (await jobResponse.json()) as Job;
  let normalizedSolutions = normalizeSolutionPreviews(job.solutionIdeas);
  let solutions: SolutionPreview[] = normalizedSolutions.solutions;
  let verifiedPreviewReport: PreviewReport | null = null;
  let verifiedPreviewReportKnown = false;
  // The job page already tells the owner when run artifacts are withheld. Every
  // /selection/* route reads the same boundary, so it must be able to say the same
  // thing instead of rendering an empty overlap gate as if nothing were missing.
  let artifactVerification: "verified" | "untrusted" | null = null;
  let artifactReason: string | null = null;
  // `job.solutionIdeas` is deliberately omitted by the backend during selection states,
  // so a failed /solutions read leaves an EMPTY list that looks like a finished result.
  let solutionsUnavailable = false;
  // Saved directions remain a decision-tool-only workspace.
  const shouldPrefetchConceptSets = decisionTools && url.pathname.endsWith("/selection/compare");
  const shouldFetchSampleReport = url.pathname.endsWith("/selection/review");

  // stageCosts + creditBalance are inherited from the (app) layout load — no need
  // to re-fetch them on every selection navigation.
  const [
    solutionsResponse,
    decisionStateResponse,
    metricResponse,
    discoveryDataArtifact,
    conceptSetsArtifact,
    sampleReportResponse,
  ] = await Promise.all([
    fetchBackend(`/api/jobs/${params.jobId}/solutions`, { headers }).catch(() => null),
    fetchBackend(`/api/jobs/${params.jobId}/selection-decision-state`, { headers }).catch(() => null),
    fetchBackend("/api/selection/metric-explanations", { headers }).catch(() => null),
    loadOptionalArtifact<DiscoveryData>(
      fetchBackend(`/api/jobs/${params.jobId}/discovery-data`, { headers }),
    ),
    shouldPrefetchConceptSets
      ? loadOptionalArtifact<{ sets: SelectionConceptSet[] }>(
          fetchBackend(`/api/jobs/${params.jobId}/selection-concept-sets`, { headers }),
        )
      : Promise.resolve({ known: false, value: null }),
    shouldFetchSampleReport
      ? fetchBackend("/api/settings/sample-report-url").catch(() => null)
      : Promise.resolve(null),
  ]);
  if (solutionsResponse?.ok) {
    const payload = await solutionsResponse.json().catch(() => null);
    if (payload && typeof payload === "object" && "solutionIdeas" in payload) {
      normalizedSolutions = normalizeSolutionPreviews(payload.solutionIdeas);
      solutions = normalizedSolutions.solutions;
      const previewReport = "previewReport" in payload
        ? objectRecord(payload.previewReport)
        : null;
      artifactVerification = payload.artifactVerification === "verified"
        ? "verified"
        : "untrusted";
      artifactReason = typeof payload.artifactReason === "string" ? payload.artifactReason : null;
      if (artifactVerification === "verified" && previewReport) {
        verifiedPreviewReport = previewReport as PreviewReport;
        verifiedPreviewReportKnown = true;
      }
    } else {
      solutionsUnavailable = true;
    }
  } else {
    solutionsUnavailable = true;
  }

  const decisionStatePayload: unknown = decisionStateResponse?.ok
    ? await decisionStateResponse.json().catch(() => null)
    : null;
  const decisionState = isDecisionStateWithReceipt(decisionStatePayload)
    ? decisionStatePayload
    : null;
  const metricExplanations = metricResponse?.ok
    ? await metricResponse.json().catch(() => null) as SelectionMetricExplanationsResponse | null
    : null;
  // The owner-only decision-state projection carries the complete historical artifact.
  // Reading a receipt therefore survives a revoked decision-tools grant; only the routes
  // that create new founder-fit output remain grant-gated.
  const founderFit = decisionState?.founderFitReceipt ?? null;
  const sampleReportAvailable = sampleReportResponse?.ok
    ? Boolean((await sampleReportResponse.json().catch(() => null))?.url)
    : false;
  const conceptSets = Array.isArray(conceptSetsArtifact.value?.sets)
    ? conceptSetsArtifact.value.sets
    : null;
  const discoverySectionsKnown = discoveryDataArtifact.known && verifiedPreviewReportKnown;
  const availableSectionIds = discoverySectionsKnown
    ? createDiscoveryDisplayModel(
        verifiedPreviewReport,
        discoveryDataArtifact.value,
      ).availableSectionIds
    : undefined;

  const workspaceUrl = url.pathname.endsWith("/selection/review")
    ? new URL(url.pathname, url.origin)
    : url;

  return {
    job,
    solutions,
    decisionState,
    metricExplanations,
    founderFit,
    conceptSets,
    // Same-product idea groups come from the pool/version/fingerprint-verified
    // /solutions snapshot, never the raw preview compatibility endpoint.
    overlapGroups: verifiedPreviewReport?.overlap_groups ?? [],
    availableSectionIds,
    decisionTools,
    sampleReportAvailable,
    // Same boundary verdict the job page projects, so both surfaces can report the
    // same withheld state in the same words instead of degrading silently.
    artifactVerification,
    artifactReason,
    selectionLoadState: {
      // Duplicate-idea grouping, the discovery dossier, and every other pool-scoped
      // framing come from the verified /solutions snapshot. Untrusted means they are
      // absent by design, which the owner must be told rather than left to infer from
      // an empty duplicate gate on /selection/review.
      evidenceFramingWithheld: artifactVerification === "untrusted",
      solutionsUnavailable,
      decisionStateUnavailable: !decisionStateResponse?.ok || decisionState === null,
      metricExplanationsUnavailable: !metricResponse?.ok || metricExplanations === null,
      // Missing on a granted workspace means the decision-state read failed or an older
      // backend omitted the receipt. Without the grant, the general decision-state outage
      // indicator is enough; absence must not masquerade as a feature failure.
      founderFitUnavailable: decisionTools && founderFit === null,
      invalidSolutionCount: normalizedSolutions.invalidCount,
    },
    // Review is the committed saved shortlist. Query refs remain useful on
    // Compare/Evidence, but may never redefine the paid transaction scope.
    workspace: resolveSelectionWorkspace(workspaceUrl, job, solutions),
  };
};
