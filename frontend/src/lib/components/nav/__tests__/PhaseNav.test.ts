import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PhaseNav from "../PhaseNav.svelte";
import { rankedIdeasHref } from "$lib/selection/rankedIdeas";

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("PhaseNav selection journey", () => {
  it("returns every Choose ideas link to the visible first ranked row", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "AWAITING_SELECTION",
        jobId: "job-1",
        mode: "selection",
        nested: true,
        activeTool: "review",
      },
    });

    const links = view.getAllByRole("link", { name: "Choose ideas" });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link).toHaveAttribute("href", rankedIdeasHref("job-1"));
    }
  });

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

describe("PhaseNav saved decision record", () => {
  it("uses read-only destinations and removes selection actions after handoff", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "RUNNING_PHASE2",
        jobId: "job-1",
        mode: "selection-record",
        nested: true,
        activeTool: "risks",
        selectionQuery: "?idea=idea-a%3A3",
        decisionTools: true,
      },
    });

    expect(view.getAllByRole("link", { name: "Comparison record" })).toHaveLength(2);
    expect(view.getAllByRole("link", { name: "Evidence & risk record" })).toHaveLength(2);
    expect(view.getAllByRole("link", { name: "Saved research scope" })).toHaveLength(2);
    expect(view.getAllByRole("link", { name: "View run" })).toHaveLength(2);
    expect(view.container.querySelector("nav.selection-mobile-nav--record")).toBeInTheDocument();
    expect(view.container.querySelector("nav.selection-mobile-nav--record.selection-mobile-nav--journey"))
      .not.toBeInTheDocument();
    expect(view.queryByText("Choose ideas")).not.toBeInTheDocument();
    expect(view.queryByText("Review and start")).not.toBeInTheDocument();
    for (const link of view.getAllByRole("link", { name: "Evidence & risk record" })) {
      expect(link).toHaveAttribute("href", "/jobs/job-1/selection/risks?idea=idea-a%3A3");
      expect(link).toHaveAttribute("aria-current", "page");
    }
  });
});

describe("PhaseNav stopped run", () => {
  it("shows only the recovery row when a stopped run has no discovery sections", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "CANCELLED",
        jobId: "job-1",
        mode: "stopped",
        recoverLabel: "Start new research",
        recoverHref: "/new?fromJob=job-1&prefilled=test",
        availableSectionIds: [],
      },
    });

    expect(view.getAllByText("Recover run").length).toBeGreaterThan(0);
    for (const link of view.getAllByRole("link", { name: "Start new research" })) {
      expect(link).toHaveAttribute("href", "/new?fromJob=job-1&prefilled=test");
    }
    expect(view.queryByText("Discovery context")).toBeNull();
  });

  it("keeps the discovery context group when a stopped run has sections to read", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "FAILED",
        jobId: "job-1",
        mode: "stopped",
        recoverLabel: "Resume run",
        availableSectionIds: ["overview", "pain-points"],
      },
    });

    expect(view.getAllByText("Discovery context").length).toBeGreaterThan(0);
    expect(view.getAllByText("Overview").length).toBeGreaterThan(0);
  });

  it("leaves the selection-mode discovery group untouched by the stopped-mode guard", () => {
    const view = render(PhaseNav, {
      props: {
        jobStatus: "AWAITING_SELECTION",
        jobId: "job-1",
        mode: "selection",
        nested: true,
        selectedCount: 1,
        availableSectionIds: [],
      },
    });

    // The empty-group guard is scoped to stopped mode only — the selection layout
    // (second consumer of this component) keeps its group exactly as before.
    expect(view.getAllByText("Discovery context").length).toBeGreaterThan(0);
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
    expect(view.getByRole("link", { name: "Decision record" })).toHaveAttribute(
      "href",
      "/jobs/job-1/selection/compare",
    );
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
