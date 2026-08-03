import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
import type { TokenPackage } from "$lib/types/billing";
import CreditTopUpModal from "../CreditTopUpModal.svelte";

function pkg(id: string, credits: number, priceInCents: number): TokenPackage {
  return {
    id,
    name: `${credits} pack`,
    description: null,
    credits,
    priceInCents,
    isPopular: false,
    tagline: null,
    includesLabel: null,
    creditsInfo: null,
    features: null,
    ctaText: null,
    badgeLabel: null,
  } as TokenPackage;
}

// Four packages so the shortfall-aware window has something beyond the first three.
const PACKAGES = [
  pkg("p10", 10, 500),
  pkg("p25", 25, 1000),
  pkg("p50", 50, 1800),
  pkg("p120", 120, 4000),
];

beforeEach(() => {
  creditTopUp.cachedPackages = PACKAGES;
});

afterEach(() => {
  cleanup();
  creditTopUp.open = false;
  creditTopUp.cachedPackages = null;
});

describe("CreditTopUpModal package window", () => {
  it("labels the smallest covering package 'Covers your need'", async () => {
    creditTopUp.show({ balance: 0, required: 20, stageName: "discovery" });
    const view = render(CreditTopUpModal);

    expect(await view.findByText("· Covers your need")).toBeInTheDocument();
    expect(view.getByText("25 credits")).toBeInTheDocument();
    expect(view.queryByText(/of \d+ needed/)).not.toBeInTheDocument();
  });

  it("always includes the smallest covering package even outside the first three", async () => {
    creditTopUp.show({ balance: 0, required: 100, stageName: "deep research" });
    const view = render(CreditTopUpModal);

    // Window shifts to end at the covering package: 25 / 50 / 120.
    expect(await view.findByText("120 credits")).toBeInTheDocument();
    expect(view.queryByText("10 credits")).not.toBeInTheDocument();
    expect(view.getByText("· Covers your need")).toBeInTheDocument();
  });

  it("shows the honesty sub-line when no package covers the shortfall", async () => {
    creditTopUp.show({ balance: 0, required: 300, stageName: "deep research" });
    const view = render(CreditTopUpModal);

    expect(await view.findByText("· Best value")).toBeInTheDocument();
    expect(view.getByText("Covers 120 of 300 needed")).toBeInTheDocument();
  });
});
