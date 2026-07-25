import { redirect } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

/** Compatibility only: test planning is a contextual form over the evidence
 * workspace, never a fifth journey page. */
export const load: PageLoad = ({ params, url }) => {
  const query = new URLSearchParams(url.searchParams);
  query.set("tool", "tests");
  throw redirect(
    307,
    `/jobs/${encodeURIComponent(params.jobId)}/selection/risks?${query.toString()}`,
  );
};
