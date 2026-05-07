/**
 * Types for the saved-items surface (/saved page + SaveButton).
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
  willingnessToPayScore: number;
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

export interface SavedIdeaItem {
  id: string;
  userId: string;
  ideaId: string;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  idea: SavedIdeaCardData;
}

export interface SavedPainPointItem {
  id: string;
  userId: string;
  painPointId: string;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  painPoint: SavedPainPointCardData;
}

export interface SavedListResponse<T> {
  items: T[];
  nextCursor: string | null;
}

export interface SavedCounts {
  ideas: number;
  painPoints: number;
}

/** Filter set for the /saved page query string. */
export interface SavedItemFilters {
  hasNotes?: boolean;
  /** Only honoured for ideas; pain points don't carry verdict in v1. */
  verdict?: 'GO' | 'CONDITIONAL' | 'NO_GO';
}

/** Response shape from GET /api/saves/{ideas|pain-points}/status?ids=... */
export type SavedStatusMap = Record<string, boolean>;
