import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';
import type { SubscriptionPlan, UserSubscription } from '$lib/types/billing';

interface Transaction {
  id: string;
  type: string;
  amount: number;
  balanceAfter: number;
  description: string | null;
  createdAt: string;
}

interface BillingData {
  balance: number;
  available?: number;
  monthlyAllowance?: number;
  purchasedBalance?: number;
  monthlyAllowancePeriodEnd?: string | null;
  totalPurchased: number;
  totalUsed: number;
  recentTransactions: Transaction[];
}

interface TokenPackage {
  id: string;
  name: string;
  description: string | null;
  credits: number;
  priceInCents: number;
  isPopular: boolean;
}

const DEFAULT_BILLING: BillingData = {
  balance: 0,
  available: 0,
  monthlyAllowance: 0,
  purchasedBalance: 0,
  monthlyAllowancePeriodEnd: null,
  totalPurchased: 0,
  totalUsed: 0,
  recentTransactions: [],
};

// Subscription plans (public). Kept out of the main flow so the
// packages→billing fetch order (covered by tests) is preserved.
async function fetchPlans(): Promise<SubscriptionPlan[]> {
  try {
    const plansResponse = await fetchBackend('/api/billing/plans');
    if (plansResponse?.ok) {
      const data = await plansResponse.json();
      return data.plans || [];
    }
  } catch (error) {
    console.error('Error fetching plans:', error);
  }
  return [];
}

async function fetchSubscription(userId: string): Promise<UserSubscription | null> {
  try {
    const subResponse = await fetchBackend('/api/billing/subscription', {
      headers: { 'X-User-ID': userId },
    });
    if (subResponse?.ok) {
      const data = await subResponse.json();
      return data.subscription ?? null;
    }
  } catch (error) {
    console.error('Error fetching subscription:', error);
  }
  return null;
}

export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();
  const userId = session?.user?.id;

  // Check for success/canceled query params (one-time + subscription)
  const success = url.searchParams.get('success') === 'true';
  const canceled = url.searchParams.get('canceled') === 'true';
  const subSuccess = url.searchParams.get('sub_success') === 'true';
  const subCanceled = url.searchParams.get('sub_canceled') === 'true';

  // Fetch packages (public endpoint, no auth needed) — FIRST fetch.
  let packages: TokenPackage[] = [];
  try {
    const packagesResponse = await fetchBackend('/api/billing/packages');
    if (packagesResponse.ok) {
      const data = await packagesResponse.json();
      packages = data.packages || [];
    }
  } catch (error) {
    console.error('Error fetching packages:', error);
  }

  if (!userId) {
    const plans = await fetchPlans();
    return {
      billing: { ...DEFAULT_BILLING },
      packages,
      plans,
      subscription: null as UserSubscription | null,
      success,
      canceled,
      subSuccess,
      subCanceled,
    };
  }

  // Billing — SECOND fetch (test relies on this call order).
  let billing: BillingData = { ...DEFAULT_BILLING };
  try {
    const response = await fetchBackend('/api/billing', {
      headers: { 'X-User-ID': userId },
    });
    if (response.ok) {
      billing = await response.json();
    } else {
      console.error('Failed to fetch billing info:', response.statusText);
    }
  } catch (error) {
    console.error('Error fetching billing info:', error);
  }

  const [plans, subscription] = await Promise.all([
    fetchPlans(),
    fetchSubscription(userId),
  ]);

  return { billing, packages, plans, subscription, success, canceled, subSuccess, subCanceled };
};
