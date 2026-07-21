<script lang="ts">
  import AnnotationSurface from "../AnnotationSurface.svelte";
  import { provideAnnotationContext, type AnnotationSaveStatus, type AnnotationTool } from "../context";
  import type { AnnotationStroke } from "$lib/types/discoveryAnnotations";

  let {
    active = false,
    strokes = [] as AnnotationStroke[],
  }: { active?: boolean; strokes?: AnnotationStroke[] } = $props();

  provideAnnotationContext({
    get editable() { return true; },
    get active() { return active; },
    get tool() { return "navigate" as AnnotationTool; },
    get color() { return "#dc2626"; },
    get strokeWidth() { return 4; },
    get saveStatus() { return "saved" as AnnotationSaveStatus; },
    getStrokes: () => strokes,
    addStroke: () => {},
    removeStroke: () => {},
    setActive: () => {},
    setTool: () => {},
    setColor: () => {},
    undo: () => {},
  });
</script>

<AnnotationSurface surfaceKey="test-surface">
  <div>surface content</div>
</AnnotationSurface>
