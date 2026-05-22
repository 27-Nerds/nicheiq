<script lang="ts">
  import type { CtaConfig } from "$lib/types/cta";

  interface Props {
    ctaTexts?: Record<string, CtaConfig | null>;
  }

  let { ctaTexts }: Props = $props();

  // Show by default; only hide when the backend explicitly sets visible=false.
  // Marketing/legal can flip the cta_show_testimonials key to hide quickly without a deploy.
  const visible = $derived(ctaTexts?.cta_show_testimonials?.visible !== false);
</script>

{#if visible}
  <section class="section relative" id="testimonials">
    <div class="landing-container">
      <div class="landing-section-header-wrap">
        <div class="landing-section-label-row">
          <span class="landing-section-dot"></span>
          <span class="landing-section-label">What Founders Are Saying</span>
        </div>
        <h2 class="landing-section-h2">
          We gave early access.<br />
          <span style="color: var(--color-text-muted)">
            We asked for feedback
          </span>
        </h2>
      </div>

      <div class="testimonials-wrap">
        <div class="testimonials-grid">
          <div
            class="testimonial-card"
            style="background: var(--color-bg-surface); border-radius: var(--radius-xl); display: flex; flex-direction: column;"
          >
            <p
              style="
								font-size: clamp(var(--text-xl), 1.7vw, 1.375rem);
								font-style: italic;
								line-height: var(--leading-snug);
								color: var(--color-text-primary);
								margin-bottom: var(--space-4);
							"
            >
              "Looks like a useful tool to get a quick overview before deciding
              whether to build a product. The ideas are genuinely good — I took
              some of them. Market description, problems and opportunities look
              correct. Recommendations align well with our vision. The list of
              subreddits, top threads, and influencers — you can take it
              straight into production. Gives a lot of useful SEO info and
              immediately shows keyword distribution. Our hypothesis was clearly
              confirmed."
            </p>

            <div
              style="display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-6);"
            >
              <span class="t-tag">Accuracy</span>
              <span class="t-tag">SEO insights</span>
              <span class="t-tag">Market depth</span>
            </div>

            <div style="flex: 1;"></div>

            <div class="t-author">
              <img src="/landing/roman_d.png" alt="" class="t-avatar" />
              <p
                style="font-size: var(--text-base); color: var(--color-text-secondary); margin: 0;"
              >
                <a
                  href="https://www.linkedin.com/in/rdoroshenko/"
                  target="_blank"
                  rel="noopener noreferrer"
                  style="color: var(--color-text-primary); text-decoration: none; font-weight: var(--font-bold);"
                  >Roman Doroshenko</a
                ><br />
                CEO at Zeeks / GP at NetSolid Investments
              </p>
            </div>
          </div>

          <div
            class="testimonial-card"
            style="background: var(--color-bg-surface); border-radius: var(--radius-xl); display: flex; flex-direction: column;"
          >
            <p
              style="
								font-size: clamp(var(--text-xl), 1.7vw, 1.375rem);
								font-style: italic;
								line-height: var(--leading-snug);
								color: var(--color-text-primary);
								margin-bottom: var(--space-4);
							"
            >
              "Nice, quick, easy onboarding. Just a few questions, no
              overcomplicated flows. I like detailed explanations for
              everything, including hovering info. Competitive Landscape —
              accurate. Audience Intelligence — nice."
            </p>

            <div
              style="display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-6);"
            >
              <span class="t-tag">Easy onboarding</span>
              <span class="t-tag">Accuracy</span>
            </div>

            <div style="flex: 1;"></div>

            <div class="t-author">
              <img src="/landing/yevhen_t.png" alt="" class="t-avatar" />
              <p
                style="font-size: var(--text-base); color: var(--color-text-secondary); margin: 0;"
              >
                <span
                  style="color: var(--color-text-primary); font-weight: var(--font-bold);"
                  >Yevhen Tarasenko</span
                ><br />
                Co-founder &amp; CMO @ Apptonomy
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
{/if}

<style>
  .t-tag {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: 9px 14px;
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    line-height: 1;
  }

  .testimonials-wrap {
    overflow: hidden;
  }

  /* Author row pinned to the card bottom. Reserve a consistent height and
	   top-align so the avatar + name line up across cards regardless of how
	   many lines the role/title wraps to. */
  .t-author {
    display: flex;
    align-items: flex-start;
    gap: var(--space-4);
    width: fit-content;
    min-height: 4.5rem;
  }

  .t-avatar {
    width: 36px;
    height: 36px;
    object-fit: cover;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .testimonials-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-5);
  }

  .testimonial-card {
    padding: var(--space-12);
  }

  @media (max-width: 768px) {
    .testimonials-wrap {
      overflow: visible;
    }
    .testimonials-grid {
      display: flex;
      overflow-x: auto;
      scroll-snap-type: x mandatory;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
      gap: var(--space-4);
    }
    .testimonials-grid::-webkit-scrollbar {
      display: none;
    }
    .testimonials-grid > :global(div) {
      flex: 0 0 88%;
      scroll-snap-align: start;
    }
    .testimonial-card {
      padding: var(--space-8);
    }
  }
</style>
