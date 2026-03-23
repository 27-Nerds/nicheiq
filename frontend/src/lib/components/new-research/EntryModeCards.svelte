<script lang="ts" module>
  export type EntryMode = "idea" | "audience" | "discovery";

  export const MODE_COLORS: Record<EntryMode, { dot: string; c1: string; c2: string }> = {
    idea: { dot: "bg-accent", c1: "#F06030", c2: "#F48060" },
    audience: { dot: "bg-indigo-500", c1: "#6366F1", c2: "#818CF8" },
    discovery: { dot: "bg-emerald-500", c1: "#10B981", c2: "#34D399" },
  };
</script>

<script lang="ts">
  interface Props {
    selected: EntryMode;
    onselect: (mode: EntryMode) => void;
  }

  let { selected, onselect }: Props = $props();

  const modes = [
    {
      id: "idea" as EntryMode,
      title: "Explore a niche",
      mobileTitle: "Explore",
      description: "You have a market or problem in mind",
    },
    {
      id: "audience" as EntryMode,
      title: "Solve for a group",
      mobileTitle: "My audience",
      description: "You know who you want to build for",
    },
    {
      id: "discovery" as EntryMode,
      title: "Find what's emerging",
      mobileTitle: "Explore",
      description: "You want to see what's trending",
    },
  ] as const;

  const selectedDescription = $derived(
    modes.find((m) => m.id === selected)?.description ?? ""
  );
</script>

<div>
  <div class="inline-flex w-full sm:w-auto rounded-full bg-bg-elevated p-1 gap-1">
    {#each modes as mode}
      <button
        type="button"
        onclick={() => onselect(mode.id)}
        class="pressable flex-1 sm:flex-none py-2 px-4 rounded-full text-sm font-medium transition-all duration-200
          {selected === mode.id
          ? 'bg-accent/10 text-accent font-semibold border border-accent/30'
          : 'bg-transparent text-text-muted border border-transparent opacity-60 hover:opacity-100 hover:text-text-secondary'}"
      >
        <span class="flex items-center gap-1.5">
          {#if selected === mode.id}
            <span class="w-1.5 h-1.5 rounded-full {MODE_COLORS[mode.id].dot} shrink-0"></span>
          {/if}
          <span class="hidden sm:inline">{mode.title}</span>
          <span class="sm:hidden">{mode.mobileTitle}</span>
        </span>
      </button>
    {/each}
  </div>
  <p class="text-sm text-text-muted mt-2 text-center">{selectedDescription}</p>
</div>
