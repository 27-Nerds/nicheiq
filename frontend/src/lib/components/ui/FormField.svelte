<script lang="ts">
  import type { ComponentType } from "svelte";

  interface Props {
    id: string;
    label: string;
    type?: string;
    value: string;
    icon: ComponentType;
    placeholder?: string;
    required?: boolean;
    minlength?: number;
    maxlength?: number;
    disabled?: boolean;
    onkeydown?: (e: KeyboardEvent) => void;
    class?: string;
  }

  let {
    id,
    label,
    type = "text",
    value = $bindable(),
    icon: Icon,
    placeholder,
    required = false,
    minlength,
    maxlength,
    disabled = false,
    onkeydown,
    class: className = "",
  }: Props = $props();
</script>

<div class={className}>
  <label for={id} class="block text-sm font-medium text-text-primary mb-1">
    {label}
  </label>
  <div class="relative">
    <Icon
      class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted"
    />
    <input
      {type}
      {id}
      bind:value
      {required}
      {minlength}
      {maxlength}
      {disabled}
      {placeholder}
      {onkeydown}
      class="input input-with-icon"
    />
  </div>
</div>
