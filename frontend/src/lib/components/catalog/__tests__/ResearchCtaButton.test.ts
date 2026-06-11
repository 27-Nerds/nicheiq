import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import { page } from "$app/state";
import { goto } from "$app/navigation";
import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
import ResearchCtaButton from "../ResearchCtaButton.svelte";

function setPageData(over: Record<string, unknown> = {}) {
  (page as any).data = {
    session: { user: { id: "u1" } },
    stageCosts: { discovery: 5, deep_research: 15 },
    creditBalance: 100,
    ...over,
  };
  (page as any).url = new URL("http://localhost/idea/invoiceflow");
}

describe("ResearchCtaButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    creditTopUp.open = false;
    setPageData();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    creditTopUp.open = false;
  });

  it("anonymous → redirects to register, no modal", async () => {
    setPageData({ session: null });
    render(ResearchCtaButton, { props: { kind: "idea", slug: "invoiceflow", label: "Deep research on this idea", subject: "InvoiceFlow" } });
    await fireEvent.click(screen.getByRole("button", { name: /deep research on this idea/i }));
    expect(goto).toHaveBeenCalledWith(expect.stringContaining("/register?ref=catalog&returnTo="));
    expect(screen.queryByText(/authorize/i)).toBeNull();
  });

  it("logged-in with credits → opens confirm modal, then POSTs and navigates", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ id: "job-9" }) }));
    vi.stubGlobal("fetch", fetchMock);

    render(ResearchCtaButton, { props: { kind: "idea", slug: "invoiceflow", label: "Deep research on this idea", subject: "InvoiceFlow" } });
    await fireEvent.click(screen.getByRole("button", { name: /deep research on this idea/i }));

    // Modal shows the cost ledger + authorize action.
    const authorize = await screen.findByRole("button", { name: /authorize · 15 credits/i });
    await fireEvent.click(authorize);

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/catalog/ideas/invoiceflow/deep-research",
        expect.objectContaining({ method: "POST" }),
      );
      expect(goto).toHaveBeenCalledWith("/jobs/job-9", { invalidateAll: true });
    });
  });

  it("insufficient credits → modal offers 'Get more credits' (no silent ignore)", async () => {
    setPageData({ creditBalance: 4 }); // 4 < 15
    render(ResearchCtaButton, { props: { kind: "idea", slug: "invoiceflow", label: "Deep research on this idea", subject: "InvoiceFlow" } });
    await fireEvent.click(screen.getByRole("button", { name: /deep research on this idea/i }));

    const getCredits = await screen.findByRole("button", { name: /get 11 more credits/i });
    expect(screen.queryByRole("button", { name: /authorize/i })).toBeNull();

    await fireEvent.click(getCredits);
    await vi.waitFor(() => expect(creditTopUp.open).toBe(true));
  });

  it("pain kind → POSTs painSlugs:[slug] at the discovery cost", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ id: "job-7" }) }));
    vi.stubGlobal("fetch", fetchMock);

    render(ResearchCtaButton, { props: { kind: "pain", slug: "manual-invoicing", label: "Explore solutions", subject: "Manual invoicing" } });
    await fireEvent.click(screen.getByRole("button", { name: /explore solutions/i }));

    const authorize = await screen.findByRole("button", { name: /authorize · 5 credits/i });
    await fireEvent.click(authorize);

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/catalog/pain-research",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ painSlugs: ["manual-invoicing"] }),
        }),
      );
      expect(goto).toHaveBeenCalledWith("/jobs/job-7", { invalidateAll: true });
    });
  });

  it("404 (removed from catalog) → non-retry error message", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ error: "Idea not found" }) }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(ResearchCtaButton, { props: { kind: "idea", slug: "invoiceflow", label: "Deep research on this idea", subject: "InvoiceFlow" } });
    await fireEvent.click(screen.getByRole("button", { name: /deep research on this idea/i }));
    const authorize = await screen.findByRole("button", { name: /authorize · 15 credits/i });
    await fireEvent.click(authorize);

    expect(await screen.findByText(/removed from the catalog/i)).toBeTruthy();
    expect(goto).not.toHaveBeenCalled();
  });
});
