import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * A test that cannot LOAD is not a failing test — vitest reports it as a failed
 * *file* contributing "no tests", so the assertion count silently drops and the
 * suite still looks healthy. The way that happens here is a test importing a real
 * pipeline artifact out of `output/`, which is gitignored: it resolves on the
 * machine that produced the run and nowhere else.
 *
 * SharedDiscoveryView.test.ts did exactly this and put six assertions at risk.
 * The fix is to vendor the handful of fields a test actually reads into a
 * `__tests__/fixtures/*.captured.json` file that records the source `file` and
 * JSON `path` for each value (see discoveryCommunities.captured.json). Do that
 * instead of reaching back into `output/`.
 */

const SRC_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

const TEST_FILE = /\.(test|spec)\.(ts|js)$/;
const SKIP_DIRS = new Set(["node_modules", ".svelte-kit", "dist", "build"]);

/** `from "x"`, `import("x")`, `vi.mock("x")` — the ways a spec pulls in a module. */
const SPECIFIER =
  /(?:\bfrom\s*|\bimport\s*\(\s*|\bvi\s*\.\s*(?:mock|doMock)\s*\(\s*)["']([^"']+)["']/g;

/** Gitignored artifact trees. Reaching into these is what makes a spec unloadable. */
const GITIGNORED_TREE = /(?:^|\/)(?:output|\.venv|coverage)\//;

function collectTestFiles(dir: string, found: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) collectTestFiles(full, found);
    else if (TEST_FILE.test(entry)) found.push(full);
  }
  return found;
}

function escapesSrc(fromFile: string, specifier: string): boolean {
  if (!specifier.startsWith(".")) return false;
  const resolved = resolve(dirname(fromFile), specifier);
  const rel = relative(SRC_ROOT, resolved);
  return rel.startsWith("..") || rel.startsWith(`..${sep}`);
}

describe("test files never import from outside src/", () => {
  const testFiles = collectTestFiles(SRC_ROOT);

  it("finds the test files it is meant to police", () => {
    // Guards the guard: a walk that silently returns nothing would pass vacuously.
    expect(testFiles.length).toBeGreaterThan(50);
    expect(testFiles.some((f) => f.endsWith("SharedDiscoveryView.test.ts"))).toBe(true);
  });

  it("has no import that escapes src/ or reaches into a gitignored artifact tree", () => {
    const offenders: string[] = [];

    for (const file of testFiles) {
      const source = readFileSync(file, "utf8");
      for (const [, specifier] of source.matchAll(SPECIFIER)) {
        const reason = escapesSrc(file, specifier)
          ? "resolves outside src/"
          : GITIGNORED_TREE.test(specifier)
            ? "reaches into a gitignored artifact tree"
            : null;
        if (reason) {
          offenders.push(`${relative(SRC_ROOT, file)} imports "${specifier}" — ${reason}`);
        }
      }
    }

    expect(
      offenders,
      offenders.length
        ? `A spec importing an ungitignored path fails to LOAD on a clean checkout, which vitest ` +
          `reports as "no tests" rather than a failure — the assertions just disappear from the ` +
          `totals. Vendor the fields you need into a __tests__/fixtures/*.captured.json recording ` +
          `the source file and JSON path for each value:\n  ${offenders.join("\n  ")}`
        : undefined,
    ).toEqual([]);
  });
});
