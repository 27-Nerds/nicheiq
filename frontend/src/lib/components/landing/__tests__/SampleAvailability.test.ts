import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import HeroBlock from '../HeroBlock.svelte';
import HowItWorksBlock from '../HowItWorksBlock.svelte';
import Pricing from '../Pricing.svelte';

afterEach(cleanup);

describe('public sample-report CTAs', () => {
  it('omits sample CTAs when the backend has no publishable sample', () => {
    const hero = render(HeroBlock, { props: { hasSampleReport: false } });
    const how = render(HowItWorksBlock, { props: { hasSampleReport: false } });

    expect(hero.queryByRole('link', { name: /sample report/i })).not.toBeInTheDocument();
    expect(how.queryByRole('link', { name: /real report/i })).not.toBeInTheDocument();
  });

  it('offers the sample only when availability is verified', () => {
    const hero = render(HeroBlock, { props: { hasSampleReport: true } });
    const how = render(HowItWorksBlock, { props: { hasSampleReport: true } });

    expect(hero.getAllByRole('link', { name: /sample report/i })).not.toHaveLength(0);
    expect(how.getByRole('link', { name: /real report/i })).toHaveAttribute('href', '/sample-report');
  });

  it('suppresses a package sample sub-link while retaining the pricing action', () => {
    const plans = [{
      id: 'founder',
      name: 'Founder',
      monthlyCredits: 20,
      priceInCents: 4900,
      interval: 'month',
      isPopular: true,
      ctaSubText: 'See the sample report',
      ctaSubUrl: '/sample-report',
    }];
    const view = render(Pricing, {
      props: { plans: plans as never, hasSampleReport: false },
    });

    expect(view.queryByRole('link', { name: 'See the sample report' })).not.toBeInTheDocument();
    expect(view.getByRole('link', { name: 'Subscribe' })).toBeInTheDocument();
  });
});
