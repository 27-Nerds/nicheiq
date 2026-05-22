import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import type { SavedPainPointItem } from "$lib/types/saved";
import LockedSavedCard from "../LockedSavedCard.svelte";
import SavedPainTable from "../SavedPainTable.svelte";

// Saved items the user has lost access to are rendered as locked placeholders.
// The backend strips the item + note, so these components must (a) render a
// locked state + unlock link, (b) leak no content, and (c) not throw on the
// `idea: null` / `painPoint: null` shape.

describe("LockedSavedCard", () => {
  it("renders the locked placeholder + unlock link and fires onRemove", async () => {
    const onRemove = vi.fn();
    render(LockedSavedCard, {
      props: { kind: "idea", createdAt: "2026-01-01T00:00:00Z", onRemove },
    });

    expect(screen.getByText("Locked idea")).toBeTruthy();
    const unlock = screen.getByRole("link", { name: /subscribe to unlock/i });
    expect(unlock.getAttribute("href")).toBe("/unlock-catalog");

    await fireEvent.click(screen.getByRole("button", { name: /remove locked idea/i }));
    expect(onRemove).toHaveBeenCalledOnce();
  });
});

describe("SavedPainTable — locked rows", () => {
  const items = [
    {
      id: "s-lock",
      userId: "u",
      painPointId: "pp-1",
      notes: null,
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      locked: true,
      painPoint: null,
    },
    {
      id: "s-ok",
      userId: "u",
      painPointId: "pp-2",
      notes: null,
      createdAt: "2026-01-02T00:00:00Z",
      updatedAt: "2026-01-02T00:00:00Z",
      painPoint: {
        id: "pp-2",
        slug: "visible-pain",
        title: "VisiblePainTitle",
        description: "desc",
        mentionCount: 5,
        severityScore: 0.5,
        willingnessToPayScore: 0.4,
        opportunityLevel: "high",
        representativeQuotes: null,
        sourcePlatforms: null,
        themeId: null,
        solutionApproach: null,
        isFeatured: true,
        sourceNiche: "n",
        category: { id: "c", name: "C", slug: "c", parent: null },
      },
    },
  ] as unknown as SavedPainPointItem[];

  it("renders a locked row (no content leak) alongside an accessible row", () => {
    render(SavedPainTable, {
      props: { items, onUnsave: vi.fn(), onNotesChange: vi.fn() },
    });

    // Locked row: placeholder + unlock link; the accessible row's title renders.
    expect(screen.getByText("🔒 Locked pain point")).toBeTruthy();
    expect(screen.getByText("VisiblePainTitle")).toBeTruthy();
    const unlock = screen.getByRole("link", { name: /^unlock$/i });
    expect(unlock.getAttribute("href")).toBe("/unlock-catalog");
  });
});
