// Shared dashboard config. Imported by both the +page.server.ts loader
// (to know how many summaries to prefetch) and the +page.svelte page (to
// match the initial-visible cap for the "Show more" toggle).
export const INITIAL_VISIBLE_COMPLETED = 6;
