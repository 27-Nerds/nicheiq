<script lang="ts">
  import WorkspaceOverlay from "../WorkspaceOverlay.svelte";

  interface Props {
    onClose: () => void;
    onEscape?: () => void;
    modal?: boolean;
  }

  let { onClose, onEscape = undefined, modal = true }: Props = $props();
</script>

<WorkspaceOverlay open {modal} label="Analyst conversation" {onClose} {onEscape}>
  <div>
    <button type="button">Inside control</button>
  </div>
</WorkspaceOverlay>
