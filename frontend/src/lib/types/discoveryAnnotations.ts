export type AnnotationPoint = [number, number];

export interface AnnotationAnchorPoint {
  key: string;
  x: number;
  y: number;
  /** Original region size retained for documents saved by earlier projection rules. */
  width?: number;
  height?: number;
}

export interface AnnotationAnchor {
  key: string;
  width: number;
  height: number;
}

export interface AnnotationStroke {
  id: string;
  color: string;
  width: number;
  createdAt: number;
  surfaceHeight?: number;
  anchor?: AnnotationAnchor;
  /** Legacy per-point anchors kept for documents saved before stable anchor sizing. */
  anchors?: Array<AnnotationAnchorPoint | null>;
  points: AnnotationPoint[];
}

export interface AnnotationSurfaceData {
  strokes: AnnotationStroke[];
}

export interface DiscoveryAnnotationDocument {
  version: 1;
  surfaces: Record<string, AnnotationSurfaceData>;
}

export interface DiscoveryAnnotationResponse {
  revision: number;
  document: DiscoveryAnnotationDocument;
  updatedAt: string | null;
}

export const EMPTY_DISCOVERY_ANNOTATIONS: DiscoveryAnnotationDocument = {
  version: 1,
  surfaces: {},
};
