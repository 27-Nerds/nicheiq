import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  /**
   * TEST-ONLY. `src/utils/buyerFacingCaveat.ts` is a port of two frontend modules, and
   * `utils/__tests__/buyerFacingCaveat.drift.test.ts` holds it to the original by importing the
   * frontend authority at runtime and diffing the output. Nothing under `src/` may import
   * through this alias: `tsc` has no `$lib` path and the API ships from `dist` without the
   * frontend sources, so a production import would compile here and fail in the container.
   */
  resolve: {
    alias: {
      $lib: fileURLToPath(new URL('../frontend/src/lib', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'node',
    include: ['src/**/*.test.ts', 'tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.test.ts', 'src/index.ts'],
    },
  },
});
