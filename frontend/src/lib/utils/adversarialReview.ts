type AdversarialReviewFields = {
  incumbent_parity?: string | null;
  red_team_verdict?: string | null;
  red_team_caveats?: string[] | null;
};

export interface AdversarialReviewFinding {
  label: string;
  details: string[];
}

const EVIDENCE_PREFIX = /^shipped by evidence\s*:\s*/i;

export function isAdversarialEvidenceParity(value: string | null | undefined): boolean {
  return EVIDENCE_PREFIX.test(value?.trim() ?? "");
}

export function directIncumbentParity(
  idea: Pick<AdversarialReviewFields, "incumbent_parity">,
): string | null {
  const parity = idea.incumbent_parity?.trim();
  if (
    !parity
    || parity.toLowerCase().startsWith("none")
    || isAdversarialEvidenceParity(parity)
  ) {
    return null;
  }
  return parity;
}

export function noDirectIncumbentFound(
  idea: Pick<AdversarialReviewFields, "incumbent_parity">,
): boolean {
  return idea.incumbent_parity?.trim().toLowerCase().startsWith("none") ?? false;
}

export function adversarialReviewFinding(
  idea: AdversarialReviewFields,
): AdversarialReviewFinding | null {
  const verdict = idea.red_team_verdict?.trim();
  const parity = idea.incumbent_parity?.trim();
  const evidenceDetail = isAdversarialEvidenceParity(parity)
    ? parity!.replace(EVIDENCE_PREFIX, "").trim()
    : "";
  const details = [...(idea.red_team_caveats ?? []), evidenceDetail]
    .map((detail) => detail.trim())
    .filter((detail, index, all) => detail && all.indexOf(detail) === index);

  const killed = verdict?.toLowerCase() === "killed";
  if (!killed && !evidenceDetail) return null;

  const verdictLabel = verdict
    ? verdict.charAt(0).toUpperCase() + verdict.slice(1).toLowerCase()
    : null;
  return {
    label: verdictLabel ? `Adversarial review: ${verdictLabel}` : "Adversarial review",
    details,
  };
}
