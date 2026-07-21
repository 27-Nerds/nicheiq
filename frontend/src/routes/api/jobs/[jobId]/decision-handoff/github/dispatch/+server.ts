import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { fetchBackend } from "$lib/backend";
import { requireUserId } from "$lib/server/requireUser";

export const GET: RequestHandler = async ({ params, locals }) => {
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/decision-handoff/github/dispatch`,
    { headers: { "X-User-ID": await requireUserId(locals) } },
  );
  return json(await response.json(), {
    status: response.status,
    headers: { "Cache-Control": "private, no-store" },
  });
};

export const POST: RequestHandler = async ({ params, locals, request }) => {
  const response = await fetchBackend(
    `/api/jobs/${params.jobId}/decision-handoff/github/dispatch`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": await requireUserId(locals),
      },
      body: await request.text(),
    },
  );
  return json(await response.json(), {
    status: response.status,
    headers: { "Cache-Control": "private, no-store" },
  });
};
