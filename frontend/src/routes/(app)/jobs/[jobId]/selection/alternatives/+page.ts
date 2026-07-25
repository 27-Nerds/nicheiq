import { redirect } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

/** Compatibility only: branching is a contextual form over comparison,
 * never a separate journey page. */
export const load: PageLoad = ({ params, url }) => {
  const query = new URLSearchParams(url.searchParams);
  query.set("tool", "variants");
  throw redirect(
    307,
    `/jobs/${encodeURIComponent(params.jobId)}/selection/compare?${query.toString()}`,
  );
};
