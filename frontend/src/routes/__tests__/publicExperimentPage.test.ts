import { cleanup, fireEvent, render, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import PublicExperimentPage from '../(experiment)/validate/[publicToken]/+page.svelte';

const mocks = vi.hoisted(() => ({
  recordPublicExperimentEvent: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('$lib/api', () => mocks);

const data = {
  session: null,
  availableProviders: { google: false, github: false },
  publicToken: 'opaque-public-token',
  test: {
    viewToken: 'signed.view.token',
    artifact: {
      version: 1,
      headline: 'Signal Desk for operators',
      promise: 'Find recurring buyer signals before committing a build cycle.',
      ctaLabel: "I'm interested",
      disclosure: {
        title: 'This is a concept test',
        body: 'This product is not available yet. No account or payment was created.',
      },
    },
  },
};

describe('public experiment page', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('records exposure and interest, then immediately reveals the concept-test disclosure', async () => {
    const view = render(PublicExperimentPage, { props: { data } });

    expect(view.getByRole('heading', { name: 'Signal Desk for operators' })).toBeInTheDocument();
    expect(view.queryByText(/pass threshold|market fit|research score/i)).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.recordPublicExperimentEvent).toHaveBeenCalledWith(
      'opaque-public-token',
      expect.objectContaining({
        viewToken: 'signed.view.token',
        type: 'STIMULUS_EXPOSED',
      }),
    ));

    await fireEvent.click(view.getByRole('button', { name: "I'm interested" }));

    expect(await view.findByRole('heading', { name: 'This is a concept test' })).toBeInTheDocument();
    expect(view.getByText(/No account or payment was created/)).toBeInTheDocument();
    await waitFor(() => {
      const eventTypes = mocks.recordPublicExperimentEvent.mock.calls.map((call) => call[1].type);
      expect(eventTypes).toContain('CTA_CLICKED');
      expect(eventTypes).toContain('FAKE_DOOR_DISCLOSED');
    });
  });

  it('shows a neutral closed state without exposing the previous offer', () => {
    const view = render(PublicExperimentPage, {
      props: {
        data: {
          session: null,
          availableProviders: { google: false, github: false },
          publicToken: 'closed-token',
          test: null,
        },
      },
    });

    expect(view.getByRole('heading', { name: /no longer collecting responses/i })).toBeInTheDocument();
    expect(view.queryByText('Signal Desk for operators')).not.toBeInTheDocument();
  });
});
