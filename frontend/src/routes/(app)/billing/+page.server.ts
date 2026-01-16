import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:3001';

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

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();

  const userId = session?.user?.id;

  if (!userId) {
    return {
      billing: {
        balance: 0,
        totalPurchased: 0,
        totalUsed: 0,
        recentTransactions: [],
      } as BillingData,
    };
  }

  try {
    const response = await fetch(`${BACKEND_URL}/api/billing`, {
      headers: {
        'X-Internal-Service': env.INTERNAL_SERVICE_SECRET || 'dev-internal-secret',
        'X-User-ID': userId,
      },
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
      };
    }

    const billing: BillingData = await response.json();
    return { billing };
  } catch (error) {
    console.error('Error fetching billing info:', error);
    return {
      billing: {
        balance: 0,
        totalPurchased: 0,
        totalUsed: 0,
        recentTransactions: [],
      } as BillingData,
    };
  }
};
