<script lang="ts">
  import { renderMarkdown } from "$lib/utils/format";
  import {
    matchIdeaReferences,
    type IdeaReference,
  } from "$lib/utils/ideaReferences";

  interface Props {
    content: string;
    references?: readonly IdeaReference[];
    onOpen?: (reference: IdeaReference) => void;
    markdown?: boolean;
  }

  let {
    content,
    references = [],
    onOpen,
    markdown = false,
  }: Props = $props();

  let markdownRoot: HTMLDivElement | undefined = $state();
  const segments = $derived(matchIdeaReferences(content, references));
  const renderedMarkdown = $derived(renderMarkdown(content, { allowLinks: true }));

  function decorateMarkdown(root: HTMLDivElement, html: string, ideaReferences: readonly IdeaReference[]) {
    root.innerHTML = html;
    if (!ideaReferences.length) return;

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const textNodes: Text[] = [];
    let node = walker.nextNode();
    while (node) {
      const parent = node.parentElement;
      if (node.textContent && !parent?.closest("a, button, code, pre")) textNodes.push(node as Text);
      node = walker.nextNode();
    }

    for (const textNode of textNodes) {
      const matches = matchIdeaReferences(textNode.data, ideaReferences);
      if (!matches.some((segment) => segment.reference)) continue;

      const fragment = document.createDocumentFragment();
      for (const segment of matches) {
        if (!segment.reference) {
          fragment.append(document.createTextNode(segment.text));
          continue;
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "idea-reference-link";
        button.dataset.ideaReferenceId = segment.reference.id;
        button.setAttribute("aria-label", `Open idea details for ${segment.reference.label}`);
        button.textContent = segment.text;
        fragment.append(button);
      }
      textNode.replaceWith(fragment);
    }
  }


  function handleMarkdownClick(event: MouseEvent) {
    const target = event.target instanceof Element
      ? event.target.closest<HTMLButtonElement>("button[data-idea-reference-id]")
      : null;
    if (!target) return;
    const reference = references.find((candidate) => candidate.id === target.dataset.ideaReferenceId);
    if (reference) onOpen?.(reference);
  }

  $effect(() => {
    if (!markdown || !markdownRoot) return;
    const root = markdownRoot;
    decorateMarkdown(root, renderedMarkdown, references);
    root.addEventListener("click", handleMarkdownClick);
    return () => root.removeEventListener("click", handleMarkdownClick);
  });
</script>

{#if markdown}
  <div
    class="idea-reference-markdown"
    bind:this={markdownRoot}
  ></div>
{:else}
  {#each segments as segment}
    {#if segment.reference}
      <button
        type="button"
        class="idea-reference-link"
        aria-label={`Open idea details for ${segment.reference.label}`}
        onclick={() => onOpen?.(segment.reference)}
      >{segment.text}</button>
    {:else}{segment.text}{/if}
  {/each}
{/if}

<style>
  .idea-reference-markdown {
    display: contents;
  }

  :global(button.idea-reference-link) {
    appearance: none;
    border: 0;
    padding: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    font-weight: 650;
    text-align: inherit;
    text-decoration: underline;
    text-decoration-thickness: 0.08em;
    text-underline-offset: 0.14em;
    cursor: pointer;
  }

  :global(button.idea-reference-link:hover) {
    color: var(--color-accent);
  }

  :global(button.idea-reference-link:focus-visible) {
    border-radius: 0.125rem;
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>
