/**
 * The frontend half of the three-implementation fingerprint contract.
 *
 * `ideaPortfolioFingerprint` exists in three places — here, in
 * `backend/src/utils/ideaPortfolioFingerprint.ts`, and in Python's
 * `idea_portfolio_fingerprint` — and a disagreement of one rule between any two of them
 * flips `portfolioSummaryIsCurrent` to false, which is the round-14 defect that killed the
 * analyst summary in production.
 *
 * The cases are NOT written here. They live once, in
 * `contracts/ideaPortfolioFingerprintCases.json`, and all three suites read that file — a
 * copy-pasted table let a deliberate lockstep edit (change one implementation and its own
 * copy of the table) leave the other two undetected. The expectations in the file are
 * literal strings, never a re-implemented hash: a mirrored helper would follow a contract
 * change silently.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { SolutionPreview } from "$lib/types/job";

import { ideaPortfolioFingerprint } from "../ideaPortfolioFingerprint";

type SharedCase = {
  name: string;
  candidates: Array<Record<string, unknown> | null>;
  fingerprint: string | null;
};
type DivergenceCase = {
  name: string;
  candidates: Array<Record<string, unknown> | null>;
  fingerprint: { python: string | null; typescript: string | null };
};

// `fileURLToPath`, not `new URL(..., import.meta.url)`: Vite rewrites that literal into an
// asset URL, and readFileSync then rejects it with "The URL must be of scheme file".
const CONTRACT_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../contracts/ideaPortfolioFingerprintCases.json",
);
const CONTRACT = JSON.parse(readFileSync(CONTRACT_PATH, "utf8")) as {
  shared: SharedCase[];
  divergences: DivergenceCase[];
};

/** The wire admits `idea_revision: null` and a null element; the TS type does not. */
function pool(candidates: Array<Record<string, unknown> | null>): SolutionPreview[] {
  return candidates as unknown as SolutionPreview[];
}

describe("ideaPortfolioFingerprint — contract shared with the backend and Python", () => {
  it("reads the same case file the backend and Python suites read", () => {
    // A suite that silently loses its cases proves nothing; the count is the tripwire.
    expect(CONTRACT.shared.length).toBeGreaterThanOrEqual(11);
    expect(CONTRACT.divergences.length).toBeGreaterThanOrEqual(2);
  });

  for (const testCase of CONTRACT.shared) {
    it(testCase.name, () => {
      expect(ideaPortfolioFingerprint(pool(testCase.candidates)))
        .toBe(testCase.fingerprint);
    });
  }

  // Known, documented, non-blocking: the two cases where the languages cannot agree.
  // Pinned so a future change that "fixes" one of them has to say so out loud.
  for (const testCase of CONTRACT.divergences) {
    it(`known divergence — ${testCase.name}`, () => {
      expect(ideaPortfolioFingerprint(pool(testCase.candidates)))
        .toBe(testCase.fingerprint.typescript);
    });
  }
});
