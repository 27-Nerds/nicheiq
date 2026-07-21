import { error, redirect } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { fetchBackend } from "$lib/backend";
import { requireUser } from '$lib/server/requireUser';

function githubUrl(value: unknown): string {
  if (typeof value !== "string") throw error(502, "GitHub returned an invalid redirect");
  const target = new URL(value);
  if (target.protocol !== "https:" || target.hostname !== "github.com") {
    throw error(502, "GitHub returned an invalid redirect");
  }
  return target.toString();
}

export const GET: RequestHandler = async ({ url, locals }) => {
  const user = await requireUser(locals);
  const state = url.searchParams.get("state");
  const installationId = url.searchParams.get("installation_id");
  if (!state || !installationId) throw error(400, "Invalid GitHub setup callback");
  const response = await fetchBackend("/api/integrations/github/setup", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-ID": user.id,
    },
    body: JSON.stringify({ state, installationId }),
  });
  const body = await response.json();
  if (!response.ok) throw error(response.status, body.error ?? "Could not verify GitHub setup");
  redirect(303, githubUrl(body.authorizeUrl));
};
