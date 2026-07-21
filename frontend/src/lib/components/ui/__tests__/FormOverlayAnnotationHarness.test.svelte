<script lang="ts">
  import FormOverlay from "../FormOverlay.svelte";
  import { provideAnnotationContext } from "$lib/components/annotations/context";

  let { editable = true }: { editable?: boolean } = $props();

  provideAnnotationContext({
    get editable() { return editable; },
    active: true,
    tool: "navigate",
    color: "#dc2626",
    strokeWidth: 4,
    saveStatus: "saved",
    getStrokes: () => [],
    addStroke: () => {},
    removeStroke: () => {},
    setActive: () => {},
    setTool: () => {},
    setColor: () => {},
    undo: () => {},
  });
</script>

<FormOverlay
  open
  title="Decision profile"
  annotationAnchor="decision-profile-form"
  onRequestClose={() => {}}
>
  <label>
    Available hours
    <input aria-label="Available hours" />
  </label>

  {#snippet footer()}
    <button type="button">Save profile</button>
  {/snippet}
</FormOverlay>
