import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PhaseNav from "../PhaseNav.svelte";

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("PhaseNav selection journey", () => {
  it("keeps the same four decision destinations on every selection route", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "AWAITING_SELECTION",
        jobId: "job-1",
        mode: "selection",
        nested: true,
        activeTool: "risks",
        selectedCount: 2,
        selectionQuery: "?idea=idea-a%3A3&idea=idea-b%3A1",
        decisionTools: true,
      },
    });

    expect(view.getAllByText("Choose ideas").length).toBeGreaterThan(0);
    expect(view.getAllByText("Compare trade-offs").length).toBeGreaterThan(0);
    expect(view.getAllByText("Check the evidence").length).toBeGreaterThan(0);
    expect(view.getAllByText("Review and start").length).toBeGreaterThan(0);
    for (const link of view.getAllByRole("link", { name: "Compare trade-offs" })) {
      expect(link).toHaveAttribute(
        "href",
        "/jobs/job-1/selection/compare?idea=idea-a%3A3&idea=idea-b%3A1",
      );
    }
    for (const link of view.getAllByRole("link", { name: "Check the evidence" })) {
      expect(link).toHaveAttribute(
        "href",
        "/jobs/job-1/selection/risks?idea=idea-a%3A3&idea=idea-b%3A1",
      );
    }
    for (const link of view.getAllByRole("link", { name: "Review and start" })) {
      expect(link).toHaveAttribute(
        "href",
        "/jobs/job-1/selection/review",
      );
    }
    expect(view.queryByText("Plan a test")).not.toBeInTheDocument();
    expect(view.queryByText("Explore variants")).not.toBeInTheDocument();
  });

  it("marks Review and start as the current destination on desktop and mobile", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "AWAITING_SELECTION",
        jobId: "job-1",
        mode: "selection",
        nested: true,
        activeTool: "review",
        selectedCount: 2,
      },
    });

    const reviewLinks = view.getAllByRole("link", { name: "Review and start" });
    expect(reviewLinks).toHaveLength(2);
    for (const link of reviewLinks) {
      expect(link).toHaveAttribute("aria-current", "page");
      expect(link).toHaveClass("active");
    }
  });

  it("only links to Discovery sections present in a partial report on desktop and mobile", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "AWAITING_SELECTION",
        jobId: "job-1",
        mode: "selection",
        nested: true,
        activeTool: "compare",
        selectedCount: 2,
        availableSectionIds: ["overview", "pain-points"],
      },
    });

    expect(view.getAllByRole("link", { name: "Overview" })).toHaveLength(2);
    expect(view.getAllByRole("link", { name: "Pain Points" })).toHaveLength(2);
    expect(view.queryByRole("link", { name: "Market Snapshot" })).not.toBeInTheDocument();
    expect(view.queryByRole("link", { name: "Audience" })).not.toBeInTheDocument();
    expect(view.queryByRole("link", { name: "Community" })).not.toBeInTheDocument();
  });
});

describe("PhaseNav without the decision tools grant", () => {
  it("drops Check the evidence but keeps the required path", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "AWAITING_SELECTION",
        jobId: "job-1",
        mode: "selection",
        nested: true,
        selectedCount: 2,
        selectionQuery: "?idea=idea-a%3A3",
        decisionTools: false,
      },
    });

    expect(view.getAllByText("Choose ideas").length).toBeGreaterThan(0);
    expect(view.getAllByText("Compare trade-offs").length).toBeGreaterThan(0);
    expect(view.getAllByText("Review and start").length).toBeGreaterThan(0);
    expect(view.queryByText("Check the evidence")).toBeNull();
    expect(view.queryByRole("link", { name: "Check the evidence" })).toBeNull();
  });
});

describe("PhaseNav completed-report destinations", () => {
  it.each([
    ["Brief", "/jobs/job-1/report?view=brief"],
    ["Evidence", "/jobs/job-1/report?view=evidence"],
    ["Plan", "/jobs/job-1/report?view=plan"],
  ])("links %s to its report view on desktop and mobile", async (label, href) => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "COMPLETED",
        jobId: "job-1",
        reportAvailable: true,
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Section navigation" }));
    const links = view.getAllByRole("link", { name: label });
    expect(links).toHaveLength(2);
    for (const link of links) {
      expect(link).toHaveAttribute("href", href);
    }
  });

  it("does not duplicate report topics in the global phase navigation", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "COMPLETED",
        jobId: "job-1",
        reportAvailable: true,
      },
    });

    expect(view.queryByRole("button", { name: "Solution" })).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Market" })).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Competitors" })).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Technical" })).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: "GTM" })).not.toBeInTheDocument();
  });

  it("orients the completed hub without fake completion marks and shows the real deliverable state", async () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "COMPLETED",
        jobId: "job-1",
        landingPageStatus: "running",
        reportAvailable: true,
      },
    });

    const desktopOverview = view.getByRole("link", { name: "Run overview" });
    expect(desktopOverview).toHaveAttribute("aria-current", "page");
    expect(desktopOverview).toHaveAttribute("href", "/jobs/job-1");
    expect(view.getByRole("link", { name: /Landing page Generating/ })).toHaveAttribute(
      "href",
      "/jobs/job-1#optional-deliverables",
    );
    expect(view.container.querySelector(".nav-check")).not.toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Section navigation" }));

    const overviewLinks = view.getAllByRole("link", { name: "Run overview" });
    expect(overviewLinks).toHaveLength(2);
    for (const link of overviewLinks) {
      expect(link).toHaveAttribute("aria-current", "page");
    }
    expect(view.getAllByText("Generating")).toHaveLength(2);
    expect(view.container.querySelector(".nav-check")).not.toBeInTheDocument();
  });

  it("does not link into a report route until the report asset exists", async () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "COMPLETED",
        jobId: "job-1",
        reportAvailable: false,
      },
    });

    expect(view.getAllByText("Report unavailable")).toHaveLength(2);
    expect(view.queryByRole("link", { name: "Brief" })).toBeNull();

    await fireEvent.click(view.getByRole("button", { name: "Section navigation" }));
    expect(view.getAllByText("Report unavailable")).toHaveLength(3);
    expect(view.queryByRole("link", { name: "Evidence" })).toBeNull();
  });
});
