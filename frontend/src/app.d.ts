// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
import type { Session } from '@auth/core/types';

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
    // interface PageState {}
    // interface Platform {}
  }
}

export {};
