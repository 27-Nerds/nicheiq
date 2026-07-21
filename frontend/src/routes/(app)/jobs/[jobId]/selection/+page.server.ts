import { redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = ({ params, url }) => {
  throw redirect(307, `/jobs/${params.jobId}/selection/compare${url.search}`);
};
