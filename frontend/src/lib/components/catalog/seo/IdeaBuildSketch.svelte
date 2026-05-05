<script lang="ts">
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import type { AudienceSignals } from "$lib/types/publicCatalog.js";
  import Chip from "./Chip.svelte";

  // Build sketch panel for /idea/[slug]. Surfaces idea-specific fields:
  // core_features, target_personas, pricing_strategy, estimated_development_time,
  // technical_approach, programmatic_seo_opp, estimated_cac_organic,
  // estimated_indexable_pages, differentiation_factors. Optional GTM signals
  // footer pulls from the niche-wide AudienceSignals payload (hidden when absent).

  interface Props {
    idea: IdeaPreview;
    audienceSignals?: AudienceSignals | null;
  }

  let { idea, audienceSignals = null }: Props = $props();

  const messagingFrameworks = $derived(
    Array.isArray(audienceSignals?.messagingFrameworks)
      ? audienceSignals.messagingFrameworks.filter((s): s is string => typeof s === "string")
      : [],
  );
  const recommendedChannels = $derived(
    Array.isArray(audienceSignals?.recommendedChannels)
      ? audienceSignals.recommendedChannels.filter((s): s is string => typeof s === "string")
      : [],
  );
  const contentPreferences = $derived(
    typeof audienceSignals?.contentPreferences === "string" && audienceSignals.contentPreferences.trim() !== ""
      ? audienceSignals.contentPreferences
      : null,
  );
  const hasGtm = $derived(
    messagingFrameworks.length > 0 || recommendedChannels.length > 0 || contentPreferences !== null,
  );

  const formatPages = (n: number | null): string | null =>
    n == null ? null : new Intl.NumberFormat('en-US').format(n);

  const features = $derived(
    Array.isArray(idea.core_features)
      ? idea.core_features.filter((f): f is string => typeof f === 'string' && f.trim() !== '')
      : [],
  );
  const personas = $derived(
    Array.isArray(idea.target_personas)
      ? idea.target_personas.filter((p): p is string => typeof p === 'string' && p.trim() !== '')
      : [],
  );
  const differentiators = $derived(
    Array.isArray(idea.differentiation_factors)
      ? idea.differentiation_factors.filter((d): d is string => typeof d === 'string' && d.trim() !== '')
      : [],
  );

  const indexablePagesFmt = $derived(formatPages(idea.estimated_indexable_pages));

  // Svelte 5 idiom — wrap whole panel in {#if hasContent} so the route can
  // call <IdeaBuildSketch> unconditionally and the section header can hide
  // when there's nothing to render. The route shares the same flag for the
  // SectionDivider above.
  const hasContent = $derived(
    features.length > 0 ||
      personas.length > 0 ||
      differentiators.length > 0 ||
      !!idea.pricing_strategy ||
      !!idea.estimated_development_time ||
      !!idea.estimated_cac_organic ||
      indexablePagesFmt !== null ||
      !!idea.technical_approach ||
      !!idea.why_it_works ||
      !!idea.conventional_approach ||
      !!idea.innovation_angle ||
      !!idea.estimated_cac_paid ||
      hasGtm,
  );
</script>

{#if hasContent}
  <div class="sketch">
    <div class="grid">
      {#if features.length > 0 || personas.length > 0}
        <section class="left">
          {#if features.length > 0}
            <h3 class="block-label">Core features</h3>
            <ol class="features">
              {#each features as f, i}
                <li>
                  <span class="num">{String(i + 1).padStart(2, '0')}</span>
                  <span class="text">{f}</span>
                </li>
              {/each}
            </ol>
          {/if}
          {#if personas.length > 0}
            <div class="personas">
              <h4 class="block-label">Target personas</h4>
              <div class="chips">
                {#each personas as p}
                  <Chip label={p} />
                {/each}
              </div>
            </div>
          {/if}
        </section>
      {/if}

      <section class="right">
        {#if idea.pricing_strategy}
          <div class="kv">
            <span class="k">Pricing</span>
            <span class="v">{idea.pricing_strategy}</span>
          </div>
        {/if}
        {#if idea.estimated_development_time}
          <div class="kv">
            <span class="k">Dev time</span>
            <span class="v">{idea.estimated_development_time}</span>
          </div>
        {/if}
        {#if idea.estimated_cac_organic}
          <div class="kv">
            <span class="k">CAC (organic)</span>
            <span class="v">
              {idea.estimated_cac_organic}
              {#if idea.estimated_cac_paid}
                <span class="cac-paid">(vs {idea.estimated_cac_paid} paid)</span>
              {/if}
            </span>
          </div>
        {/if}
        {#if indexablePagesFmt !== null}
          <div class="kv">
            <span class="k">Indexable pages</span>
            <span class="v mono">{indexablePagesFmt}</span>
          </div>
        {/if}
        {#if idea.technical_approach}
          <div class="kv stack">
            <span class="k">Technical approach</span>
            <span class="v">{idea.technical_approach}</span>
          </div>
        {/if}
        <!-- programmatic_seo_opportunity is rendered in the route's Section 5
             where it has room for the full markdown render. The build sketch
             keeps the SEO data tight (Indexable pages + Technical approach). -->
      </section>
    </div>

    {#if idea.conventional_approach || idea.innovation_angle}
      <div class="innovation">
        <h4 class="block-label">Innovation breakdown</h4>
        <div class="innovation-grid">
          {#if idea.conventional_approach}
            <div class="innovation-box">
              <span class="innovation-label muted">Conventional path</span>
              <p>{idea.conventional_approach}</p>
            </div>
          {/if}
          {#if idea.innovation_angle}
            <div class="innovation-box angle">
              <span class="innovation-label">What's different</span>
              <p>{idea.innovation_angle}</p>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    {#if differentiators.length > 0}
      <div class="diff">
        <h4 class="block-label">What makes this stand out</h4>
        <ul>
          {#each differentiators as d}
            <li>{d}</li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if hasGtm}
      <div class="gtm">
        <h4 class="block-label">GTM signals</h4>
        <div class="gtm-rows">
          {#if messagingFrameworks.length > 0}
            <div class="gtm-row">
              <span class="gtm-key">Messaging angles</span>
              <div class="gtm-chips">
                {#each messagingFrameworks as m}
                  <Chip label={m} />
                {/each}
              </div>
            </div>
          {/if}
          {#if recommendedChannels.length > 0}
            <div class="gtm-row">
              <span class="gtm-key">Channels to win on</span>
              <div class="gtm-chips">
                {#each recommendedChannels as c}
                  <Chip label={c} />
                {/each}
              </div>
            </div>
          {/if}
          {#if contentPreferences}
            <div class="gtm-row">
              <span class="gtm-key">Content format</span>
              <p class="gtm-prose">{contentPreferences}</p>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .sketch {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    padding: 24px 28px;
    margin: 0 0 36px;
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 32px;
  }
  @media (max-width: 800px) {
    .grid {
      grid-template-columns: 1fr;
      gap: 28px;
    }
  }
  .left,
  .right {
    display: flex;
    flex-direction: column;
    gap: 18px;
    min-width: 0;
  }
  .block-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin: 0 0 8px;
  }
  .features {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .features li {
    display: grid;
    grid-template-columns: 28px 1fr;
    gap: 10px;
    align-items: baseline;
  }
  .features .num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
  }
  .features .text {
    font-size: 14px;
    line-height: 1.45;
    color: var(--color-text-primary);
  }
  .personas .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .kv {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 10px;
    align-items: baseline;
    padding-bottom: 10px;
    border-bottom: 1px dashed var(--color-border);
  }
  .kv:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
  .kv.stack {
    grid-template-columns: 1fr;
    gap: 4px;
  }
  .k {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
    font-weight: 600;
  }
  .v {
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-primary);
  }
  .v.mono {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 600;
  }
  /* Paid CAC comparison appended inline to the organic CAC value. */
  .cac-paid {
    color: var(--color-text-muted);
    font-size: 12px;
  }
  /* Innovation breakdown two-box section. Hairline borders only;
     accent left-stripe on the "what's different" box matches catalog idiom
     (no rounded bg-color cards, those belong to /job-app). */
  .innovation {
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid var(--color-border);
  }
  .innovation-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 8px;
  }
  .innovation-box {
    border: 1px solid var(--color-border);
    padding: 14px 16px;
    border-radius: 4px;
  }
  .innovation-box.angle {
    border-left: 3px solid var(--color-accent);
    border-radius: 0 4px 4px 0;
  }
  .innovation-label {
    display: block;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-accent-muted);
    margin-bottom: 6px;
  }
  .innovation-label.muted {
    color: var(--color-text-muted);
  }
  .innovation-box p {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-primary);
  }
  @media (max-width: 700px) {
    .innovation-grid {
      grid-template-columns: 1fr;
    }
  }
  .diff {
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid var(--color-border);
  }
  .diff ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .diff li {
    position: relative;
    padding-left: 18px;
    font-size: 14px;
    line-height: 1.5;
    color: var(--color-text-primary);
  }
  .diff li::before {
    content: "·";
    position: absolute;
    left: 4px;
    top: -2px;
    font-size: 22px;
    line-height: 1;
    color: var(--color-text-muted);
  }
  /* GTM signals footer */
  .gtm {
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid var(--color-border);
  }
  .gtm-rows {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .gtm-row {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 14px;
    align-items: baseline;
  }
  .gtm-key {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .gtm-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .gtm-prose {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-primary);
  }
  @media (max-width: 700px) {
    .gtm-row {
      grid-template-columns: 1fr;
      gap: 4px;
    }
  }
</style>
