import { PrismaClient } from '@prisma/client';
import { CONFIG } from '../config.js';

// Create a singleton Prisma client
export const prisma = new PrismaClient({
  log: CONFIG.isDev ? ['query', 'info', 'warn', 'error'] : ['error'],
});

// Test connection on startup
export async function testConnection(): Promise<boolean> {
  try {
    await prisma.$queryRaw`SELECT 1`;
    return true;
  } catch (error) {
    console.error('Database connection failed:', error);
    return false;
  }
}
