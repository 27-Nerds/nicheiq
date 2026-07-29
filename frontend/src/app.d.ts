// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
import type { Session } from '@auth/core/types';
import type { SelectionExperimentDraftSeed } from '$lib/types/selectionExperiment';
import type {
  SelectionAssumptionPrefill,
  SelectionConceptForgePrefill,
  SelectionOwnerEvidencePrefill,
} from '$lib/types/selectionCopilot';
import type { SelectionToolOrigin } from '$lib/selection/toolOrigin';
import type { ShortlistProposalHandoff } from '$lib/types/shortlistProposal';

declare global {
  // GA4 gtag types
  interface Window {
    dataLayer: unknown[];
    gtag: (...args: unknown[]) => void;
  }

  namespace App {
    // interface Error {}
    interface Locals {
      session: Session | null;
    }
    interface PageData {
      session: Session | null;
      availableProviders?: { google: boolean; github: boolean };
    }
    interface PageState {
      openId?: string;
      selectedId?: string;
      /** One-shot unsaved handoff; the URL still carries exact candidate refs. */
      selectionTestDraft?: SelectionExperimentDraftSeed;
      /** One-shot analyst-authored variant brief for the routed form. */
      selectionConceptPrefill?: SelectionConceptForgePrefill;
      /** One-shot grounded assumption draft for the direct evidence workspace. */
      selectionAssumptionPrefill?: SelectionAssumptionPrefill;
      /** One-shot owner-evidence draft for the direct evidence workspace. */
      selectionOwnerEvidencePrefill?: SelectionOwnerEvidencePrefill;
      /** One-shot return contract for a routed tool launched from the job page. */
      selectionToolOrigin?: SelectionToolOrigin;
      /** One-shot exact-scope proposal. Only the job hub may apply it. */
      shortlistProposal?: ShortlistProposalHandoff;
    }
    // interface Platform {}
  }
}

export {};
