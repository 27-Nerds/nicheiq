import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Every `${API_BASE}/...` call in api.ts goes through a SvelteKit proxy route that adds
 * the internal-service auth headers. A backend endpoint plus a client function is NOT a
 * working feature: without the matching `+server.ts` the browser request 404s.
 *
 * This is invisible to component tests, which mock api.ts wholesale — the Concept Forge
 * discard shipped broken for exactly that reason. This test is the missing guard.
 */

const API_TS = "src/lib/api.ts";
const ROUTES_ROOT = "src/routes/api";

/** Client paths with no proxy route ON PURPOSE. Adding a caller means adding a route. */
const KNOWN_UNROUTED = new Set([
  // Dead exports: getReportUrl / getLandingPageUrl build download hrefs but nothing
  // calls them. If you start using either, add the proxy route first — the URL they
  // return does not currently resolve.
  "/jobs/*/report",
  "/jobs/*/landing",
]);

function clientPaths(): Set<string> {
  const source = readFileSync(API_TS, "utf8");
  const paths = new Set<string>();
  for (const match of source.matchAll(/\$\{API_BASE\}([^`'"]*)/g)) {
    const path = match[1]
      .split("?")[0]
      .replace(/\$\{[^}]*\}/g, "*")
      .trim()
      .replace(/\/+$/, "");
    // A `*` glued to the end of a segment (`annotations${query}`) is an interpolated
    // suffix, not a segment. A `*` that IS the whole segment (`/discovery/${token}`)
    // is a real route param, so only strip the glued form.
    if (path.startsWith("/")) paths.add(path.replace(/([^/])\*$/, "$1").replace(/\/+$/, ""));
  }
  return paths;
}

function proxyRoutes(dir: string, prefix = ""): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      const segment = entry.replace(/\[\[?\.\.\.[^\]]*\]\]?/, "**").replace(/\[[^\]]*\]/, "*");
      found.push(...proxyRoutes(full, `${prefix}/${segment}`));
    } else if (entry === "+server.ts") {
      found.push(prefix || "/");
    }
  }
  return found;
}

describe("api.ts proxy coverage", () => {
  it("has a SvelteKit proxy route for every backend path the client calls", () => {
    const routes = proxyRoutes(ROUTES_ROOT);
    const covered = (path: string) => routes.some((route) =>
      route === path
      || (route.includes("**") && path.startsWith(route.split("**")[0])));

    const missing = [...clientPaths()]
      .filter((path) => path && !covered(path) && !KNOWN_UNROUTED.has(path))
      .sort();

    expect(missing).toEqual([]);
  });

  it("keeps the allowlist honest — a listed path must still be unrouted", () => {
    // Otherwise the allowlist silently outlives the gap it documents.
    const routes = proxyRoutes(ROUTES_ROOT);
    for (const path of KNOWN_UNROUTED) {
      expect(routes, `${path} now has a route; drop it from KNOWN_UNROUTED`)
        .not.toContain(path);
    }
  });
});
