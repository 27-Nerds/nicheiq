export const page = {
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
    // (app)/+layout.server.ts returns this on every navigation, so any component
    // rendered under an authenticated route always has it. Mirrored here because
    // the analyst surface reads the grant before offering a composer.
    featureAccess: { analyst: true, decisionTools: true },
  },
  form: null,
  state: {},
};
