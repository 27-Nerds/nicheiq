<script lang="ts">
  import FormOverlay from "../FormOverlay.svelte";

  let {
    open = true,
    onRequestClose = () => {},
    dirty = false,
    closeWarning = undefined,
  }: {
    open?: boolean;
    onRequestClose?: () => void;
    dirty?: boolean;
    closeWarning?: string;
  } = $props();
</script>

<FormOverlay
  {open}
  size="form"
  title="Decision profile"
  {onRequestClose}
  {dirty}
  {closeWarning}
>
  <label>
    Available hours
    <input aria-label="Available hours" />
  </label>

  {#snippet footerCancel(requestClose)}
    <button type="button" onclick={requestClose}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <button type="button">Save profile</button>
  {/snippet}
</FormOverlay>
