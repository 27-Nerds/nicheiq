import { getContext, setContext } from 'svelte';
import type { AnnotationStroke } from '$lib/types/discoveryAnnotations';

export type AnnotationTool = 'navigate' | 'pen' | 'eraser';
export type AnnotationSaveStatus = 'idle' | 'loading' | 'saving' | 'saved' | 'error';

export interface AnnotationContext {
  readonly editable: boolean;
  readonly active: boolean;
  readonly tool: AnnotationTool;
  readonly color: string;
  readonly strokeWidth: number;
  readonly saveStatus: AnnotationSaveStatus;
  getStrokes(surfaceKey: string): AnnotationStroke[];
  addStroke(surfaceKey: string, stroke: AnnotationStroke): void;
  removeStroke(surfaceKey: string, strokeId: string): void;
  setActive(active: boolean): void;
  setTool(tool: AnnotationTool): void;
  setColor(color: string): void;
  undo(): void;
}

const ANNOTATION_CONTEXT = Symbol('discovery-annotation-context');

export function provideAnnotationContext(context: AnnotationContext): void {
  setContext(ANNOTATION_CONTEXT, context);
}

export function getAnnotationContext(): AnnotationContext | undefined {
  return getContext<AnnotationContext | undefined>(ANNOTATION_CONTEXT);
}
