import { prisma } from './db.js';
import { getRedis } from './redis.js';

const CACHE_KEY = 'public_stats:v3';
const CACHE_TTL = 300; // 5 minutes

const redis = getRedis();

export interface PublicStats {
  // Count of COMPLETED research jobs (used for "Reports run" achievement).
  completedJobs: number;
  // Total registered users. null = unavailable
  // (the landing page hides the social-proof line rather than fabricate a number).
  activeFounders: number | null;
}

export async function getPublicStats(): Promise<PublicStats> {
  try {
    const cached = await redis.get(CACHE_KEY);
    if (cached) {
      return JSON.parse(cached) as PublicStats;
    }

    const [completedJobs, totalUsers] = await Promise.all([
      prisma.job.count({ where: { status: 'COMPLETED' } }),
      prisma.user.count(),
    ]);

    const stats: PublicStats = {
      completedJobs,
      activeFounders: totalUsers,
    };

    await redis.setex(CACHE_KEY, CACHE_TTL, JSON.stringify(stats));
    return stats;
  } catch (error) {
    console.error('Failed to get public stats:', error);
    // Keep the legacy reports-run fallback; hide the founders line (null).
    return { completedJobs: 47, activeFounders: null };
  }
}
