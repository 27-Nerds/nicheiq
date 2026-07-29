import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Report } from "$lib/types/report";
import SectionNav from "../SectionNav.svelte";

afterEach(cleanup);

function report(fields: Record<string, unknown> = {}): Report {
  return fields as unknown as Report;
}

describe("SectionNav report availability", () => {
  it("does not advertise sections whose complete render requirements are absent", () => {
    const view = render(SectionNav, {
      props: {
        report: report({
          detailed_pain_points: [{}],
          traffic_monetization: {},
          competitive_analytics: {},
          seo_strategy_report: {},
        }),
      },
    });

    expect(view.queryByRole("button", { name: "Executive" })).toBeNull();
    expect(view.queryByRole("button", { name: "Solution" })).toBeNull();
    expect(view.queryByRole("button", { name: "Pain Points" })).toBeNull();
    expect(view.queryByRole("button", { name: "Market" })).toBeNull();
    expect(view.queryByRole("button", { name: "Monetization" })).toBeNull();
    expect(view.queryByRole("button", { name: "Competitors" })).toBeNull();
    expect(view.queryByRole("button", { name: "SEO" })).toBeNull();
  });

  it("uses the rendered audience section id when audience data is available", async () => {
    const target = document.createElement("div");
    target.id = "audience-intelligence";
    target.scrollIntoView = vi.fn();
    document.body.append(target);

    const view = render(SectionNav, {
      props: {
        report: report({ audience_mapping: {} }),
      },
    });

    await fireEvent.click(view.getAllByRole("button", { name: "Audience" })[0]);
    expect(target.scrollIntoView).toHaveBeenCalledOnce();
  });
});
