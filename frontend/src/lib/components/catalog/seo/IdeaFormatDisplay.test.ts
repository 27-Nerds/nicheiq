import { render } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import type { IdeaPreview } from "$lib/types/catalog-landing";
import IdeaCardV2 from "./IdeaCardV2.svelte";
import IdeaHeroV2 from "./IdeaHeroV2.svelte";

vi.mock("$app/state", () => ({
  page: { url: new URL("https://example.test/idea/reply-draft") },
}));

vi.mock("../SaveButton.svelte", async () => ({
  default: (await import("./SurfaceStub.test.svelte")).default,
}));

function idea(overrides: Partial<IdeaPreview> = {}): IdeaPreview {
  return {
    id: "idea-1",
    slug: "reply-draft-browser-extension",
    solution_name: "Reply Draft",
    headline: "Draft support replies where agents work",
    short_description: "Drafts support replies without leaving the inbox.",
    description: "Drafts support replies without leaving the inbox.",
    value_proposition: "Reply faster.",
    project_type: "saas",
    format: "browser-extension",
    delivery_format: "browser-extension",
    core_features: [],
    target_personas: [],
    differentiation_factors: [],
    pricing_strategy: null,
    estimated_development_time: null,
    market_fit_score: null,
    technical_feasibility_score: null,
    seo_scalability_score: null,
    novelty_score: null,
    solo_dev_feasibility: null,
    estimated_cac_organic: null,
    programmatic_seo_opportunity: null,
    technical_approach: null,
    estimated_indexable_pages: null,
    why_it_works: null,
    conventional_approach: null,
    innovation_angle: null,
    estimated_cac_paid: null,
    organic_discovery_queries: null,
    source_niche: "Support operations",
    source_verdict: null,
    is_featured: true,
    category: { id: "cat-1", name: "Support", slug: "support" },
    created_at: "2026-08-12T00:00:00Z",
    updated_at: "2026-08-12T00:00:00Z",
    faqJson: null,
    faqJsonMeta: null,
    ...overrides,
  };
}

describe("catalog idea format display", () => {
  it("shows only the delivery format on a dense card when model differs", () => {
    const view = render(IdeaCardV2, { props: { idea: idea() } });

    expect(view.getByText("Browser extension")).toBeInTheDocument();
    expect(view.queryByText("saas")).not.toBeInTheDocument();
  });

  it("falls back to project type on a legacy dense card", () => {
    const view = render(IdeaCardV2, {
      props: { idea: idea({ delivery_format: null, format: "saas", project_type: "saas" }) },
    });

    expect(view.getByText("Saas")).toBeInTheDocument();
    expect(view.queryByText("Browser extension")).not.toBeInTheDocument();
  });

  it("ignores malformed or blank formats and uses the legacy fallback", () => {
    const malformed = idea({
      delivery_format: {} as unknown as string,
      format: "browser-extension",
      project_type: "directory",
    });
    const view = render(IdeaCardV2, { props: { idea: malformed } });

    expect(view.getByText("Directory")).toBeInTheDocument();
  });

  it("labels distinct hero facts so delivery and model cannot be confused", () => {
    const view = render(IdeaHeroV2, { props: { idea: idea() } });

    expect(view.getByText("Delivered as · Browser extension")).toBeInTheDocument();
    expect(view.getByText("Model · SaaS")).toBeInTheDocument();
  });

  it("shows one delivery-first hero fact when values match", () => {
    const view = render(IdeaHeroV2, {
      props: { idea: idea({ delivery_format: "service", format: "service", project_type: "service" }) },
    });

    expect(view.getByText("Delivered as · Service")).toBeInTheDocument();
    expect(view.queryByText("Model · Service")).not.toBeInTheDocument();
  });

  it("shows only the model for an absent legacy delivery format", () => {
    const view = render(IdeaHeroV2, {
      props: { idea: idea({ delivery_format: null, format: "saas", project_type: "saas" }) },
    });

    expect(view.getByText("Model · SaaS")).toBeInTheDocument();
    expect(view.queryByText(/Delivered as/)).not.toBeInTheDocument();
  });
});
