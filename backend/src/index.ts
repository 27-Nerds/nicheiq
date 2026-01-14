import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import { CONFIG, validateConfig } from './config.js';
import { jobsRouter } from './routes/jobs.js';
import { eventsRouter } from './routes/events.js';
import { healthRouter } from './routes/health.js';
import { authRouter } from './routes/auth.js';
import { usersRouter } from './routes/users.js';
import { prisma } from './services/db.js';

// Validate configuration
validateConfig();

const app = express();

// Middleware
app.use(cors({
  origin: CONFIG.corsOrigins,
  credentials: true,
}));
app.use(express.json());

// Request logging in development
if (CONFIG.isDev) {
  app.use((req: Request, _res: Response, next: NextFunction) => {
    console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
    next();
  });
}

// API routes
app.use('/api/auth', authRouter);
app.use('/api/users', usersRouter);
app.use('/api/jobs', jobsRouter);
app.use('/api/jobs', eventsRouter);
app.use('/api', healthRouter);

// Error handling middleware
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('Unhandled error:', err);
  res.status(500).json({
    error: 'Internal server error',
    message: CONFIG.isDev ? err.message : undefined,
  });
});

// 404 handler
app.use((_req: Request, res: Response) => {
  res.status(404).json({ error: 'Not found' });
});

// Graceful shutdown
async function shutdown() {
  console.log('Shutting down gracefully...');
  await prisma.$disconnect();
  process.exit(0);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

// Start server
app.listen(CONFIG.port, () => {
  console.log(`NicheIQ API running on port ${CONFIG.port}`);
  console.log(`Environment: ${CONFIG.nodeEnv}`);
  console.log(`Database: ${CONFIG.databaseUrl.replace(/:[^:@]+@/, ':****@')}`);
  console.log(`Redis: ${CONFIG.redisUrl}`);
});
