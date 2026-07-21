import type {
  SelectionChallenge,
  SelectionChallengeConsensus,
  SelectionChallengeLens,
  SelectionChallengeQuestion,
} from "$lib/types/selectionChallenge";

export const SELECTION_CHALLENGE_LENSES: Array<{
  value: SelectionChallengeLens;
  label: string;
  description: string;
}> = [
  { value: "demand", label: "Customer demand", description: "Pain, urgency, and willingness to pay" },
  { value: "distribution", label: "Reachability", description: "Audience access and acquisition friction" },
  { value: "competition", label: "Competition", description: "Substitutes, switching, and defensibility" },
  { value: "dependencies", label: "Dependencies", description: "Data, integrations, platforms, and compliance" },
];

export const SELECTION_CHALLENGE_QUESTION_LABELS: Record<string, string> = {
  pain_is_observed: "Is the pain directly observed?",
  urgency_is_behavioral: "Does behavior show urgency?",
  buyer_will_pay: "Is willingness to pay evidenced?",
  substitutes_are_weak: "Are current substitutes meaningfully weak?",
  switching_barrier_is_surmountable: "Can buyers realistically switch?",
  wedge_is_defensible: "Is the initial wedge defensible?",
  audience_is_reachable: "Can the audience be reached?",
  channel_matches_observed_behavior: "Do proposed channels match observed behavior?",
  acquisition_friction_is_plausible: "Is acquisition friction plausible for the customer value?",
  required_data_is_obtainable: "Is required data obtainable?",
  critical_integrations_are_available: "Are critical integrations available?",
  platform_and_compliance_risk_is_bounded: "Are platform and compliance risks bounded?",
};

export const SELECTION_CHALLENGE_ASSUMPTIONS: Record<string, string> = {
  pain_is_observed: "The target customer repeatedly experiences this pain in the stated workflow.",
  urgency_is_behavioral: "The pain is urgent enough to produce observable workaround behavior.",
  buyer_will_pay: "Qualified buyers will make a concrete payment commitment for this outcome.",
  substitutes_are_weak: "Current substitutes leave an important outcome unresolved.",
  switching_barrier_is_surmountable: "Qualified buyers can adopt this solution without prohibitive switching cost.",
  wedge_is_defensible: "The initial product wedge can remain differentiated after launch.",
  audience_is_reachable: "The target audience can be reached through a repeatable channel.",
  channel_matches_observed_behavior: "The proposed channel matches where the audience already seeks solutions.",
  acquisition_friction_is_plausible: "The acquisition effort is plausible for the expected customer value.",
  required_data_is_obtainable: "The data required for the core promise can be obtained reliably.",
  critical_integrations_are_available: "Critical integrations can support the required workflow.",
  platform_and_compliance_risk_is_bounded: "Platform and compliance risks can be bounded before launch.",
};

export const SELECTION_RISK_PRIORITY: Record<SelectionChallengeConsensus, number> = {
  contradicted: 0,
  disputed: 1,
  mixed: 2,
  insufficient: 3,
  supported: 4,
};

export function selectionChallengeConsensusLabel(consensus: SelectionChallengeConsensus): string {
  return {
    supported: "Supported",
    contradicted: "Contradicted",
    mixed: "Mixed",
    disputed: "Disputed",
    insufficient: "Not established",
  }[consensus];
}

export function actionableSelectionQuestion(
  challenge: SelectionChallenge,
): SelectionChallengeQuestion | null {
  return [...challenge.questions]
    .filter((question) => question.consensus !== "supported")
    .sort((left, right) => (
      SELECTION_RISK_PRIORITY[left.consensus] - SELECTION_RISK_PRIORITY[right.consensus]
    ))[0] ?? null;
}
