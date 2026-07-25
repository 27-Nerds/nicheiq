import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte({ hot: false })],
  resolve: {
    // Force client-side Svelte exports for testing (Svelte 5 compatibility)
    conditions: ['browser'],
  },
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    alias: {
      $lib: '/src/lib',
      '$app/stores': '/src/test/mocks/app-stores.ts',
      '$app/state': '/src/test/mocks/app-state.ts',
      '$app/navigation': '/src/test/mocks/app-navigation.ts',
      '$app/environment': '/src/test/mocks/app-environment.ts',
      '$env/dynamic/private': '/src/test/mocks/env.ts',
      '$env/dynamic/public': '/src/test/mocks/env.ts',
    },
  },
});
