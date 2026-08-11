import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Guard, not a sweep.
 *
 * `labels.ts` carries a binding copy rule in its own header ("No em or en dashes
 * anywhere in this module") that nothing enforced. This test enforces it, and
 * extends it to the sibling modules that are ALSO hand-authored client copy and
 * are already clean, so a new dash cannot arrive in them unnoticed.
 *
 * COVERED: the modules listed below. Every one of them is a copy/label module -
 * strings written by us and shown to the reader.
 *
 * DELIBERATELY NOT COVERED, and why:
 * - `buyerFacingResearchProse.ts`. It is the sanitiser for PIPELINE prose; its
 *   constants are dash patterns by design, because matching and rewriting a dash
 *   requires containing one. Covering it would make the guard un-passable.
 * - `evaluationProgress.svelte.ts`. It has two authored dashes today (lines 72
 *   and 85). Rewording verified copy to satisfy a new lint is backwards, so it
 *   stays out of the list and the sites are reported to the owner instead.
 * - `.svelte` components. Inline markup copy is out of scope for this guard: an
 *   em dash in hand-written component copy is a house-style inconsistency, and
 *   the one mechanical sweep this program ran over such copy caused a defect.
 * - Code comments in the covered modules. Only string and template literals are
 *   scanned, so a dash in prose ABOUT the code never trips the guard.
 */
const COVERED_MODULES = [
  "labels.ts",
  "decisionJourney.ts",
  "overlapWarnings.ts",
  "founderFitLabels.ts",
  "profileFormat.ts",
  "rankedIdeas.ts",
  "workspaceLifecycle.ts",
  "workspaceTools.ts",
  "addScopeMenu.ts",
  "toolOrigin.ts",
  "founderFitScope.ts",
  "ideaPortfolioFingerprint.ts",
] as const;

const EM_DASH = "—";
const EN_DASH = "–";

/**
 * Every string / template literal in the source, with its 1-based line number.
 *
 * Hand-rolled rather than regex-matched because the two things that must never
 * be confused - a literal and a comment - can each contain the other's opening
 * token. A regex that strips `//` comments first would silently swallow the rest
 * of any line containing a URL inside a string.
 */
function stringLiterals(source: string): Array<{ line: number; text: string }> {
  const found: Array<{ line: number; text: string }> = [];
  let line = 1;
  let i = 0;

  while (i < source.length) {
    const ch = source[i];
    const next = source[i + 1];

    if (ch === "\n") { line += 1; i += 1; continue; }

    if (ch === "/" && next === "/") {
      while (i < source.length && source[i] !== "\n") i += 1;
      continue;
    }
    if (ch === "/" && next === "*") {
      i += 2;
      while (i < source.length && !(source[i] === "*" && source[i + 1] === "/")) {
        if (source[i] === "\n") line += 1;
        i += 1;
      }
      i += 2;
      continue;
    }

    if (ch === '"' || ch === "'" || ch === "`") {
      const quote = ch;
      const startLine = line;
      let text = "";
      i += 1;
      while (i < source.length && source[i] !== quote) {
        if (source[i] === "\\") { text += source.slice(i, i + 2); i += 2; continue; }
        if (source[i] === "\n") line += 1;
        text += source[i];
        i += 1;
      }
      i += 1;
      found.push({ line: startLine, text });
      continue;
    }

    i += 1;
  }

  return found;
}

/** Vitest runs with `frontend/` as its root, so the modules resolve from cwd. */
const SELECTION_DIR = "src/lib/selection";

describe("selection copy modules carry no em or en dashes", () => {
  it.each(COVERED_MODULES)("%s", (moduleName) => {
    const source = readFileSync(resolve(SELECTION_DIR, moduleName), "utf8");
    const offenders = stringLiterals(source)
      .filter(({ text }) => text.includes(EM_DASH) || text.includes(EN_DASH))
      .map(({ line, text }) => `${moduleName}:${line} ${text}`);

    expect(offenders).toEqual([]);
  });

  it("scans literals only, never the prose in comments", () => {
    const withDashInComment = `// a comment with an em dash ${EM_DASH} here\nconst a = "clean";`;
    expect(stringLiterals(withDashInComment).map((entry) => entry.text)).toEqual(["clean"]);

    const withDashInLiteral = `const a = "copy with ${EM_DASH} a dash";`;
    expect(stringLiterals(withDashInLiteral)[0].text).toContain(EM_DASH);
  });

  it("does not let a URL inside a literal hide the rest of its line", () => {
    const source = `const a = "https://example.test/x"; const b = "trailing ${EN_DASH} dash";`;
    const offenders = stringLiterals(source).filter(({ text }) => text.includes(EN_DASH));
    expect(offenders).toHaveLength(1);
  });
});
