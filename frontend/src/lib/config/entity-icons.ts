/**
 * Entity icons — single source of truth for the "idea" vs "pain point" identity
 * used across catalog detail headers and the job provenance badge.
 *
 * Deliberately NOT the cliché set (lightbulb/rocket/sparkles/flame). Chosen from
 * NicheIQ's prospecting mechanic — zero in on a real pain, surface the valuable
 * opportunity:
 *   - Pain point → Crosshair (instrument-grade "zero in on the problem")
 *   - Idea       → Gem       (the validated, valuable opportunity surfaced)
 * They contrast in form (reticle lines vs faceted solid) so they read even at 10px.
 */
import Gem from "lucide-svelte/icons/gem";
import Crosshair from "lucide-svelte/icons/crosshair";

export const IDEA_ICON = Gem;
export const PAIN_ICON = Crosshair;
