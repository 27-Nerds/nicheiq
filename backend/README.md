# NicheIQ Backend

Express.js backend API for NicheIQ market research automation.

## Quick Start

```bash
# Install dependencies
npm install

# Set up database
cp .env.example .env  # Configure your database URL
npx prisma migrate dev

# Run development server
npm run dev
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server with hot reload |
| `npm run build` | Build TypeScript to JavaScript |
| `npm start` | Start production server |
| `npm test` | Run tests |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage report |
| `npm run db:migrate` | Run Prisma migrations |
| `npm run db:studio` | Open Prisma Studio |

## API Endpoints

### Authentication

All endpoints require authentication via JWT or internal service token.

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs/:jobId` | Get job details |
| GET | `/api/jobs/:jobId/events` | SSE stream for job progress |
| GET | `/api/jobs/:jobId/report` | Download job report |
| GET | `/api/jobs/:jobId/landing` | Get landing page |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/:userId` | Get user profile |
| GET | `/api/users/:userId/jobs` | Get user's jobs |
| GET | `/api/users/:userId/notification-preferences` | Get notification preferences |
| PUT | `/api/users/:userId/notification-preferences` | Update notification preferences |

### Worker (Internal)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/workers/heartbeat` | Worker heartbeat |
| POST | `/api/workers/job-started` | Report job started |
| POST | `/api/workers/progress` | Report stage progress |
| POST | `/api/workers/job-completed` | Report job finished |
| POST | `/api/workers/shutdown` | Worker graceful shutdown |

## Notification Preferences API

Users can control which email notifications they receive.

### Get Preferences

```bash
GET /api/users/:userId/notification-preferences
Authorization: Bearer <token>
```

Response:
```json
{
  "emailEnabled": true,
  "emailOnJobStart": true,
  "emailOnJobComplete": true,
  "emailOnJobError": true
}
```

### Update Preferences

```bash
PUT /api/users/:userId/notification-preferences
Authorization: Bearer <token>
Content-Type: application/json

{
  "emailEnabled": true,
  "emailOnJobStart": false,
  "emailOnJobComplete": true,
  "emailOnJobError": true
}
```

All fields are optional - only provided fields will be updated.

## Email Templates

Email templates are stored in `src/templates/email/`:

| Template | When Sent |
|----------|-----------|
| `jobStart.html` | When job starts processing |
| `jobComplete.html` | When job completes successfully |
| `jobError.html` | When job fails |

Each template has an HTML version (`.html`) and plain text fallback (`.txt`).

### Template Variables

Templates use `{{VARIABLE}}` syntax for substitution:

- `{{JOB_ID}}` - Job UUID
- `{{NICHE}}` - Research niche (truncated to 100 chars)
- `{{STATUS_URL}}` - Link to job status page
- `{{REPORT_URL}}` - Link to download report (completion only)
- `{{LANDING_URL}}` - Link to landing page (completion only)
- `{{ERROR_MESSAGE}}` - Error details (error only)

## Environment Variables

See [ENV_REFERENCE.md](../ENV_REFERENCE.md) for complete configuration.

### Email Configuration

**SendGrid (Recommended):**
```bash
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.your-api-key
FROM_EMAIL=noreply@yourdomain.com
```

**SMTP:**
```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@yourdomain.com
```

## Testing

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

Test files are located in `__tests__` directories adjacent to the code they test.
