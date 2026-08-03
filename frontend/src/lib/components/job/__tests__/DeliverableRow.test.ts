import { cleanup, fireEvent, render, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/state', () => ({
  page: { data: { creditBalance: 100 } },
}));

import DeliverableRow from '../DeliverableRow.svelte';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('DeliverableRow paid landing-page contract', () => {
  it('explains the output and confirms the current cost before generating', async () => {
    const onGenerate = vi.fn().mockResolvedValue(undefined);
    const view = render(DeliverableRow, {
      props: {
        label: 'Landing Page',
        status: 'pending',
        creditCost: 5,
        onGenerate,
      },
    });

    expect(view.getByText(/downloadable HTML for self-hosting/)).toBeInTheDocument();
    await fireEvent.click(view.getByRole('button', { name: 'Generate · 5 credits' }));

    expect(onGenerate).not.toHaveBeenCalled();
    expect(view.getByRole('heading', { name: 'Generate a waitlist landing page?' })).toBeInTheDocument();
    expect(view.getByText(/NicheIQ does not publish or host it/)).toBeInTheDocument();
    expect(view.getByText('One generated version per completed research run.')).toBeInTheDocument();
    expect(view.getByText(/eligible credits are returned automatically/)).toBeInTheDocument();

    await fireEvent.click(view.getByRole('button', { name: 'Generate page · 5 credits' }));
    await waitFor(() => expect(onGenerate).toHaveBeenCalledOnce());
  });

  it('shows the exact prior refund and makes retry a new confirmed purchase', async () => {
    const onGenerate = vi.fn().mockResolvedValue(undefined);
    const view = render(DeliverableRow, {
      props: {
        label: 'Landing Page',
        status: 'failed',
        creditCost: 5,
        refundedAmount: 5,
        onGenerate,
      },
    });

    expect(view.getByText('5 credits were returned from the failed attempt.')).toBeInTheDocument();
    await fireEvent.click(view.getByRole('button', { name: 'Retry · 5 credits' }));
    expect(onGenerate).not.toHaveBeenCalled();

    expect(view.getByRole('heading', { name: 'Retry landing page generation?' })).toBeInTheDocument();
    await fireEvent.click(view.getByRole('button', { name: 'Retry page · 5 credits' }));
    await waitFor(() => expect(onGenerate).toHaveBeenCalledOnce());
  });

  it('renders a concurrent-start refresh as a neutral status', () => {
    const view = render(DeliverableRow, {
      props: {
        label: 'Landing Page',
        status: 'running',
        notice: 'Landing page generation already started in another tab. Current status refreshed.',
        onGenerate: vi.fn(),
      },
    });

    expect(view.getByRole('status')).toHaveTextContent('already started in another tab');
    expect(view.queryByRole('alert')).not.toBeInTheDocument();
  });
});
