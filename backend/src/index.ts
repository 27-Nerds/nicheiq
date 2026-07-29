import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import { Socket } from 'net';
import { CONFIG, validateConfig } from './config.js';
import { jobsRouter } from './routes/jobs.js';
import { founderFitRouter } from './routes/founderFit.js';
import { selectionChallengesRouter } from './routes/selectionChallenges.js';
import { selectionOwnerEvidenceRouter } from './routes/selectionOwnerEvidence.js';
import { selectionAssumptionsRouter } from './routes/selectionAssumptions.js';
import { selectionExperimentsRouter } from './routes/selectionExperiments.js';
import { selectionDecisionStateRouter } from './routes/selectionDecisionState.js';
import {
  publicSelectionExperimentRunsRouter,
  selectionExperimentRunsRouter,
} from './routes/selectionExperimentRuns.js';
import { selectionExperimentConclusionsRouter } from './routes/selectionExperimentConclusions.js';
import { selectionIdeaNarrowingRouter } from './routes/selectionIdeaNarrowing.js';
import { selectionFounderFitReshapeRouter } from './routes/selectionFounderFitReshape.js';
import { selectionConceptSetsRouter } from './routes/selectionConceptSets.js';
import { selectionFinalDecisionsRouter } from './routes/selectionFinalDecisions.js';
import { selectionDecisionHandoffsRouter } from './routes/selectionDecisionHandoffs.js';
import { githubIntegrationsRouter } from './routes/githubIntegrations.js';
import { selectionHandoffGithubDispatchRouter } from './routes/selectionHandoffGithubDispatch.js';
import { selectionMetricExplanationsRouter } from './routes/selectionMetricExplanations.js';
import { eventsRouter } from './routes/events.js';
import { healthRouter } from './routes/health.js';
import { authRouter } from './routes/auth.js';
import { usersRouter } from './routes/users.js';
import { billingRouter } from './routes/billing.js';
import { workersRouter } from './routes/workers.js';
import { suggestRouter } from './routes/suggest.js';
import { adminRouter } from './routes/admin.js';
import { settingsRouter } from './routes/settings.js';
import { sharesRouter, publicShareRouter } from './routes/shares.js';
import { discoverySharesRouter, publicDiscoveryShareRouter } from './routes/discoveryShares.js';
import { discoveryAnnotationsRouter, publicDiscoveryAnnotationsRouter } from './routes/discoveryAnnotations.js';
import { webhooksRouter } from './routes/webhooks.js';
import { statsRouter } from './routes/stats.js';
import { sitemapRouter } from './routes/sitemap.js';
import { adminCatalogRouter } from './routes/adminCatalog.js';
import { publicCatalogRouter } from './routes/publicCatalog.js';
import { catalogResearchRouter } from './routes/catalogResearch.js';
import { savesRouter } from './routes/saves.js';
import { chatRouter } from './routes/chat.js';
import { requireInternalAdmin, requireInternalService } from './middleware/auth.js';
import { prisma } from './services/db.js';
import { startHeartbeatMonitor, stopHeartbeatMonitor } from './services/heartbeatService.js';
import { startSubscriptionReconciliation, stopSubscriptionReconciliation } from './services/subscriptionService.js';
import { startSelectionReminderMonitor, stopSelectionReminderMonitor } from './services/selectionReminderService.js';
import {
  startDispatchDeliveryMonitor,
  stopDispatchDeliveryMonitor,
} from './services/queueService.js';

// Validate configuration
validateConfig();

const app = express();

// Trust first proxy (for correct req.ip behind reverse proxy)
app.set('trust proxy', 1);

// Middleware
app.use(cors({
  origin: CONFIG.corsOrigins,
  credentials: true,
}));

// Stripe webhook needs raw body - must be before express.json()
app.use('/api/webhooks', express.raw({ type: 'application/json' }), webhooksRouter);

// JSON parsing for all other routes
app.use(express.json({ limit: '1mb' }));

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
app.use('/api/jobs', founderFitRouter);
app.use('/api/jobs', selectionChallengesRouter);
app.use('/api/jobs', selectionOwnerEvidenceRouter);
app.use('/api/jobs', selectionAssumptionsRouter);
app.use('/api/jobs', selectionExperimentsRouter);
app.use('/api/jobs', selectionDecisionStateRouter);
app.use('/api/jobs', selectionExperimentRunsRouter);
app.use('/api/jobs', selectionExperimentConclusionsRouter);
app.use('/api/jobs', selectionIdeaNarrowingRouter);
app.use('/api/jobs', selectionFounderFitReshapeRouter);
app.use('/api/jobs', selectionConceptSetsRouter);
app.use('/api/jobs', selectionFinalDecisionsRouter);
app.use('/api/jobs', selectionDecisionHandoffsRouter);
app.use('/api/integrations/github', githubIntegrationsRouter);
app.use('/api/jobs', selectionHandoffGithubDispatchRouter);
app.use('/api/selection', selectionMetricExplanationsRouter);
app.use('/api/jobs', sharesRouter);
app.use('/api/jobs', eventsRouter);
app.use('/api/jobs', chatRouter);
app.use('/api/shared', publicShareRouter);
app.use('/api/jobs', discoverySharesRouter);
app.use('/api/jobs', discoveryAnnotationsRouter);
app.use('/api/shared/discovery', publicDiscoveryShareRouter);
app.use('/api/shared/discovery', publicDiscoveryAnnotationsRouter);
app.use('/api/public/experiments', requireInternalService, publicSelectionExperimentRunsRouter);
app.use('/api/billing', billingRouter);
app.use('/api/workers', workersRouter);
app.use('/api/suggest', suggestRouter);
app.use('/api/admin', adminRouter);
app.use('/api/settings', settingsRouter);
app.use('/api/stats', statsRouter);
app.use('/api/sitemap', sitemapRouter);
app.use('/api/admin/catalog', requireInternalAdmin, adminCatalogRouter);
// Public-rendering surface: service secret only, no userId required (used by
// SvelteKit (public) SSR loaders that have no session cookie).
app.use('/api/public/catalog', requireInternalService, publicCatalogRouter);
// User-initiated research seeded from catalog items (requireInternalAuth applied per-route).
app.use('/api/catalog', catalogResearchRouter);
// Saved-items surface: per-user bookmarks. requireInternalAuth applied
// inside the router so the no-store cache header runs first.
app.use('/api/saves', savesRouter);
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

// Track active connections for cleanup on shutdown
const activeConnections = new Set<Socket>();

// Start server
const server = app.listen(CONFIG.port, () => {
  console.log(`NicheIQ API running on port ${CONFIG.port}`);
  console.log(`Environment: ${CONFIG.nodeEnv}`);
  console.log(`Database: ${CONFIG.databaseUrl.replace(/:[^:@]+@/, ':****@')}`);
  console.log(`Redis: ${CONFIG.redisUrl}`);

  // Start the heartbeat monitor for worker crash detection
  startHeartbeatMonitor();
  startDispatchDeliveryMonitor();

  // Start the selection reminder monitor for interactive jobs
  startSelectionReminderMonitor();

  // Daily backstop that reconciles lapsed/renewed subscriptions (webhooks are the primary path)
  startSubscriptionReconciliation();
});

// Track connections for graceful shutdown
server.on('connection', (socket: Socket) => {
  activeConnections.add(socket);
  socket.on('close', () => activeConnections.delete(socket));
});

// Graceful shutdown
async function shutdown() {
  console.log('Shutting down gracefully...');

  // Stop the heartbeat monitor
  stopHeartbeatMonitor();
  stopDispatchDeliveryMonitor();
  stopSelectionReminderMonitor();
  stopSubscriptionReconciliation();

  // Stop accepting new connections
  server.close();

  // Destroy all active connections (including SSE)
  console.log(`Closing ${activeConnections.size} active connection(s)...`);
  for (const socket of activeConnections) {
    socket.destroy();
  }

  // Disconnect from database
  await prisma.$disconnect();

  process.exit(0);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
