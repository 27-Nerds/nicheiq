import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import UsersPage from "./+page.svelte";

vi.mock("$app/navigation", () => ({
  goto: vi.fn(),
  invalidateAll: vi.fn(),
}));

vi.mock("$app/state", () => ({
  page: { url: new URL("http://localhost/admin/users") },
}));

const users = [
  {
    id: "user-1",
    email: "member@example.com",
    name: "Member Name",
    role: "USER",
    subscriptionStatus: null,
    subscriptionPlanName: null,
    fullCatalogAccess: true,
    chatAnalystAccess: true,
    decisionToolsAccess: true,
    creditBalance: 160,
    jobCount: 14,
    createdAt: "2026-03-10T00:00:00.000Z",
  },
  {
    id: "admin-1",
    email: "admin@example.com",
    name: "Admin Name",
    role: "ADMIN",
    subscriptionStatus: null,
    subscriptionPlanName: null,
    fullCatalogAccess: false,
    chatAnalystAccess: false,
    decisionToolsAccess: false,
    creditBalance: 524,
    jobCount: 91,
    createdAt: "2026-03-04T00:00:00.000Z",
  },
];

afterEach(cleanup);

describe("admin users layout", () => {
  it("groups account data into stable columns and keeps every control addressable", () => {
    const { getAllByRole, getByRole, getByText } = render(UsersPage, {
      props: {
        data: {
          search: "",
          usersData: {
            users,
            page: 1,
            totalPages: 1,
            total: users.length,
          },
        } as never,
      },
    });

    expect(
      getAllByRole("columnheader").map((header) => header.textContent?.trim()),
    ).toEqual(["User", "Role", "Access", "Usage", "Actions"]);
    expect(getByText("member@example.com")).toBeInTheDocument();
    expect(getByText("Catalog grant")).toBeInTheDocument();
    expect(getByText("Chat grant")).toBeInTheDocument();
    expect(getByText("Tools grant")).toBeInTheDocument();
    expect(getByText("All access")).toBeInTheDocument();
    expect(
      getByRole("button", { name: "Add credits to member@example.com" }),
    ).toBeInTheDocument();
    expect(
      getByRole("button", { name: "Promote member@example.com" }),
    ).toBeInTheDocument();
    expect(
      getByRole("button", { name: "Decision tools" }),
    ).toHaveAttribute("aria-pressed", "true");
  });
});
