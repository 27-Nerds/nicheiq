import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { page } from "$app/state";
import AppHeader from "../AppHeader.svelte";

vi.mock("@auth/sveltekit/client", () => ({ signOut: vi.fn() }));

afterEach(() => {
  cleanup();
  page.url = new URL("http://localhost/") as typeof page.url;
  page.route.id = null;
});

describe("AppHeader width contract", () => {
  it.each([
    ["dashboard", "/(app)/dashboard", "/dashboard"],
    ["new research", "/(app)/new", "/new"],
    ["job workspace", "/(app)/jobs/[jobId]", "/jobs/job-1"],
    ["job report", "/(app)/jobs/[jobId]/report", "/jobs/job-1/report"],
    ["logged-in catalog", "/(public)/ideas", "/ideas"],
  ])("uses the canonical full-width shell on %s", (_label, routeId, pathname) => {
    page.route.id = routeId as typeof page.route.id;
    page.url = new URL(`http://localhost${pathname}`) as typeof page.url;

    const view = render(AppHeader);
    const inner = view.container.querySelector<HTMLElement>(".app-header > div");

    expect(inner).not.toBeNull();
    expect(inner).toHaveClass("w-full", "px-4", "sm:px-6", "lg:px-8");
    expect(inner).not.toHaveClass("max-w-7xl", "mx-auto");
  });
});
