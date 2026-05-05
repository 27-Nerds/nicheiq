<script lang="ts" module>
  export type EntryMode = "idea" | "audience" | "discovery";

  export const MODE_COLORS: Record<EntryMode, { dot: string; c1: string; c2: string }> = {
    idea: { dot: "bg-accent", c1: "#EA580C", c2: "#FB923C" },
    audience: { dot: "bg-indigo-500", c1: "#6366F1", c2: "#818CF8" },
    discovery: { dot: "bg-emerald-500", c1: "#10B981", c2: "#34D399" },
  };
</script>

<script lang="ts">
  import { Lightbulb, Users, TrendingUp } from "lucide-svelte";

  interface Props {
    selected: EntryMode;
    onselect: (mode: EntryMode) => void;
  }

  let { selected, onselect }: Props = $props();

  const modes = [
    {
      id: "idea" as EntryMode,
      title: "Explore a niche",
      description: "You have a market or problem in mind",
      icon: Lightbulb,
      iconClass: "text-accent",
    },
    {
      id: "audience" as EntryMode,
      title: "Solve for a group",
      description: "You know who you want to build for",
      icon: Users,
      iconClass: "text-indigo-500",
    },
    {
      id: "discovery" as EntryMode,
      title: "Find what's emerging",
      description: "You want to see what's trending",
      icon: TrendingUp,
      iconClass: "text-emerald-500",
    },
  ] as const;
</script>

<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
  {#each modes as mode}
    {@const isSelected = selected === mode.id}
    <button
      type="button"
      onclick={() => onselect(mode.id)}
      class="pressable text-left p-4 rounded-lg border transition-all duration-150 ease-out
        focus-visible:ring-2 focus-visible:ring-accent/30 focus-visible:outline-none
        {isSelected
        ? 'border-border-emphasis bg-bg-elevated'
        : 'border-border bg-bg-elevated opacity-70 hover:opacity-90'}"
    >
      <div class="flex items-start gap-3">
        <mode.icon class="w-5 h-5 shrink-0 mt-0.5 {isSelected ? mode.iconClass : 'text-text-muted'}" />
        <div class="min-w-0">
          <p class="text-sm font-medium text-text-primary">
            {mode.title}
          </p>
          <p class="text-xs mt-0.5 text-text-muted">
            {mode.description}
          </p>
        </div>
      </div>
    </button>
  {/each}
</div>
