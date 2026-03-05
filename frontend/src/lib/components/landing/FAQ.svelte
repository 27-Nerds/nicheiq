<script lang="ts">
  import { intersect } from "$lib/actions/intersect";
  import { Accordion } from "./ui";

  let isVisible = $state(false);

  // Optimized FAQs: Trust first, consolidated competitor question, common objections
  // All answers are HTML strings to support rich formatting uniformly
  const faqs = [
    {
      question: "Can I trust the numbers? Or is this AI hallucinating?",
      answer:
        "<p>Short answer: no. 80% of your report is hard data pulled from APIs—keyword volumes, source discussions, engagement metrics. Every pain point links to a specific Reddit post with post ID, upvote count, and timestamp. Click through and verify it yourself. The hybrid architecture uses 80% programmatic data assembly and 20% LLM synthesis. The data comes from APIs. AI only handles synthesis.</p>",
    },
    {
      question: "Can't I just use ChatGPT, Perplexity, or Grok?",
      answer:
        "<p>Better prompts improve output, but they can't solve architectural limitations. No AI chat tool has direct access to social platforms, real-time keyword APIs, or live community discussions. ChatGPT uses training data (months old). Perplexity crawls indexed pages (misses real-time posts). Grok excels at X/Twitter but can't access Reddit. NicheIQ connects directly to APIs for current data with source attribution on every claim.</p>",
    },
    {
      question: "How long does research take?",
      answer:
        "<p>Typically around 45 minutes. Once you submit your niche, the system autonomously runs a 16-stage research pipeline: searching social media, extracting validated pain points, calculating market size, validating pricing, and compiling your report. If there's a queue, you'll be notified when your research starts and when it's complete.</p>",
    },
    {
      question: "How do you calculate market size and pricing?",
      answer:
        "<p>Market sizing (TAM/SAM/SOM) uses real keyword search volumes from DataForSEO API - actual search demand, not AI estimates. Pricing recommendations combine competitor analysis (what similar tools charge) with willingness-to-pay signals from customer discussions. The report shows methodology so you can analyze the numbers.</p>",
    },
    {
      question: "Can I get a refund?",
      answer:
        "<p>Yes. If your report doesn't deliver, you get a full refund — the research credit will be returned to your account. If you have any other questions, please email hello@nicheiq.dev within 7 days. If a research is interrupted due to a technical issue, you'll see a Resume option and the process will continue from where it stopped. One completed report uses one research credit and includes a full niche research and a ready-to-launch landing page (optional).</p>",
    },
    {
      question: "What if my niche is too specialized?",
      answer:
        "<p>NicheIQ works best when there's active public discussion around a niche. Consumer SaaS, developer tools, and creator-focused products usually have strong coverage across social platforms. For highly specialized or very narrow B2B niches, there may not be enough public data to run a meaningful research. If that happens, the system will notify you and your research credit will be returned to your account, so you can submit another niche request. You'll never lose a credit for a research that can't be completed.</p>",
    },
    {
      question:
        "What if I don't like the proposed solution or get a NO-GO verdict?",
      answer:
        "<p>NicheIQ builds solutions around validated problems, based on real market research and demand signals. Each report includes one primary solution and two alternative directions, so you have options even if the main idea doesn't feel right. If the research results in a NO-GO verdict or isn't a fit for you, the report is still considered successfully delivered and refunds are not provided for idea outcomes. Many founders run multiple researches to explore different angles until they find an idea that truly clicks.</p>",
    },
    {
      question: "Do you have a credit-based system?",
      answer: `<p>Yes! Each research uses 20 credits: 5 for Discovery + 15 for Deep Research. Your packages:</p>
        <ul class="my-3 ml-4 space-y-1 list-disc">
          <li><strong>Starter ($19)</strong>: 20 credits = 1 complete report (Discovery + Deep Research)</li>
          <li><strong>Basic ($45)</strong>: 60 credits = 3 complete reports</li>
          <li><strong>Pro ($100)</strong>: 200 credits = 10 complete reports</li>
        </ul>
        <p>This gives you flexibility — try multiple Discovery sessions to find the right niche, then invest in Deep Research only for your best opportunities.</p>
        <p class="mt-2 font-semibold text-accent">Bonus: every package includes 1 FREE Discovery session (5 credits).</p>`,
    },
    {
      question: "Can I run multiple researches?",
      answer:
        "<p>Yes - pay per research report. Explore as many niches as you want. This is NicheIQ's strength: fast research means you can explore 5 niches in an afternoon instead of committing months to one. Most founders use it to narrow down from several niches to their best opportunity.</p>",
    },
    {
      question: "Do you store my research data?",
      answer:
        "<p>We store your reports for your account access only. Your research is 100% private - no shared database, no data sharing between customers, no marketing use of your niche ideas. NicheIQ is a tool, not a marketplace. Your research stays your competitive advantage.</p>",
    },
  ];
</script>

<section id="faq" class="section-alt" use:intersect={{ threshold: 0.1, onIntersect: () => isVisible = true }}>
  <div class="max-w-3xl mx-auto px-6 lg:px-12">
    {#if isVisible}
      <!-- Section Header -->
      <div class="text-center mb-16">
        <span class="section-label animate-fade-in">FAQ</span>
        <h2
          class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6"
        >
          Common Questions
        </h2>
      </div>

      <!-- FAQ Items - Dark Accordion Style -->
      <div class="animate-fade-in delay-300 border-t border-border">
        {#each faqs as faq}
          <Accordion title={faq.question}>
            {@html faq.answer}
          </Accordion>
        {/each}
      </div>

      <!-- Contact CTA -->
      <div class="animate-fade-in delay-400 mt-12 text-center">
        <div class="divider max-w-xs mx-auto mb-8"></div>
        <p class="text-text-muted">
          Still have questions?
          <a
            href="mailto:hello@nicheiq.dev"
            class="text-accent hover:text-accent-hover hover:underline font-medium transition-colors"
          >
            Contact us
          </a>
        </p>
      </div>
    {/if}
  </div>
</section>
