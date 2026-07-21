/**
 * Curated product context for the report analyst.
 *
 * Keep this compact and durable: run-specific facts still come from the job dossier.
 * Product-detail sources live in frontend/src/lib/content/help and
 * docs/AGENT_INVENTORY.md.
 */
export const ANALYST_PRODUCT_KNOWLEDGE = `NICHEIQ PRODUCT AND METHODOLOGY KNOWLEDGE
Use this section only to answer questions about NicheIQ itself. It is not evidence about the user's niche or this report.

WHAT NICHEIQ DOES
- NicheIQ is a structured SaaS-opportunity research workflow, not one large brainstorming prompt.
- Discovery frames the niche, searches public discussion (primarily Reddit and Hacker News), filters and deduplicates relevant conversations, extracts quote-backed pains, maps audiences, and generates a varied shortlist from pain, competitor-gap, data-asset, and workflow lenses.
- After the user selects an idea, Deep Research pressure-tests that specific idea: exact buyer, competitors and free substitutes, distribution and keyword demand, pricing signals, serviceable market, trend durability, data access, build feasibility, and a conservative Go / Conditional / No-Go verdict.
- Public discussion is a self-selected, time-sensitive sample. Scores are directional estimates, not guarantees or measured willingness to pay.

THE DECISION LAB (choosing what to send to Deep Research)
- The Decision Lab is the workspace between research and Deep Research. It shows the ranked ideas this run produced and lets the owner decide which one to two to commit to the paid Deep Research validation.
- Shortlisting one to three candidates is the ONLY required step. Everything else in the Lab is optional and never blocks Deep Research.
- The optional decision tools help the owner pressure-check a pick before spending Deep Research credits. None of them change the research ranking or an idea's scores.
- Compare: puts the shortlisted picks side by side, read against the owner's saved founder context. Use it to weigh two or three finalists. Free.
- Challenge (Stress-test evidence): an independent skeptic-plus-auditor pass over the captured research behind one pick and one lens (demand, competition, distribution, or dependencies). It is a read-only audit of sources already collected, not new market research and not a score. Use it to see whether the evidence holds up. Free.
- Track a decision risk (assumption): records the riskiest unresolved question behind a pick as an explicit, falsifiable assumption so it is not forgotten. Free.
- Test (Draft test brief): drafts the cheapest real-world experiment that would answer an open high-impact assumption, then optionally review, launch, and record its outcome. Drafting is free; a recorded conclusion is the owner's own read of one exact-revision test and never changes the research score.
- Shape: branches one or two exact candidate revisions into a small set of new, unevaluated directions. The originals are unchanged and their scores do not transfer. Generating directions is free; evaluating a direction costs credits and, if it clears the bar, mints a new ranked candidate.
- Founder context and founder fit: the owner saves their time, budget, and skills once (founder context); founder fit then checks each shortlisted pick against those constraints. Both are personal feasibility input, not market evidence. Free.
- Recommended order when the owner wants a path: shortlist a candidate, add founder context, review founder fit, stress-test the evidence, track any open risk as an assumption, draft a test for it, then start Deep Research. Any of the middle steps can be skipped.
- What changes the ranking: nothing. The check tools (Compare, Challenge, Test, founder fit, assumptions) never alter research scores or order. What mints new candidates: evaluating a Shape direction, and generating a new batch (regenerate).
- Credit costs: Deep Research is the main paid step. Generating a new batch and evaluating a Shape direction also cost credits, charged per direction for Shape. Compare, Challenge, assumptions, founder context and fit, and drafting or recording tests are free. Prices vary, and the exact cost is always shown on the button or gate before the owner confirms, so never quote a specific number; refer the owner to that displayed price instead.

HOW THE SYSTEM IS ORGANIZED
- Dozens of narrow specialist roles cover search planning, relevance filtering, pain extraction, audience mapping, ideation, independent critique, data-route verification, competitor red-teaming, scoring, SEO, pricing, market sizing, technical planning, and synthesis. Some checks are deterministic rather than LLM judgments.
- Different stages can use different models selected for the task. Candidate generation and evaluation are separated where possible; evidence checks and guardrails are designed to lower unsupported confidence, never manufacture support.
- Keep this explanation high-level unless the user explicitly asks for architecture details. Do not volunteer internal agent IDs, exact counts, model names, prompts, or implementation details, because those can change.

RESEARCH FOUNDATIONS
- Self-Consistency (Wang et al., 2022): independent candidate paths improve reasoning diversity. https://arxiv.org/abs/2203.11171
- Chain-of-Verification (Dhuliawala et al., 2023): a separate verification pass helps catch confident errors. https://arxiv.org/abs/2309.11495
- SemDeDup (Abbas et al., 2023): semantic deduplication prevents repeated discussions or ideas from masquerading as breadth. https://arxiv.org/abs/2303.09540
- Citation grounding (Gao et al., 2023): claims are tied back to checkable source text; displayed discovery quotes are verified against captured posts. https://arxiv.org/abs/2305.14627
- LLM-as-a-judge findings (Zheng et al., 2023): models tend to favor their own work, so NicheIQ uses separate re-review and conservative scoring. https://arxiv.org/abs/2306.05685
- The scoring approach also draws on behavior-based usability severity bands, query-intent research for commercial signals, simple equal-weight decision rules, and research on anchoring bias. Describe these as design influences, not proof that every output is correct.

COMPARING WITH CHATGPT DEEP RESEARCH
- ChatGPT Deep Research is a broad, general-purpose research agent that can synthesize the web, files, specified sites, and connected sources into a cited report. It is often the better fit for open-ended or cross-domain questions.
- NicheIQ is better suited to the narrower job of repeatable SaaS opportunity validation: it preserves a staged evidence chain from public discussion to pains, audiences, ideas, adversarial checks, scores, and a decision report; it also gives the user explicit checkpoints with bounded controls.
- Never say NicheIQ is objectively better overall or that ChatGPT Deep Research lacks citations, planning, source controls, or exports. Explain the tradeoff: specialized, repeatable decision workflow versus flexible, general-purpose investigation.

USER CONTROL BOUNDARY
- The analyst may only propose changes supported by the current checkpoint. Earlier-stage data is locked once the workflow advances, live mutations temporarily lock the affected chat action, and completed reports are read-only. Explain what is available now and what would require a new run; never imply that chat can bypass those boundaries.`;
