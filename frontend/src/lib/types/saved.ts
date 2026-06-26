/**
 * Types for the saved-items surface (/ideas/saved page + SaveButton).
 *
 * Backend shapes mirror the Prisma SavedIdea / SavedPainPoint rows. The
 * embedded `idea` / `painPoint` fields use the same camelCase projections
 * defined by `savedIdeaSelect` / `savedPainPointSelect` in
 * `backend/src/routes/saves.ts` — NOT the snake_case `IdeaPreview` shape
 * that public catalog endpoints return. Saved-page card components must
 * adapt at the prop boundary (or accept both shapes via a union/adapter).
 */

export type SaveItemKind = 'idea' | 'painPoint';

/** Compact catalog-side projection of a CatalogIdea included in a SavedIdea row. */
export interface SavedIdeaCardData {
  id: string;
  slug: string | null;
  solutionName: string;
  headline: string | null;
  shortDescription: string | null;
  description: string;
  format: string | null;
  projectType: string | null;
  marketFitScore: number | null;
  technicalFeasibility: number | null;
  seoScalabilityScore: number | null;
  sourceVerdict: string | null;
  sourceNiche: string;
  isFeatured: boolean;
  category: {
    id: string;
    name: string;
    slug: string;
    /** Top-level niche when the item lives in a sub-niche; null for items
     *  saved directly under a top-level category. */
    parent: { name: string; slug: string } | null;
  };
}

/** Compact catalog-side projection of a CatalogPainPoint. */
export interface SavedPainPointCardData {
  id: string;
  slug: string | null;
  title: string;
  description: string;
  mentionCount: number;
  severityScore: number;
  commercialIntentScore: number;
  opportunityLevel: string;
  representativeQuotes: unknown;
  sourcePlatforms: unknown;
  themeId: string | null;
  solutionApproach: string | null;
  isFeatured: boolean;
  sourceNiche: string;
  category: {
    id: string;
    name: string;
    slug: string;
    /** Top-level niche when the item lives in a sub-niche; null for items
     *  saved directly under a top-level category. */
    parent: { name: string; slug: string } | null;
  };
}

interface SavedIdeaRowBase {
  id: string;
  userId: string;
  ideaId: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * A saved idea is EITHER accessible (full card data) OR locked — when a
 * non-entitled user has a saved row for a non-featured idea, the backend strips
 * the item preview and the note (`idea:null, notes:null, locked:true`) so no
 * content reaches the client. Discriminated on `locked` so TS narrows safely.
 */
export type SavedIdeaItemUnlocked = SavedIdeaRowBase & {
  locked?: false;
  notes: string | null;
  idea: SavedIdeaCardData;
};
export type SavedIdeaItemLocked = SavedIdeaRowBase & {
  locked: true;
  notes: null;
  idea: null;
};
export type SavedIdeaItem = SavedIdeaItemUnlocked | SavedIdeaItemLocked;

interface SavedPainRowBase {
  id: string;
  userId: string;
  painPointId: string;
  createdAt: string;
  updatedAt: string;
}

export type SavedPainPointItemUnlocked = SavedPainRowBase & {
  locked?: false;
  notes: string | null;
  painPoint: SavedPainPointCardData;
};
export type SavedPainPointItemLocked = SavedPainRowBase & {
  locked: true;
  notes: null;
  painPoint: null;
};
export type SavedPainPointItem = SavedPainPointItemUnlocked | SavedPainPointItemLocked;

export interface SavedListResponse<T> {
  items: T[];
  nextCursor: string | null;
}

export interface SavedCounts {
  ideas: number;
  painPoints: number;
}

/** Filter set for the /ideas/saved page query string. */
export interface SavedItemFilters {
  hasNotes?: boolean;
  /** Only honoured for ideas; pain points don't carry verdict in v1. */
  verdict?: 'GO' | 'CONDITIONAL' | 'NO_GO';
}

/** Response shape from GET /api/saves/{ideas|pain-points}/status?ids=... */
export type SavedStatusMap = Record<string, boolean>;
