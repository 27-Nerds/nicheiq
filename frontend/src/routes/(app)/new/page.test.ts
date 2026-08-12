import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { page } from "$app/state";

import NewResearchPage from "./+page.svelte";

const ALL_NAMED_TYPES = [
  "saas",
  "directory",
  "aggregator",
  "comparison-tool",
  "marketplace",
];

function pageData() {
  return {
    catalogPainPoints: [],
    hasCatalogData: false,
    sampleReportAvailable: false,
  };
}

function jobsPayload(fetchMock: ReturnType<typeof vi.fn>): Record<string, unknown> {
  const call = fetchMock.mock.calls.find(([url]) => url === "/api/jobs");
  expect(call).toBeDefined();
  return JSON.parse((call![1] as RequestInit).body as string);
}

async function enterPitch(text: string) {
  await fireEvent.input(screen.getByRole("textbox"), { target: { value: text } });
}

async function submitPrimaryCta(container: HTMLElement) {
  const button = container.querySelector<HTMLButtonElement>(".submit-btn");
  expect(button).not.toBeNull();
  await fireEvent.click(button!);
}

describe("/new project-shape constraints", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (page as any).url = new URL("http://localhost/new");
    (page as any).data = {
      ...(page as any).data,
      creditBalance: 100,
      stageCosts: {
        discovery: 5,
        deep_research: 15,
        landing_page: 5,
        regenerate_ideas: 2,
        seed_idea: 3,
      },
      billingLoadState: {
        discoveryCostUnavailable: false,
        guidedCostsUnavailable: false,
      },
    };
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the Product shape filter in exploration, but not when checking an arbitrary idea", async () => {
    const view = render(NewResearchPage, { props: { data: pageData() as never } });

    await fireEvent.click(view.getByRole("button", { name: /Research setup/ }));
    expect(view.getByRole("button", { name: /Product shape filter/ })).toBeInTheDocument();

    await fireEvent.click(view.getByRole("radio", { name: /Check my idea/ }));
    expect(view.queryByRole("button", { name: /Product shape filter/ })).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: /Business model filter/ })).not.toBeInTheDocument();
  });

  it("omits the constraint when all named shapes are selected", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "job-all" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const view = render(NewResearchPage, { props: { data: pageData() as never } });

    await enterPitch("Independent veterinary clinics managing medication inventory");
    await submitPrimaryCta(view.container);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/jobs", expect.any(Object)));
    expect(jobsPayload(fetchMock)).not.toHaveProperty("allowedProjectTypes");
  });

  it("submits the exact narrowed subset in exploration mode", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "job-subset" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const view = render(NewResearchPage, { props: { data: pageData() as never } });

    await fireEvent.click(view.getByRole("button", { name: /Research setup/ }));
    await fireEvent.click(view.getByRole("button", { name: /Product shape filter/ }));
    await fireEvent.click(view.getByRole("button", { name: "Directory" }));
    await enterPitch("Independent veterinary clinics managing medication inventory");
    await submitPrimaryCta(view.container);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/jobs", expect.any(Object)));
    expect(jobsPayload(fetchMock).allowedProjectTypes).toEqual(
      ALL_NAMED_TYPES.filter((type) => type !== "directory"),
    );
  });

  it("does not leak a stale exploration subset into Check my idea", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === "/api/suggest") {
        return new Response(JSON.stringify({
          clarify: {
            parse_confidence: "high",
            fields: {
              audience: { value: "shop owners", confidence: "high", guess: null },
              problem: { value: "slow replies", confidence: "high", guess: null },
              delivery: { value: "browser extension", confidence: "high", guess: null },
            },
            questions: [],
          },
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ id: "job-validate" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const view = render(NewResearchPage, { props: { data: pageData() as never } });

    await fireEvent.click(view.getByRole("button", { name: /Research setup/ }));
    await fireEvent.click(view.getByRole("button", { name: /Product shape filter/ }));
    await fireEvent.click(view.getByRole("button", { name: "Directory" }));
    await fireEvent.click(view.getByRole("radio", { name: /Check my idea/ }));
    await enterPitch(
      "A browser extension that drafts concise customer-support replies for independent shops",
    );
    await submitPrimaryCta(view.container);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/jobs", expect.any(Object)));
    const payload = jobsPayload(fetchMock);
    expect(payload.entryMode).toBe("validate_idea");
    expect(payload).not.toHaveProperty("allowedProjectTypes");
  });
});
