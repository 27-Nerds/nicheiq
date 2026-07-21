import { error, redirect } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { fetchBackend } from "$lib/backend";
import { requireUser } from '$lib/server/requireUser';

export const GET: RequestHandler = async ({ url, locals }) => {
  const user = await requireUser(locals);
  const state = url.searchParams.get("state");
  const code = url.searchParams.get("code");
  if (!state || !code) throw error(400, "Invalid GitHub authorization callback");
  const response = await fetchBackend("/api/integrations/github/callback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-ID": user.id,
    },
    body: JSON.stringify({ state, code }),
  });
  const body = await response.json();
  if (!response.ok) throw error(response.status, body.error ?? "Could not verify GitHub authorization");
  if (typeof body.returnPath !== "string" || !/^\/jobs\/[0-9a-f-]+\/report\?github=connected$/i.test(body.returnPath)) {
    throw error(502, "GitHub returned an invalid destination");
  }
  redirect(303, body.returnPath);
};
