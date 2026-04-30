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
