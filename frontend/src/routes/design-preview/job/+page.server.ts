import type { PageServerLoad } from "./$types";
import { normalizeJob } from "./normalize";
import solutions from "./_fixture/solutions.json";
import preview from "./_fixture/preview.json";

/**
 * Prototype/demo page. The data is a captured snapshot of the "Peptides
 * Supplements" job (status AWAITING_SELECTION) stored under `_fixture/`, so
 * the page renders in production with NO backend call — that job does not
 * exist on prod. `normalizeJob` stays the source of truth: if the view-model
 * shape changes, this page updates without recapturing (unless the raw
 * backend payload shape itself changes). To refresh the snapshot, re-run the
 * two `/api/jobs/<id>/{solutions,preview-report}` calls against a dev backend.
 *
 * Not prerendered: adapter-node serves it via SSR, and the fixture is bundled,
 * so there is no backend dependency at request time.
 */
type SolutionsPayload = Parameters<typeof normalizeJob>[0];
type PreviewPayload = Parameters<typeof normalizeJob>[1];

export const load: PageServerLoad = () => {
  const vm = normalizeJob(
    solutions as unknown as SolutionsPayload,
    preview as unknown as PreviewPayload,
  );
  return { ready: true, reason: null, jobId: "peptides-supplements-demo", data: vm };
};
