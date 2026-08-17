/**
 * WHERE the Stage-1 reframe disclosure renders, on the two reader-facing surfaces that
 * are whole components: the completed Deep Research report (`ReportContent`, mounted by
 * /jobs/[jobId]/report, /shared/[shareToken] and /sample-report) and the shared discovery
 * view (`SharedDiscoveryView`, mounted by /shared/discovery/[shareToken]).
 *
 * Both are driven the way production drives them — one whole artifact object in, rendered
 * DOM out. Nothing here hand-builds a `niche_context`: the captures are script-sliced from
 * real runs (see their `_provenance`), and both surfaces read the field off the same
 * artifact their existing copy already reads.
 *
 * The completed report is the surface that most needs this. It labels itself with the
 * SUBMITTED text — `nicheName` reads `niche_context.niche_input` — while every finding
 * beneath was researched against the wider derived market.
 */
import { cleanup, render } from "@testing-library/svelte";
import { page } from "$app/state";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Report } from "$lib/types/report";
import type { DiscoveryShareData } from "$lib/api";
import ReportContent from "../ReportContent.svelte";
import SharedDiscoveryView from "../SharedDiscoveryView.svelte";
import {
  ON_NICHE_RUN,
  REFRAMED_RUN,
  type CapturedRun,
  expectDiscloses,
  expectSilent,
} from "./fixtures/nicheReframeSurface";

const originalUrl = page.url;

beforeEach(() => {
  page.url = new URL("http://localhost/report") as typeof page.url;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
});

afterEach(() => {
  cleanup();
  page.url = originalUrl;
  vi.unstubAllGlobals();
  localStorage.clear();
});

/** The artifact as the report route hands it over: the captured run itself. */
function reportOf(run: CapturedRun): Report {
  return run as unknown as Report;
}

/** The payload GET /api/shares/discovery/:token returns; `niche_context` is a
 *  niche-scoped preview field (backend routes/schemas/sharedDiscoveryPayload.ts), so it
 *  is served even when the candidate pool has gone stale. */
function shareOf(run: CapturedRun): DiscoveryShareData {
  return {
    shareType: "discovery",
    niche: run.niche,
    solutions: [],
    discoveryData: null,
    previewReport: run as unknown as DiscoveryShareData["previewReport"],
    voteSummary: { totalVotes: 0, solutionVotes: {} },
  } as DiscoveryShareData;
}

describe("completed report discloses a Stage-1 reframe", () => {
  it("names the submitted input on a report researched against a wider market", () => {
    const view = render(ReportContent, { props: { report: reportOf(REFRAMED_RUN) } });

    expectDiscloses(view.container, REFRAMED_RUN);
  });

  it("says nothing on a report whose niche is the one the user named", () => {
    const view = render(ReportContent, { props: { report: reportOf(ON_NICHE_RUN) } });

    expectSilent(view.container);
  });

  it("keeps the disclosure on the deeper report views, not just the brief", () => {
    // `compactIdentity` strips the deck and the context meta on every view except the
    // brief; the disclosure must not be stripped with them.
    page.url = new URL(
      "http://localhost/report?view=evidence&topic=market&detail=full",
    ) as typeof page.url;

    const view = render(ReportContent, { props: { report: reportOf(REFRAMED_RUN) } });

    expectDiscloses(view.container, REFRAMED_RUN);
  });
});

describe("shared discovery view discloses a Stage-1 reframe", () => {
  it("names the submitted input to a visitor who never chose it", () => {
    const view = render(SharedDiscoveryView, {
      props: { data: shareOf(REFRAMED_RUN), shareToken: "share-token" },
    });

    expectDiscloses(view.container, REFRAMED_RUN);
  });

  it("says nothing when the shared run researched the niche as submitted", () => {
    const view = render(SharedDiscoveryView, {
      props: { data: shareOf(ON_NICHE_RUN), shareToken: "share-token" },
    });

    expectSilent(view.container);
  });

  it("stays silent on a share whose preview report was withheld entirely", () => {
    // The backend serves no preview fields for an untrusted artifact snapshot. No
    // evidence either way is not a licence to guess.
    const withheld = { ...shareOf(REFRAMED_RUN), previewReport: null };

    const view = render(SharedDiscoveryView, {
      props: { data: withheld as DiscoveryShareData, shareToken: "share-token" },
    });

    expectSilent(view.container);
    expect(view.container.textContent).not.toContain("You asked about");
  });
});
