import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

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

export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();
  const userId = session?.user?.id;

  // Check for success/canceled query params
  const success = url.searchParams.get('success') === 'true';
  const canceled = url.searchParams.get('canceled') === 'true';

  // Fetch packages (public endpoint, no auth needed)
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
    return {
      billing: {
        balance: 0,
        totalPurchased: 0,
        totalUsed: 0,
        recentTransactions: [],
      } as BillingData,
      packages,
      success,
      canceled,
    };
  }

  try {
    const response = await fetchBackend('/api/billing', {
      headers: { 'X-User-ID': userId },
    });

    if (!response.ok) {
      console.error('Failed to fetch billing info:', response.statusText);
      return {
        billing: {
          balance: 0,
          totalPurchased: 0,
          totalUsed: 0,
          recentTransactions: [],
        } as BillingData,
        packages,
        success,
        canceled,
      };
    }

    const billing: BillingData = await response.json();
    return { billing, packages, success, canceled };
  } catch (error) {
    console.error('Error fetching billing info:', error);
    return {
      billing: {
        balance: 0,
        totalPurchased: 0,
        totalUsed: 0,
        recentTransactions: [],
      } as BillingData,
      packages,
      success,
      canceled,
    };
  }
};
