<script lang="ts">
  // Lightweight stand-in for KonvaAnnotationCanvas so the deferral test never
  // pulls in the real Konva runtime (which needs a live <canvas>).
  let { surfaceKey }: { surfaceKey: string; width: number; height: number } = $props();
</script>

<div data-testid="konva-stub" data-surface={surfaceKey}></div>
