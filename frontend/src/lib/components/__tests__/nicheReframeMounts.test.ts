/**
 * The mechanical guard for the failure class that shipped round 1, not a pin on the one
 * mount that was broken.
 *
 * Two ways a disclosure can be correct, well-tested and still disclose nothing:
 *
 *   1. Its data cannot reach it. Round 1 gated on `report.niche_context` and the only
 *      caller passed a synthesized `previewHeroReport` that has no such field. Guarded
 *      here statically: every mount must hand `NicheReframeNote` an expression that reads
 *      `niche_context` off a loaded artifact.
 *   2. Nobody covers the surface, so nothing notices. Guarded here by requiring every
 *      mounting file to be listed below with a test that renders THAT surface through
 *      production wiring; the tests themselves refuse a disclosure buried in an
 *      aria-hidden/inert subtree (`expectDiscloses` in fixtures/nicheReframeSurface.ts).
 *
 * Adding a mount without a wiring test fails this file. That is the point: a new surface
 * is a new chance to render the disclosure where its data — or its reader — cannot follow.
 */
import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SRC_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const SKIP_DIRS = new Set(["node_modules", ".svelte-kit", "dist", "build"]);

/** Mounting file → the spec that renders that surface with a captured run. */
const COVERED_MOUNTS: Record<string, string> = {
  "lib/components/ReportContent.svelte":
    "lib/components/__tests__/nicheReframeSurfaces.test.ts",
  "lib/components/SharedDiscoveryView.svelte":
    "lib/components/__tests__/nicheReframeSurfaces.test.ts",
  "routes/(app)/jobs/[jobId]/+page.svelte":
    "routes/(app)/jobs/[jobId]/__tests__/nicheReframeDisclosure.test.ts",
};

/** The assertion that refuses an unreadable disclosure. A wiring spec that does not call
 *  it is not proving what this registry claims it proves. */
const READABILITY_ASSERTION = "expectDiscloses";

function collect(dir: string, match: RegExp, found: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) collect(full, match, found);
    else if (match.test(entry)) found.push(full);
  }
  return found;
}

const svelteFiles = collect(SRC_ROOT, /\.svelte$/);
const mountsByFile = new Map<string, string[]>();
for (const file of svelteFiles) {
  const source = readFileSync(file, "utf8");
  const tags = [...source.matchAll(/<NicheReframeNote\b([\s\S]*?)\/?>/g)].map((m) => m[1]);
  if (tags.length) mountsByFile.set(relative(SRC_ROOT, file), tags);
}

describe("the reframe disclosure is only mounted where its data and its reader can reach it", () => {
  it("finds the mounts it is meant to police", () => {
    // Guards the guard: a walk that silently returns nothing would pass vacuously, and a
    // renamed component would make every assertion below empty.
    expect(svelteFiles.length).toBeGreaterThan(50);
    expect([...mountsByFile.keys()].sort()).toEqual(Object.keys(COVERED_MOUNTS).sort());
  });

  it("hands every mount a niche_context read off a loaded artifact", () => {
    const offenders: string[] = [];
    for (const [file, tags] of mountsByFile) {
      for (const attrs of tags) {
        const context = /context=\{([^}]*)\}/.exec(attrs)?.[1]?.trim();
        if (!context) {
          offenders.push(`${file}: mount passes no context={…}`);
        } else if (!context.includes("niche_context")) {
          offenders.push(`${file}: context={${context}} does not read niche_context`);
        }
      }
    }

    expect(
      offenders,
      offenders.length
        ? "A mount whose expression does not read `niche_context` off the artifact the " +
          "surface loaded renders nothing, forever, without failing anything — that is " +
          "exactly how round 1 shipped:\n  " + offenders.join("\n  ")
        : undefined,
    ).toEqual([]);
  });

  it("keeps every mount covered by a spec that renders that surface for real", () => {
    const offenders: string[] = [];
    for (const [file] of mountsByFile) {
      const specPath = COVERED_MOUNTS[file];
      if (!specPath) {
        offenders.push(`${file}: mounted with no wiring spec registered`);
        continue;
      }
      let spec: string;
      try {
        spec = readFileSync(join(SRC_ROOT, specPath), "utf8");
      } catch {
        offenders.push(`${file}: registered spec ${specPath} does not exist`);
        continue;
      }
      const surface = file.split("/").pop()!;
      const rendersSurface =
        spec.includes(surface) || spec.includes(surface.replace(/\.svelte$/, ""));
      if (!rendersSurface) {
        offenders.push(`${specPath} never renders ${surface}`);
      }
      if (!spec.includes(READABILITY_ASSERTION)) {
        offenders.push(`${specPath} never calls ${READABILITY_ASSERTION}()`);
      }
    }

    expect(
      offenders,
      offenders.length
        ? "Every surface that mounts the disclosure must have a spec that drives the real " +
          "component/page with a captured run and asserts the rendered text is reachable:\n  " +
          offenders.join("\n  ")
        : undefined,
    ).toEqual([]);
  });
});
