<script lang="ts">
  import {
    GENERATION_SLIDES,
    DISCOVERY_SLIDES,
    type GenerationSlide,
  } from "$lib/data/previewPlaceholders";

  interface Props {
    currentStage?: number;
    phase?: 'discovery' | 'deep_research';
  }

  let { currentStage, phase = 'deep_research' }: Props = $props();

  const slides: GenerationSlide[] = $derived(
    phase === 'discovery' ? DISCOVERY_SLIDES : GENERATION_SLIDES
  );
  const totalSlides = $derived(slides.length);

  let currentSlide = $state(0);
  let isHovered = $state(false);
  let transitionDuration = $state(300);

  // Track which slide was last highlighted by stage progress
  let lastHighlightedStage = $state<number | undefined>(undefined);

  // Auto-advance timer: pauses on hover, resets on manual navigation
  $effect(() => {
    if (isHovered) return;

    const id = setInterval(() => {
      transitionDuration = 300;
      currentSlide = (currentSlide + 1) % totalSlides;
    }, 8000);

    return () => clearInterval(id);
  });

  // When a related stage completes, jump to that slide briefly
  $effect(() => {
    if (currentStage == null) return;
    if (currentStage === lastHighlightedStage) return;

    const matchIndex = slides.findIndex(
      (s) => s.relatedStage === currentStage,
    );
    if (matchIndex >= 0) {
      lastHighlightedStage = currentStage;
      transitionDuration = 300;
      currentSlide = matchIndex;
    }
  });

  function goToSlide(index: number) {
    transitionDuration = 200;
    currentSlide = index;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "ArrowLeft") {
      goToSlide((currentSlide - 1 + totalSlides) % totalSlides);
    } else if (e.key === "ArrowRight") {
      goToSlide((currentSlide + 1) % totalSlides);
    }
  }

  const activeSlide = $derived(slides[currentSlide]);
</script>

<div
  class="slideshow"
  role="region"
  aria-label="Generation progress slideshow"
  aria-roledescription="carousel"
  tabindex="-1"
  onmouseenter={() => (isHovered = true)}
  onmouseleave={() => (isHovered = false)}
  onkeydown={handleKeydown}
>
  <!-- Slide content area -->
  <div class="slide-viewport">
    {#key currentSlide}
      <div
        class="slide"
        role="tabpanel"
        aria-label="Slide {currentSlide + 1} of {totalSlides}"
        style="--transition-duration: {transitionDuration}ms"
      >
        <h3 class="slide-title">{activeSlide.title}</h3>
        <p class="slide-description">{activeSlide.description}</p>
        <ul class="slide-bullets">
          {#each activeSlide.bullets as bullet}
            <li class="slide-bullet">&rarr; {bullet}</li>
          {/each}
        </ul>
      </div>
    {/key}
  </div>

  <!-- Bottom controls -->
  <div class="slide-controls">
    <div class="slide-dots" role="tablist" aria-label="Slide navigation">
      {#each slides as _, i}
        <button
          class="slide-dot"
          class:active={i === currentSlide}
          role="tab"
          aria-selected={i === currentSlide}
          aria-label="Go to slide {i + 1}"
          onclick={() => goToSlide(i)}
        ></button>
      {/each}
    </div>

    <span class="slide-counter">
      {currentSlide + 1} / {totalSlides}
    </span>
  </div>
</div>

<style>
  .slideshow {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    background: var(--color-bg-surface);
    overflow: hidden;
  }

  .slide-viewport {
    position: relative;
    min-height: 160px;
    overflow: hidden;
  }

  .slide {
    animation: slideFadeIn var(--transition-duration) ease-out;
  }

  @keyframes slideFadeIn {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .slide-title {
    font-family: var(--font-display);
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 var(--space-2) 0;
  }

  .slide-description {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: 0 0 var(--space-4) 0;
    line-height: 1.5;
  }

  .slide-bullets {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .slide-bullet {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
    line-height: 1.5;
  }

  /* Bottom controls */
  .slide-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: var(--space-6);
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .slide-dots {
    display: flex;
    gap: var(--space-2);
  }

  .slide-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: none;
    background: var(--color-border-emphasis);
    cursor: pointer;
    padding: 0;
    transition: background-color 0.15s ease;
  }

  .slide-dot:hover {
    background: var(--color-text-muted);
  }

  .slide-dot.active {
    background: var(--color-accent);
  }

  .slide-dot:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .slide-counter {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    letter-spacing: 0.05em;
    font-variant-numeric: tabular-nums;
  }
</style>
