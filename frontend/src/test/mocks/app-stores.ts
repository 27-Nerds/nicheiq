import { readable, writable } from 'svelte/store';

// Mock $page store
export const page = readable({
  url: new URL('http://localhost'),
  params: {},
  route: { id: null },
  status: 200,
  error: null,
  data: {
    session: {
      user: {
        id: 'test-user-id',
        email: 'test@example.com',
        name: 'Test User',
        image: null,
      },
    },
    creditBalance: 10,
  },
  form: null,
});

// Mock navigating store
export const navigating = readable(null);

// Mock updated store
export const updated = {
  subscribe: readable(false).subscribe,
  check: async () => false,
};
