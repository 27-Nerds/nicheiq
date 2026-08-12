NicheIQ is a staged research pipeline rather than one prompt. Narrow model-assisted and deterministic steps handle search planning, relevance filtering, pain extraction, audience mapping, ideation, verification, scoring, and report synthesis. The stages pass structured records forward so later claims can be traced back to the material that produced them.

## Narrow jobs, explicit handoffs

Different parts of the workflow need different inputs and checks. Search planning works from the niche frame. Pain extraction works from captured discussion. Idea evaluation works from the candidate, its source pains, competitors, and data requirements. Deep Research then works from the exact scope the owner confirmed.

The implementation contains many specialist roles, but exact counts are not a useful product promise: roles, models, and stage boundaries change as the pipeline evolves. The durable point is separation of duties. Generation, independent review, deterministic validation, and final synthesis do not all rely on one unchallenged response.

## Live sources and stored evidence

Discovery can collect Reddit and Hacker News discussion, then use web and keyword-search providers in later checks. Availability depends on the run configuration and the source itself. Public discussion is treated as an incomplete, time-sensitive sample, not as a census of a market.

Captured social text is fenced as untrusted content before it reaches model-assisted steps. Discovery pain quotes go through a source-grounding check against captured post text. Source attribution can still be incomplete, so the interface and report must preserve caveats rather than present an unresolved mapping as verified.

## Models are configured per task

Stages can use different configured models for generation, review, classification, and synthesis. Some choices have task-specific evaluation or A/B evidence in the engineering repository; that does not mean every prompt or model change has been proven in a live customer experiment. Automated tests protect schemas, state transitions, and deterministic rules, while model quality still requires ongoing evaluation on real examples.

## Checks do not manufacture support

Independent calibration can replace a generator's scores, and deterministic rules can cap scores when known constraints make a high value unsupported. Other checks can leave a value unchanged or abstain. The important boundary is that missing evidence is not converted into positive evidence.

Failures are handled according to the stage. Some non-critical steps use an explicitly recorded fallback or caveat; critical failures can stop the run. A missing resource should be shown as unavailable, not silently rendered as a finding of "none."

## What this means for the report

The result is still AI-assisted research. Scores, growth estimates, and market sizes are directional estimates, not guarantees. Use the linked evidence, caveats, and calculation explanations to understand why a value appears. The selection tools can help compare or challenge the captured case, but they do not rewrite Discovery scores. Only the exact scope shown at confirmation enters the paid Deep Research run.
