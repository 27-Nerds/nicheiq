import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import DocketEmpty from "../DocketEmpty.svelte";

// Locks down the copy matrix across the 5 reachable variants of the
// DocketEmpty discriminated union. The kicker was removed in a later
// revision (redundant with the SectionDivider above in section mode and
// with the headline in page mode) — these tests now also assert the old
// kicker text strings are NOT rendered, guarding against accidental
// re-introduction.

const FORBIDDEN_KICKERS = [
  "DOCKET · EMPTY",
  "SUBJECT · IDEAS · FILTER ACTIVE",
  "SUBJECT · PAIN POINTS · FILTER ACTIVE",
  "SUBJECT · IDEAS · NONE SAVED",
  "SUBJECT · PAIN POINTS · NONE SAVED",
];

function assertNoKicker() {
  for (const text of FORBIDDEN_KICKERS) {
    expect(screen.queryByText(text)).toBeNull();
  }
}

describe("DocketEmpty — page scope (globally empty docket)", () => {
  it("renders the docket-empty headline, body, and catalog anchor; no kicker", () => {
    render(DocketEmpty, { props: { scope: "page" } });

    expect(screen.getByText("An empty docket.")).toBeTruthy();
    expect(
      screen.getByText(/Bookmark ideas and pain points from the catalog/),
    ).toBeTruthy();

    const cta = screen.getByRole("link", { name: /Browse the catalog/ });
    expect(cta.getAttribute("href")).toBe("/ideas");

    assertNoKicker();
  });
});

describe("DocketEmpty — section/filter scope (filter narrowed to none)", () => {
  it("ideas variant: filter headline + filter-clear button; no kicker", () => {
    const onClearFilter = vi.fn();
    render(DocketEmpty, {
      props: {
        scope: "section",
        subject: "IDEAS",
        mode: "filter",
        onClearFilter,
      },
    });

    expect(screen.getByText("This filter returned no entries.")).toBeTruthy();
    expect(
      screen.getByText(/No saved ideas match the "Has notes" filter/),
    ).toBeTruthy();

    const cta = screen.getByRole("button", { name: /Show all saves/ });
    expect(cta).toBeTruthy();

    assertNoKicker();
  });

  it("pain points variant: filter headline + filter-clear button; no kicker", () => {
    const onClearFilter = vi.fn();
    render(DocketEmpty, {
      props: {
        scope: "section",
        subject: "PAIN POINTS",
        mode: "filter",
        onClearFilter,
      },
    });

    expect(
      screen.getByText(/No saved pain points match the "Has notes" filter/),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /Show all saves/ })).toBeTruthy();

    assertNoKicker();
  });
});

describe("DocketEmpty — section/discover scope (mixed-empty)", () => {
  it("ideas variant: discover headline, supply-side body, catalog anchor; no kicker", () => {
    render(DocketEmpty, {
      props: { scope: "section", subject: "IDEAS", mode: "discover" },
    });

    expect(screen.getByText("No ideas in this docket yet.")).toBeTruthy();
    expect(
      screen.getByText(/Ideas capture the supply side/),
    ).toBeTruthy();
    expect(
      screen.getByText(/pair with your saved pain points/),
    ).toBeTruthy();

    // Discover mode renders an anchor, NOT a button — clicking takes
    // the user to the catalog rather than firing a callback.
    const cta = screen.getByRole("link", { name: /Browse the catalog/ });
    expect(cta.getAttribute("href")).toBe("/ideas");
    expect(screen.queryByRole("button", { name: /Browse/ })).toBeNull();

    assertNoKicker();
  });

  it("pain points variant: discover headline, demand-side body, catalog anchor; no kicker", () => {
    render(DocketEmpty, {
      props: { scope: "section", subject: "PAIN POINTS", mode: "discover" },
    });

    expect(screen.getByText("No pain points in this docket yet.")).toBeTruthy();
    expect(
      screen.getByText(/Pain points capture the demand side/),
    ).toBeTruthy();
    expect(screen.getByText(/pair with your saved ideas/)).toBeTruthy();

    const cta = screen.getByRole("link", { name: /Browse the catalog/ });
    expect(cta.getAttribute("href")).toBe("/ideas");

    assertNoKicker();
  });
});
