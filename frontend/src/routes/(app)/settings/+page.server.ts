import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';

interface NotificationPreferences {
  emailEnabled: boolean;
  emailOnJobStart: boolean;
  emailOnJobComplete: boolean;
  emailOnJobError: boolean;
}

interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  image: string | null;
  createdAt: string;
  jobCount: number;
}

export const load: PageServerLoad = async ({ parent }) => {
  const { session } = await parent();
  const userId = session?.user?.id;

  const defaultPreferences: NotificationPreferences = {
    emailEnabled: true,
    emailOnJobStart: true,
    emailOnJobComplete: true,
    emailOnJobError: true,
  };

  if (!userId) {
    return {
      notificationPreferences: defaultPreferences,
      userProfile: null,
    };
  }

  const headers = { 'X-User-ID': userId };

  // Fetch notification preferences and user profile in parallel
  const [prefsResponse, profileResponse] = await Promise.all([
    fetchBackend(`/api/users/${userId}/notification-preferences`, { headers }).catch(() => null),
    fetchBackend(`/api/users/${userId}`, { headers }).catch(() => null),
  ]);

  let notificationPreferences = defaultPreferences;
  let userProfile: UserProfile | null = null;

  if (prefsResponse?.ok) {
    try {
      notificationPreferences = await prefsResponse.json();
    } catch {
      console.error('Failed to parse notification preferences');
    }
  }

  if (profileResponse?.ok) {
    try {
      userProfile = await profileResponse.json();
    } catch {
      console.error('Failed to parse user profile');
    }
  }

  return {
    notificationPreferences,
    userProfile,
  };
};
