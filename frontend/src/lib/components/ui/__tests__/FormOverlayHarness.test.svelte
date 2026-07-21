<script lang="ts">
  import FormOverlay from "../FormOverlay.svelte";

  let {
    open = true,
    title = "Decision profile",
    onRequestClose = () => {},
    dirty = false,
    closeWarning = undefined,
  }: {
    open?: boolean;
    title?: string;
    onRequestClose?: () => void;
    dirty?: boolean;
    closeWarning?: string;
  } = $props();
</script>

<FormOverlay
  {open}
  size="wide"
  eyebrow="Decision setup"
  {title}
  description="Set the constraints that should shape this decision."
  annotationAnchor="decision-profile-form"
  {onRequestClose}
  {dirty}
  {closeWarning}
>
  <label>
    Available hours
    <input aria-label="Available hours" />
  </label>

  {#snippet footer()}
    <button type="button">Save profile</button>
  {/snippet}
</FormOverlay>
