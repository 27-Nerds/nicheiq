import { env } from '$env/dynamic/private';

// Single source of truth for the pre-launch SEO gate. While the env var is
// `true` (default) every public-catalog SSR route stamps `noindex, follow`
// and the sitemap omits the catalog branches. Flipping `SEO_LAUNCH_GATE=false`
// in the deployment env opens the entire catalog to indexing in one go.
//
// Routes import this constant rather than re-deriving it inline; that's how
// the default and parsing rule stays consistent if it ever changes.
export const LAUNCH_GATE_ON = (env.SEO_LAUNCH_GATE ?? 'true') !== 'false';
