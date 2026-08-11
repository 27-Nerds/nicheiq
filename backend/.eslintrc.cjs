/**
 * Phase 5.4 — minimal ESLint config encoding the catalog ingestion barrier.
 *
 * The architectural invariant is: public catalog runtime is DB-only.
 * `routes/publicCatalog.ts` (and the public-rendering exports of
 * `services/catalogService.ts`) MUST NOT import the ingestion-layer
 * helpers that read JobAsset files (`getJobAsset`, `extractOrCreateResearchContext`,
 * `loadReportJson`) or perform direct filesystem reads.
 *
 * The guardrail test in `routes/__tests__/publicCatalog.guardrail.test.ts`
 * enforces this at test-time. This ESLint rule enforces it at lint-time.
 */
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
  },
  rules: {},
  overrides: [
    {
      files: ['src/**/*.ts'],
      excludedFiles: [
        'src/**/__tests__/**',
        // Existing artifact-only consumers are explicit legacy exceptions. New
        // production modules are denied by default and must use the context service.
        'src/routes/discoveryShares.ts',
        'src/routes/jobs.ts',
        'src/routes/selectionChallenges.ts',
        'src/routes/selectionExperiments.ts',
        'src/routes/selectionFinalDecisions.ts',
        'src/services/currentSelectionContext.ts',
      ],
      rules: {
        'no-restricted-imports': [
          'error',
          {
            patterns: [
              {
                group: [
                  '**/assetService.js',
                  '**/assetService',
                  '**/selectionBoundary/rawPreviewReport.js',
                  '**/selectionBoundary/rawPreviewReport',
                ],
                importNames: ['getPreviewReportForJob'],
                message:
                  'Selection boundary: raw preview reports are not a producer API. Use loadCurrentSelectionContext().',
              },
            ],
          },
        ],
      },
    },
    {
      files: ['src/**/*.ts'],
      excludedFiles: [
        'src/**/__tests__/**',
        // Grandfathered mutation/record endpoints. The list is intentionally
        // exact: a new producer file fails closed instead of inheriting access.
        'src/routes/discoveryShares.ts',
        // Legacy transport/adapters still expose pool-shaped data to established
        // non-producer consumers. New modules remain denied by default.
        'src/routes/events.ts',
        'src/routes/founderFit.ts',
        'src/routes/jobs.ts',
        'src/routes/selectionAssumptions.ts',
        'src/routes/selectionChallenges.ts',
        'src/routes/selectionExperiments.ts',
        'src/routes/selectionFinalDecisions.ts',
        'src/routes/selectionFounderFitReshape.ts',
        'src/routes/selectionIdeaNarrowing.ts',
        'src/routes/selectionOwnerEvidence.ts',
        'src/routes/workers.ts',
        'src/services/currentSelectionContext.ts',
        'src/services/selectionDecisionStateService.ts',
        'src/services/selectionOwnedJobService.ts',
        'src/services/selectionReminderService.ts',
        'src/utils/jobFormatter.ts',
      ],
      rules: {
        'no-restricted-syntax': [
          'error',
          {
            selector: "Property[key.name='solutionIdeas'][value.value=true]",
            message:
              'Selection boundary: direct Job.solutionIdeas selection is forbidden in new modules. Use loadCurrentSelectionContext().',
          },
          {
            selector: "MemberExpression[computed=false][property.name='solutionIdeas']",
            message:
              'Selection boundary: direct Job.solutionIdeas reads are forbidden in new modules. Use loadCurrentSelectionContext().',
          },
          {
            selector: "MemberExpression[computed=true][property.value='solutionIdeas']",
            message:
              'Selection boundary: direct Job.solutionIdeas reads are forbidden in new modules. Use loadCurrentSelectionContext().',
          },
          {
            selector: "ObjectPattern > Property[key.name='solutionIdeas']",
            message:
              'Selection boundary: destructuring Job.solutionIdeas is forbidden in new modules. Use loadCurrentSelectionContext().',
          },
        ],
      },
    },
    {
      files: ['src/routes/publicCatalog.ts'],
      rules: {
        'no-restricted-imports': [
          'error',
          {
            patterns: [
              {
                group: ['*/services/researchContextService*', '*services/researchContextService*'],
                message:
                  'Phase 5.4 invariant: public catalog runtime is DB-only. Ingestion helpers (extractOrCreateResearchContext, loadReportJson) must not be imported here.',
              },
              {
                group: ['*/services/jobService*', '*services/jobService*'],
                message:
                  'Phase 5.4 invariant: public catalog runtime must not call getJobAsset / addJobAsset.',
              },
              {
                group: ['fs', 'fs/promises', 'node:fs', 'node:fs/promises'],
                message:
                  'Phase 5.4 invariant: public catalog runtime must not read files. CatalogResearchContext is the durable projection.',
              },
            ],
          },
        ],
      },
    },
  ],
};
