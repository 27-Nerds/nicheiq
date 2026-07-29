import { describe, expect, it } from "vitest";
import { conceptForgeJsonResponse } from "../conceptForgeProxy";

describe("conceptForgeJsonResponse", () => {
  it("passes a no-content success through instead of reporting it as a failure", async () => {
    // The archive endpoint answers 204. Parsing that as JSON throws, and the fallback
    // turned a SUCCESSFUL discard into a 502 the UI reported as "Could not discard".
    const result = await conceptForgeJsonResponse(new Response(null, { status: 204 }));

    expect(result.status).toBe(204);
    expect(await result.text()).toBe("");
  });

  it("passes a reset-content success through as well", async () => {
    const result = await conceptForgeJsonResponse(new Response(null, { status: 205 }));

    expect(result.status).toBe(205);
  });

  it("forwards a JSON body and its status", async () => {
    const result = await conceptForgeJsonResponse(
      new Response(JSON.stringify({ set: { id: "s1" } }), { status: 200 }),
    );

    expect(result.status).toBe(200);
    expect(await result.json()).toEqual({ set: { id: "s1" } });
  });

  it("keeps an upstream error status when the body is not JSON", async () => {
    const result = await conceptForgeJsonResponse(new Response("<html>502</html>", { status: 502 }));

    expect(result.status).toBe(502);
    expect((await result.json()).error).toMatch(/could not read the server response/i);
  });
});
