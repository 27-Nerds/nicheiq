<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    type?: "text" | "email" | "password" | "number";
    placeholder?: string;
    value?: string;
    disabled?: boolean;
    error?: string;
    icon?: Snippet;
    class?: string;
    oninput?: (e: Event) => void;
    onkeydown?: (e: KeyboardEvent) => void;
  }

  let {
    type = "text",
    placeholder = "",
    value = $bindable(""),
    disabled = false,
    error = "",
    icon,
    class: className = "",
    oninput,
    onkeydown,
  }: Props = $props();
</script>

<div class="relative w-full">
  {#if icon}
    <span class="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted">
      {@render icon()}
    </span>
  {/if}

  <input
    {type}
    {placeholder}
    {disabled}
    bind:value
    {oninput}
    {onkeydown}
    class="
			w-full px-4 py-3.5 font-body text-base text-text-primary
			bg-bg-paper border rounded outline-none
			transition-all duration-200 ease-out
			placeholder:text-text-muted
			focus:border-accent-copper focus:shadow-[0_0_0_3px_rgba(184,115,51,0.1)]
			disabled:bg-bg-ivory disabled:cursor-not-allowed
			{icon ? 'pl-12' : ''}
			{error ? 'border-error' : 'border-border'}
			{className}
		"
  />

  {#if error}
    <p class="mt-2 text-sm text-error">{error}</p>
  {/if}
</div>
