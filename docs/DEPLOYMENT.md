# Production Deployment Guide

This guide covers deploying NicheIQ to a production server using Docker Compose.

## Table of Contents

- [DigitalOcean Deployment (Recommended)](#digitalocean-deployment-recommended)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Deployment Commands](#deployment-commands)
- [SSL/Reverse Proxy Setup](#sslreverse-proxy-setup)
- [Scaling Workers](#scaling-workers)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Backup & Restore](#backup--restore)
- [Updating & Maintenance](#updating--maintenance)
- [Troubleshooting](#troubleshooting)
- [Admin Operations](#admin-operations)
  - [User Roles & Admin Access](#user-roles--admin-access)
  - [Stripe Configuration](#stripe-configuration)
  - [SendGrid Configuration](#sendgrid-configuration)
  - [Google OAuth Configuration](#google-oauth-configuration)
  - [GitHub OAuth Configuration](#github-oauth-configuration)
  - [OpenAI Configuration](#openai-configuration)
  - [Serper.dev Configuration](#serperdev-configuration)
  - [Reddit API Configuration](#reddit-api-configuration)
  - [DataForSEO Configuration](#dataforseo-configuration)
  - [Token Packages](#token-packages)
  - [Promo Codes](#promo-codes)

---

## DigitalOcean Deployment (Recommended)

One-command deployment to DigitalOcean with automatic HTTPS via Caddy.

### Infrastructure

- **Droplet**: 4 GB RAM / 2 vCPUs / Ubuntu 24.04 ($24/mo)
- **Database**: PostgreSQL 16 (Docker)
- **Cache/Queue**: Redis 7 (Docker)
- **Reverse Proxy**: Caddy (automatic HTTPS)
- **Domain**: yourdomain.com (replace with your domain)
- **Server IP**: YOUR_SERVER_IP (replace with your server IP)

### Files

| File | Purpose |
|------|---------|
| `docker/docker-compose.prod.yml` | Production orchestration with Caddy |
| `docker/Caddyfile` | HTTPS reverse proxy configuration |
| `.env.production.example` | Production environment template |
| `scripts/server-setup.sh` | Server provisioning script |
| `scripts/deploy.sh` | One-command deployment script |

### Step 1: DNS Configuration

Add an A record in your DNS provider:

```
Type: A
Host: @ (or subdomain)
Value: YOUR_SERVER_IP
TTL: 300
```

### Step 2: Firewall Configuration

Via DigitalOcean Dashboard → Networking → Firewalls:

| Type | Port | Source |
|------|------|--------|
| SSH | 22 | Your IP |
| HTTP | 80 | All IPv4/IPv6 |
| HTTPS | 443 | All IPv4/IPv6 |

### Step 3: Server Setup

```bash
ssh root@YOUR_SERVER_IP

# Run setup script
curl -sSL https://raw.githubusercontent.com/YOUR_REPO/nicheiq/main/scripts/server-setup.sh | bash
```

Or clone first:

```bash
git clone https://github.com/YOUR_REPO/nicheiq.git /opt/nicheiq
cd /opt/nicheiq
bash scripts/server-setup.sh
```

### Step 4: Configure Environment

```bash
cd /opt/nicheiq
cp .env.production.example .env
vim .env  # Add your API keys
```

**Required variables:**

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | Strong database password |
| `AUTH_SECRET` | Generate: `openssl rand -base64 32` |
| `OPENAI_API_KEY` | OpenAI API key |
| `SERPER_API_KEY` | Serper.dev API key |
| `REDDIT_CLIENT_ID` | Reddit API credentials |
| `REDDIT_CLIENT_SECRET` | Reddit API credentials |
| `DATAFORSEO_LOGIN` | DataForSEO credentials |
| `DATAFORSEO_PASSWORD` | DataForSEO credentials |

### Step 5: Deploy

```bash
./scripts/deploy.sh --build
```

### Step 6: Update OAuth Callbacks

**Google** (https://console.cloud.google.com/apis/credentials):
```
https://yourdomain.com/api/auth/callback/google
```

**GitHub** (https://github.com/settings/developers):
```
https://yourdomain.com/api/auth/callback/github
```

### Deploy Script Commands

```bash
./scripts/deploy.sh                          # Deploy/update
./scripts/deploy.sh --build                  # Rebuild and deploy
./scripts/deploy.sh --build --scale-workers 3 # Rebuild with 3 workers
./scripts/deploy.sh --logs                   # View logs
./scripts/deploy.sh --status                 # Container status
./scripts/deploy.sh --down                   # Stop services
./scripts/deploy.sh --restart                # Restart services
./scripts/deploy.sh --migrate                # Run migrations only
```

### Verification Checklist

- [ ] DNS A record pointing to Droplet IP
- [ ] Firewall configured (22, 80, 443)
- [ ] Docker installed on server
- [ ] Repository cloned to `/opt/nicheiq`
- [ ] `.env` configured with all API keys
- [ ] `docker compose up -d` succeeds
- [ ] Database migrations complete
- [ ] https://yourdomain.com loads
- [ ] OAuth login works
- [ ] Job creation works

---

## Prerequisites

### System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Storage | 20 GB | 50+ GB (for research outputs) |
| OS | Ubuntu 22.04+ / Debian 12+ | Ubuntu 24.04 LTS |

### Required Software

- **Docker** 24.0+ with Compose v2
- **Git** for cloning the repository

```bash
# Install Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Verify installation
docker --version
docker compose version
```

### Required API Keys

| Service | Purpose | Get Key |
|---------|---------|---------|
| OpenAI | Agent reasoning & embeddings | [platform.openai.com](https://platform.openai.com/api-keys) |
| Serper.dev | Google search | [serper.dev](https://serper.dev/) |
| Reddit | Social data collection | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |
| DataForSEO | Keyword research | [dataforseo.com](https://dataforseo.com/) |
| SendGrid (optional) | Email notifications | [sendgrid.com](https://sendgrid.com/) |

---

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/your-org/nicheiq.git
cd nicheiq

# 2. Create production environment file
cp .env.example .env.production
# Edit .env.production with your API keys and production settings

# 3. Build all images
docker compose -f docker/docker-compose.yml build

# 4. Start infrastructure (PostgreSQL + Redis)
docker compose -f docker/docker-compose.yml up -d postgres redis

# 5. Wait for PostgreSQL to be ready (check health)
docker compose -f docker/docker-compose.yml ps

# 6. Run database migrations
docker compose -f docker/docker-compose.yml run --rm api npx prisma migrate deploy

# 7. Deploy full application stack
docker compose -f docker/docker-compose.yml --profile production up -d

# 8. Verify deployment
docker compose -f docker/docker-compose.yml ps
curl http://localhost:3001/api/health
```

---

## Environment Configuration

Create `.env.production` in the project root with the following variables:

### Required Variables

```bash
# =============================================================================
# DATABASE & QUEUE (Required)
# =============================================================================
DATABASE_URL=postgresql://nicheiq:STRONG_PASSWORD_HERE@postgres:5432/nicheiq
REDIS_URL=redis://redis:6379

# =============================================================================
# API SERVER (Required)
# =============================================================================
PORT=3001
NODE_ENV=production
CORS_ORIGINS=https://yourdomain.com
BASE_URL=https://yourdomain.com

# =============================================================================
# AI SERVICES (Required)
# =============================================================================
OPENAI_API_KEY=sk-...
CHROMA_OPENAI_API_KEY=sk-...  # Same as OPENAI_API_KEY
SERPER_API_KEY=...

# =============================================================================
# REDDIT API (Required)
# =============================================================================
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=NicheIQ/1.0.0

# =============================================================================
# DATAFORSEO (Required for keyword research)
# =============================================================================
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...

# =============================================================================
# FILE STORAGE
# =============================================================================
NICHEIQ_OUTPUT_DIR=/app/output/jobs
JOB_TTL_SECONDS=604800  # 7 days
```

### Optional Variables

```bash
# =============================================================================
# EMAIL NOTIFICATIONS (Optional)
# =============================================================================
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.your-sendgrid-api-key
FROM_EMAIL=noreply@yourdomain.com

# =============================================================================
# MODEL OPTIMIZATION (Optional - defaults shown)
# =============================================================================
OPENAI_MODEL_NAME=gpt-4o
FUNCTION_CALLING_LLM=gpt-4o-mini
BRAINSTORM_LLM=o1

# =============================================================================
# TWITTER (Optional - currently unreliable)
# =============================================================================
ENABLE_TWITTER=false
TWITTER_USERNAME=...
TWITTER_PASSWORD=...
TWITTER_EMAIL=...

# =============================================================================
# TOKEN & COST CONTROL (Optional)
# =============================================================================
TOKEN_MONITORING_ENABLED=true
COST_BUDGET_ENABLED=false
COST_BUDGET_LIMIT=5.00
```

### Security Notes

- Never commit `.env.production` to version control
- Use strong, unique passwords for PostgreSQL
- Consider using Docker secrets or a secrets manager for sensitive values
- Rotate API keys periodically

---

## Deployment Commands

### Build Images

```bash
# Build all images
docker compose -f docker/docker-compose.yml build

# Build specific service
docker compose -f docker/docker-compose.yml build api
docker compose -f docker/docker-compose.yml build worker
docker compose -f docker/docker-compose.yml build frontend

# Build with no cache (force rebuild)
docker compose -f docker/docker-compose.yml build --no-cache
```

### Start Services

```bash
# Start infrastructure only (PostgreSQL + Redis)
docker compose -f docker/docker-compose.yml up -d postgres redis

# Start full production stack
docker compose -f docker/docker-compose.yml --profile production up -d

# Start with environment file
docker compose -f docker/docker-compose.yml --env-file .env.production --profile production up -d
```

### Database Migrations

```bash
# Run pending migrations
docker compose -f docker/docker-compose.yml run --rm api npx prisma migrate deploy

# Check migration status
docker compose -f docker/docker-compose.yml run --rm api npx prisma migrate status

# Generate Prisma client (after schema changes)
docker compose -f docker/docker-compose.yml run --rm api npx prisma generate
```

### Stop Services

```bash
# Stop all services (preserves data)
docker compose -f docker/docker-compose.yml --profile production down

# Stop and remove volumes (DATA LOSS!)
docker compose -f docker/docker-compose.yml --profile production down -v
```

---

## SSL/Reverse Proxy Setup

For production, use Nginx as a reverse proxy with SSL termination.

### Nginx Configuration

Create `/etc/nginx/sites-available/nicheiq`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend (SvelteKit)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # API endpoints
    location /api {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support for progress updates
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }

    # Increase max upload size for large reports
    client_max_body_size 50M;
}
```

### Enable Site and Get SSL Certificate

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/nicheiq /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Install Certbot and get certificate
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com

# Reload Nginx
sudo systemctl reload nginx
```

### Update docker-compose.yml for Production

When using a reverse proxy, update the frontend environment:

```yaml
frontend:
  environment:
    PUBLIC_API_URL: https://yourdomain.com/api
```

---

## Scaling Workers

### Run Multiple Worker Instances

Scale workers horizontally for increased throughput:

```bash
# Using the helper script (recommended)
./scripts/scale-workers.sh 3          # Scale to 3 workers
./scripts/scale-workers.sh 1          # Scale back to 1
./scripts/scale-workers.sh            # Show current worker count

# Or during deployment
./scripts/deploy.sh --build --scale-workers 3

# Or directly with docker compose
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d --no-recreate --scale worker=3

# Check worker instances
docker compose --env-file .env -f docker/docker-compose.prod.yml ps worker
```

### Worker Resource Allocation

Add resource limits in `docker-compose.yml`:

```yaml
worker:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
```

### Considerations

- Each worker processes one job at a time (blocking queue consumer)
- More workers = more parallel job processing
- Monitor API rate limits (OpenAI, DataForSEO) when scaling
- Each worker requires ~2GB RAM for large research jobs

---

## Monitoring & Health Checks

### Health Check Endpoints

```bash
# API health check
curl http://localhost:3001/api/health

# PostgreSQL health
docker exec nicheiq-postgres pg_isready -U nicheiq

# Redis health
docker exec nicheiq-redis redis-cli ping
```

### View Logs

```bash
# All services
docker compose -f docker/docker-compose.yml --profile production logs -f

# Specific service
docker compose -f docker/docker-compose.yml logs -f api
docker compose -f docker/docker-compose.yml logs -f worker
docker compose -f docker/docker-compose.yml logs -f frontend

# Last 100 lines
docker compose -f docker/docker-compose.yml logs --tail=100 worker
```

### Container Status

```bash
# All containers
docker compose -f docker/docker-compose.yml --profile production ps

# Resource usage
docker stats nicheiq-api nicheiq-frontend nicheiq-postgres nicheiq-redis
# Or use compose to include all worker instances:
docker compose -f docker/docker-compose.prod.yml ps -q | xargs docker stats
```

### Queue Monitoring

```bash
# Check queue length
docker exec nicheiq-redis redis-cli LLEN nicheiq:jobs

# View pending jobs
docker exec nicheiq-redis redis-cli LRANGE nicheiq:jobs 0 -1
```

---

## Backup & Restore

### PostgreSQL Backup

```bash
# Create backup
docker exec nicheiq-postgres pg_dump -U nicheiq nicheiq > backup_$(date +%Y%m%d_%H%M%S).sql

# Create compressed backup
docker exec nicheiq-postgres pg_dump -U nicheiq nicheiq | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Automated daily backup (add to crontab)
0 2 * * * docker exec nicheiq-postgres pg_dump -U nicheiq nicheiq | gzip > /backups/nicheiq_$(date +\%Y\%m\%d).sql.gz
```

### PostgreSQL Restore

```bash
# Stop application services first
docker compose -f docker/docker-compose.yml --profile production stop api worker frontend

# Restore from backup
cat backup.sql | docker exec -i nicheiq-postgres psql -U nicheiq nicheiq

# Or from compressed backup
gunzip -c backup.sql.gz | docker exec -i nicheiq-postgres psql -U nicheiq nicheiq

# Restart services
docker compose -f docker/docker-compose.yml --profile production up -d
```

### Redis Backup

Redis uses RDB persistence by default. The data volume is at `redis_data`.

```bash
# Trigger manual save
docker exec nicheiq-redis redis-cli BGSAVE

# Copy RDB file
docker cp nicheiq-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### Output Files Backup

Research reports and landing pages are stored in `./output/`:

```bash
# Backup output directory
tar -czvf output_backup_$(date +%Y%m%d).tar.gz ./output/

# Restore
tar -xzvf output_backup_20240101.tar.gz
```

---

## Updating & Maintenance

### Zero-Downtime Update Procedure

```bash
# 1. Pull latest code
git pull origin main

# 2. Build new images
docker compose -f docker/docker-compose.yml build

# 3. Run database migrations (if any)
docker compose -f docker/docker-compose.yml run --rm api npx prisma migrate deploy

# 4. Restart services one by one
docker compose -f docker/docker-compose.yml --profile production up -d --no-deps api
docker compose -f docker/docker-compose.yml --profile production up -d --no-deps worker
docker compose -f docker/docker-compose.yml --profile production up -d --no-deps frontend

# 5. Verify health
curl http://localhost:3001/api/health
```

### Rollback Procedure

```bash
# 1. Stop current services
docker compose -f docker/docker-compose.yml --profile production down

# 2. Checkout previous version
git checkout <previous-commit-hash>

# 3. Rebuild and redeploy
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml --profile production up -d
```

### Cleanup Old Images

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (careful - may delete data!)
docker volume prune

# Full cleanup
docker system prune -a
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
docker compose -f docker/docker-compose.yml logs api
docker compose -f docker/docker-compose.yml logs worker

# Check container exit codes
docker ps -a | grep nicheiq

# Inspect container
docker inspect nicheiq-api
```

### Database Connection Issues

```bash
# Verify PostgreSQL is running
docker compose -f docker/docker-compose.yml ps postgres

# Test connection from host
docker exec nicheiq-postgres psql -U nicheiq -c "SELECT 1"

# Check DATABASE_URL format
# Correct: postgresql://nicheiq:password@postgres:5432/nicheiq
# Note: Use 'postgres' (service name) not 'localhost' inside Docker
```

### Redis Connection Issues

```bash
# Verify Redis is running
docker compose -f docker/docker-compose.yml ps redis

# Test connection
docker exec nicheiq-redis redis-cli ping

# Check queue
docker exec nicheiq-redis redis-cli LLEN nicheiq:jobs
```

### Worker Not Processing Jobs

```bash
# Check worker logs
docker compose -f docker/docker-compose.yml logs -f worker

# Verify worker is connected to Redis
docker compose -f docker/docker-compose.prod.yml exec worker python -c "import redis; r=redis.from_url('redis://redis:6379'); print(r.ping())"

# Check for stuck jobs
docker exec nicheiq-redis redis-cli LRANGE nicheiq:jobs 0 -1
```

### API Key Issues

```bash
# Verify environment variables are set
docker compose -f docker/docker-compose.yml run --rm worker env | grep OPENAI
docker compose -f docker/docker-compose.yml run --rm worker env | grep SERPER

# Test OpenAI connection
docker compose -f docker/docker-compose.yml run --rm worker python -c "
from openai import OpenAI
client = OpenAI()
print(client.models.list().data[0])
"
```

### Out of Memory

```bash
# Check container memory usage
docker stats --no-stream

# Increase worker memory limit in docker-compose.yml
# Or reduce parallel workers
docker compose -f docker/docker-compose.yml --profile production up -d --scale worker=1
```

### Port Conflicts

```bash
# Check what's using ports
sudo lsof -i :3000
sudo lsof -i :3001
sudo lsof -i :5432
sudo lsof -i :6379

# Use alternative ports (edit docker-compose.yml or use environment variables)
DOCKER_PG_PORT=5435 DOCKER_REDIS_PORT=6380 docker compose up -d
```

### Viewing Job Progress

```bash
# Subscribe to job progress channel
docker exec nicheiq-redis redis-cli SUBSCRIBE "job:*:progress"

# Check job status in database
docker exec nicheiq-postgres psql -U nicheiq -c "SELECT id, status, current_stage, progress_percent FROM \"Job\" ORDER BY created_at DESC LIMIT 5"
```

---

## Admin Operations

### User Roles & Admin Access

NicheIQ has two user roles: `USER` (default) and `ADMIN`. Admin users can access the admin panel at `/admin` to manage dashboard stats, reports, promo codes, users, and token packages.

#### Promote a User to Admin

**Development (local):**

```bash
cd backend
npx tsx prisma/seed-admin.ts user@example.com
```

**Production (Docker):**

```bash
# Option 1: Run the seed script inside the API container
docker compose --env-file .env -f docker/docker-compose.prod.yml exec api npx tsx prisma/seed-admin.ts user@example.com

# Option 2: Direct SQL via PostgreSQL container
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq -c \
  "UPDATE \"User\" SET role = 'ADMIN' WHERE email = 'user@example.com';"
```

**Verify:**

```bash
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq -c \
  "SELECT email, name, role FROM \"User\" WHERE role = 'ADMIN';"
```

#### Demote an Admin back to User

```bash
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq -c \
  "UPDATE \"User\" SET role = 'USER' WHERE email = 'user@example.com';"
```

**Note:** Role changes take effect after the user logs out and back in (the role is stored in the JWT).

---

### Stripe Configuration

Stripe handles payment processing for token packages. You must configure Stripe before users can purchase credits.

#### Step 1: Create Stripe Account

1. Sign up at https://stripe.com
2. Complete business verification (required for live payments)

#### Step 2: Get API Keys

1. Go to https://dashboard.stripe.com/apikeys
2. Copy your **Secret key** (starts with `sk_test_` or `sk_live_`)
3. Add to your `.env`:

```bash
# Development (test mode - no real charges)
STRIPE_SECRET_KEY=sk_test_...

# Production (live mode - real charges)
STRIPE_SECRET_KEY=sk_live_...
```

#### Step 3: Create Products and Prices

In Stripe Dashboard → Products → Add Product:

| Product Name | Price | Price ID |
|--------------|-------|----------|
| Starter Pack | $9.99 | `price_xxx` |
| Pro Pack | $24.99 | `price_yyy` |
| Enterprise Pack | $69.99 | `price_zzz` |

**Important:** Copy the Price ID (starts with `price_`) for each product. You'll need these when adding token packages to the database.

#### Step 4: Configure Webhook

Webhooks notify your app when payments complete.

1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Enter your endpoint URL:
   - **Production:** `https://yourdomain.com/api/webhooks/stripe`
   - **Development:** Use [Stripe CLI](https://stripe.com/docs/stripe-cli) for local testing
4. Select events to listen for:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
5. Click "Add endpoint"
6. Copy the **Signing secret** (starts with `whsec_`)
7. Add to your `.env`:

```bash
STRIPE_WEBHOOK_SECRET=whsec_...
```

#### Local Development with Stripe CLI

For testing webhooks locally:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe  # macOS
# Or download from https://stripe.com/docs/stripe-cli

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:3001/api/webhooks/stripe

# Copy the webhook signing secret shown and add to .env
```

#### Verify Stripe Configuration

```bash
# Check if Stripe keys are set (production)
docker exec -it nicheiq-api printenv | grep STRIPE

# Test webhook endpoint
curl -X POST https://yourdomain.com/api/webhooks/stripe \
  -H "Content-Type: application/json" \
  -d '{"type": "test"}'
# Should return 400 (invalid signature) - confirms endpoint is reachable
```

---

### SendGrid Configuration

SendGrid handles email notifications for job status updates.

#### Step 1: Create SendGrid Account

1. Sign up at https://sendgrid.com (free tier: 100 emails/day)
2. Complete sender verification

#### Step 2: Create API Key

1. Go to Settings → API Keys → Create API Key
2. Name it (e.g., "NicheIQ Production")
3. Select permissions:
   - **Full Access** (easiest), or
   - **Restricted Access** with "Mail Send" enabled
4. Click "Create & View"
5. **Copy the key immediately** (shown only once!)

#### Step 3: Verify Sender Identity

SendGrid requires sender verification to prevent spam.

**Option A: Single Sender Verification (Quick)**

1. Go to Settings → Sender Authentication → Single Sender Verification
2. Add your sender email (e.g., `noreply@yourdomain.com`)
3. Check your inbox and click the verification link

**Option B: Domain Authentication (Recommended for Production)**

1. Go to Settings → Sender Authentication → Domain Authentication
2. Add your domain (e.g., `yourdomain.com`)
3. Add the DNS records SendGrid provides (CNAME records)
4. Click "Verify" once DNS propagates

#### Step 4: Configure Environment

```bash
# Add to .env
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.your-api-key-here
FROM_EMAIL=noreply@yourdomain.com
```

#### Verify SendGrid Configuration

```bash
# Check if SendGrid is configured (production)
docker exec -it nicheiq-api printenv | grep -E "SENDGRID|EMAIL"

# Test email sending (via API or trigger a test job)
curl -X POST https://yourdomain.com/api/test-email \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to": "test@example.com"}'
```

#### SendGrid Dashboard

Monitor email delivery at:
- **Activity Feed:** https://app.sendgrid.com/email_activity
- **Statistics:** https://app.sendgrid.com/statistics

---

### Google OAuth Configuration

Google OAuth enables users to sign in with their Google accounts. This is required for the "Sign in with Google" functionality.

#### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click "Select a project" → "New Project"
3. Name it (e.g., "NicheIQ Production")
4. Click "Create"

#### Step 2: Configure OAuth Consent Screen

1. Go to APIs & Services → OAuth consent screen
2. Select **External** user type (unless you have Google Workspace)
3. Fill in the app information:
   - **App name**: NicheIQ
   - **User support email**: Your email
   - **App logo**: Optional
   - **App domain**: `https://yourdomain.com`
   - **Authorized domains**: `yourdomain.com`
   - **Developer contact email**: Your email
4. Click "Save and Continue"
5. **Scopes**: Click "Add or Remove Scopes"
   - Select: `email`, `profile`, `openid`
   - Click "Update" → "Save and Continue"
6. **Test users** (required for testing before publishing):
   - Add email addresses of users who can test
   - Click "Save and Continue"
7. Review and click "Back to Dashboard"

#### Step 3: Create OAuth 2.0 Credentials

1. Go to APIs & Services → Credentials
2. Click "Create Credentials" → "OAuth client ID"
3. Select **Web application**
4. Name it (e.g., "NicheIQ Web Client")
5. Add **Authorized JavaScript origins**:
   - `https://yourdomain.com`
   - `http://localhost:3000` (for development)
6. Add **Authorized redirect URIs**:
   - `https://yourdomain.com/api/auth/callback/google`
   - `http://localhost:3000/api/auth/callback/google` (for development)
7. Click "Create"
8. **Copy the Client ID and Client Secret** immediately

#### Step 4: Configure Environment

```bash
# Add to .env
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-client-secret>
```

#### Step 5: Publish App (For Production)

While in "Testing" mode, only users added as test users can sign in.

To allow any Google user to sign in:
1. Go to OAuth consent screen
2. Click "Publish App"
3. Confirm the verification requirements
4. For apps requesting only basic scopes (email, profile), verification is usually not required

**Note**: Published apps with >100 users may require Google verification.

#### Verify Google OAuth Configuration

```bash
# Check if Google OAuth is configured (production)
docker exec -it nicheiq-api printenv | grep GOOGLE

# Test OAuth flow
# Navigate to https://yourdomain.com and click "Sign in with Google"
```

#### Google Cloud Console Links

- **Credentials**: https://console.cloud.google.com/apis/credentials
- **OAuth consent screen**: https://console.cloud.google.com/apis/credentials/consent

---

### GitHub OAuth Configuration

GitHub OAuth enables users to sign in with their GitHub accounts. This is useful for developer-focused applications.

#### Step 1: Create GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "OAuth Apps" in the left sidebar
3. Click "New OAuth App"
4. Fill in the application details:
   - **Application name**: NicheIQ
   - **Homepage URL**: `https://yourdomain.com`
   - **Application description**: (optional) "AI-powered market research platform"
   - **Authorization callback URL**: `https://yourdomain.com/api/auth/callback/github`
5. Click "Register application"

#### Step 2: Get Client Credentials

After registration:
1. You'll see your **Client ID** on the app page
2. Click "Generate a new client secret"
3. **Copy the Client Secret immediately** (you won't see it again!)

#### Step 3: Configure Environment

```bash
# Add to .env
GITHUB_CLIENT_ID=Iv1.a1b2c3d4e5f6g7h8
GITHUB_CLIENT_SECRET=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
```

#### Development Setup

For local development, create a separate OAuth app with:
- **Homepage URL**: `http://localhost:3000`
- **Authorization callback URL**: `http://localhost:3000/api/auth/callback/github`

Or add `http://localhost:3000/api/auth/callback/github` as an additional callback URL to your existing app (GitHub allows multiple callback URLs).

#### Verify GitHub OAuth Configuration

```bash
# Check if GitHub OAuth is configured (production)
docker exec -it nicheiq-api printenv | grep GITHUB

# Test OAuth flow
# Navigate to https://yourdomain.com and click "Sign in with GitHub"
```

#### GitHub Developer Links

- **OAuth Apps**: https://github.com/settings/developers
- **Documentation**: https://docs.github.com/en/apps/oauth-apps

---

### OpenAI Configuration

OpenAI powers the AI agents that analyze content and generate research insights.

#### Step 1: Create OpenAI Account

1. Go to [OpenAI Platform](https://platform.openai.com)
2. Click "Sign up" or "Log in"
3. Verify your email address

#### Step 2: Add Payment Method

1. Click your profile icon (top right) → "Billing"
2. Click "Add payment method"
3. Add a credit/debit card
4. **Recommended**: Set usage limits to control costs
   - Go to Billing → Limits
   - Set a monthly budget (e.g., $50/month)
   - Enable email alerts when approaching limit

#### Step 3: Create API Key

1. Go to [API Keys](https://platform.openai.com/api-keys)
2. Click "+ Create new secret key"
3. Name it: "NicheIQ Production"
4. **Copy the key immediately** (you won't see it again!)
5. The key starts with `sk-proj-` or `sk-`

#### Step 4: Configure Environment

```bash
# Add to .env
OPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
OPENAI_MODEL_NAME=gpt-4o

# Optional: Use same key for embeddings
CHROMA_OPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

#### Model Options

| Model | Cost | Use Case |
|-------|------|----------|
| `gpt-4o` | ~$0.005/1K input, ~$0.015/1K output | Recommended - best quality |
| `gpt-4o-mini` | ~$0.00015/1K input, ~$0.0006/1K output | Budget option - 75% cheaper |
| `o1` | ~$0.015/1K input, ~$0.06/1K output | Advanced reasoning tasks |

**Typical Cost**: ~$0.50-$2.00 per research run with GPT-4o.

#### Verify OpenAI Configuration

```bash
# Check if OpenAI is configured (production)
docker exec -it nicheiq-api printenv | grep OPENAI

# Test API connection (production)
docker compose -f docker/docker-compose.prod.yml exec worker python -c "
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[{'role': 'user', 'content': 'Say hello'}],
    max_tokens=10
)
print('✓ OpenAI connected:', response.choices[0].message.content)
"
```

#### OpenAI Dashboard Links

- **API Keys**: https://platform.openai.com/api-keys
- **Usage**: https://platform.openai.com/usage
- **Billing**: https://platform.openai.com/account/billing

---

### Serper.dev Configuration

Serper.dev enables Google Search to discover Reddit and Twitter discussions for research.

#### Step 1: Create Serper.dev Account

1. Go to [Serper.dev](https://serper.dev)
2. Click "Get Started Free" or "Sign Up"
3. Sign up with Google (easiest) or email
4. No credit card required for free tier!

#### Step 2: Get API Key

1. After signup, you'll see your dashboard
2. Your API key is displayed prominently
3. Copy it (looks like: `a1b2c3d4e5f6g7h8i9j0...`)

#### Free Tier & Pricing

| Tier | Searches | Cost |
|------|----------|------|
| Free | 2,500 searches | $0 |
| Pro | Unlimited | $50/month |

**Typical usage**: ~10-20 searches per research run (2,500 free = ~100+ research runs).

#### Step 3: Configure Environment

```bash
# Add to .env
SERPER_API_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
```

#### Verify Serper.dev Configuration

```bash
# Check if Serper is configured (production)
docker exec -it nicheiq-api printenv | grep SERPER

# Test API connection (production)
docker compose -f docker/docker-compose.prod.yml exec worker python -c "
import os
import requests
response = requests.post(
    'https://google.serper.dev/search',
    headers={'X-API-KEY': os.environ['SERPER_API_KEY']},
    json={'q': 'test'}
)
print('✓ Serper connected:', response.status_code == 200)
print('  Credits remaining:', response.headers.get('X-Credits-Remaining', 'N/A'))
"
```

#### Serper.dev Dashboard

- **Dashboard & Usage**: https://serper.dev/dashboard

---

### Reddit API Configuration

Reddit API collects posts and comments for pain point analysis.

#### Step 1: Create Reddit Account

1. Go to [Reddit](https://www.reddit.com)
2. Create an account if you don't have one
3. Verify your email (required for API access)

#### Step 2: Create Reddit App

1. Go to [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Scroll to bottom and click "create another app..." or "are you a developer? create an app..."
3. Fill in the form:
   - **Name**: "NicheIQ Research Tool"
   - **App type**: Select **"script"** (important!)
   - **Description**: "Market research automation tool"
   - **About URL**: Leave blank or `http://localhost`
   - **Redirect URI**: `http://localhost:8080` (required, but not used for script apps)
4. Click "Create app"

#### Step 3: Get Credentials

After creation, you'll see your app listed:

```
NicheIQ Research Tool
  personal use script
  ↳ AbCdEf12GhIjKl    ← This is your Client ID (under the app name)
  secret: aBcDeFgHiJkLmNoPqRsTuVwXyZ123456    ← This is your Client Secret
```

#### Step 4: Configure Environment

```bash
# Add to .env
REDDIT_CLIENT_ID=AbCdEf12GhIjKl
REDDIT_CLIENT_SECRET=aBcDeFgHiJkLmNoPqRsTuVwXyZ123456
REDDIT_USER_AGENT=NicheIQ/1.0.0 (by /u/yourusername)
```

**Note**: The user agent should be descriptive and unique. Reddit may block generic user agents.

#### Rate Limits

- **60 requests per minute** (sufficient for NicheIQ)
- OAuth apps have higher limits than guest access
- NicheIQ respects rate limits automatically

#### Verify Reddit API Configuration

```bash
# Check if Reddit is configured (production)
docker exec -it nicheiq-api printenv | grep REDDIT

# Test API connection (production)
docker compose -f docker/docker-compose.prod.yml exec worker python -c "
import praw
import os
reddit = praw.Reddit(
    client_id=os.environ['REDDIT_CLIENT_ID'],
    client_secret=os.environ['REDDIT_CLIENT_SECRET'],
    user_agent=os.environ.get('REDDIT_USER_AGENT', 'NicheIQ/1.0.0')
)
print('✓ Reddit connected')
print('  Read-only mode:', reddit.read_only)
"
```

#### Reddit Developer Links

- **App Preferences**: https://www.reddit.com/prefs/apps
- **API Documentation**: https://www.reddit.com/dev/api

---

### DataForSEO Configuration

DataForSEO provides keyword search volume data and market validation.

#### Step 1: Create DataForSEO Account

1. Go to [DataForSEO](https://dataforseo.com)
2. Click "Sign Up" (top right)
3. Fill in:
   - Email address
   - Password
   - Company name (can be personal name)
   - Country
4. Click "Create Account"
5. Verify your email

#### Step 2: Add Payment Method

**Important**: A payment method is required to receive the $1 free credit.

1. After login, go to [Billing](https://app.dataforseo.com/billing)
2. Click "Add funds"
3. Add a payment method (credit/debit card)
4. You'll receive **$1 free credit** after verification
5. Optionally, add $5-10 to start (goes a long way)

#### Step 3: Get API Credentials

1. Go to [API Access](https://app.dataforseo.com/api-access)
2. Your credentials are displayed:
   - **Login**: Usually your email address
   - **Password**: A generated API password (NOT your account password)
3. If you don't see a password, click "Generate new password"
4. **Copy both the login and password**

#### Step 4: Configure Environment

```bash
# Add to .env
DATAFORSEO_LOGIN=your.email@example.com
DATAFORSEO_PASSWORD=aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0
```

**Important**: Use the API password, not your account password!

#### Pricing

| Endpoint | Cost per Request |
|----------|------------------|
| Keywords Data (Google) | $0.005 |
| SERP Overview | $0.003 |
| Keyword Suggestions | $0.005 |

**Typical usage**: ~$0.01-$0.10 per research run. NicheIQ batches keywords to minimize costs (1,000 keywords = 1 request).

#### Location & Language Codes

Common location codes for keyword research:

| Country | Code |
|---------|------|
| United States | 2840 |
| United Kingdom | 2826 |
| Canada | 2124 |
| Australia | 2036 |
| Germany | 2276 |

Configure in `.env`:
```bash
TARGET_LOCATION=2840  # United States
TARGET_LANGUAGE=en
```

#### Verify DataForSEO Configuration

```bash
# Check if DataForSEO is configured (production)
docker exec -it nicheiq-api printenv | grep DATAFORSEO

# Test API connection (production)
docker compose -f docker/docker-compose.prod.yml exec worker python -c "
import os
import requests
from requests.auth import HTTPBasicAuth
response = requests.get(
    'https://api.dataforseo.com/v3/keywords_data/google_ads/status',
    auth=HTTPBasicAuth(
        os.environ['DATAFORSEO_LOGIN'],
        os.environ['DATAFORSEO_PASSWORD']
    )
)
data = response.json()
if data.get('status_code') == 20000:
    print('✓ DataForSEO connected')
else:
    print('✗ DataForSEO error:', data.get('status_message'))
"
```

#### DataForSEO Dashboard Links

- **Dashboard**: https://app.dataforseo.com
- **API Access**: https://app.dataforseo.com/api-access
- **Billing**: https://app.dataforseo.com/billing
- **API Documentation**: https://docs.dataforseo.com

---

### Token Packages

Token packages define the credit bundles users can purchase via Stripe.

#### Development (Local Database)

```bash
# Connect to local PostgreSQL
psql postgresql://nicheiq:nicheiq@localhost:5435/nicheiq

# Or use Prisma Studio
cd backend && npm run db:studio
```

#### Production (Docker)

```bash
# Connect to the PostgreSQL container
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq
```

#### Add Token Packages

```sql
INSERT INTO "TokenPackage" (id, name, description, credits, "priceInCents", "stripePriceId", "isActive", "isPopular", "sortOrder")
VALUES
  (gen_random_uuid(), 'Starter', '5 research credits', 5, 999, 'price_xxx', true, false, 1),
  (gen_random_uuid(), 'Pro', '15 research credits', 15, 2499, 'price_yyy', true, true, 2),
  (gen_random_uuid(), 'Enterprise', '50 research credits', 50, 6999, 'price_zzz', true, false, 3);
```

**Important:** Replace `price_xxx`, `price_yyy`, `price_zzz` with actual Stripe Price IDs from your Stripe Dashboard.

#### Token Package Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Auto-generated with `gen_random_uuid()` |
| `name` | String | Display name (e.g., "Starter", "Pro") |
| `description` | String | Package description shown to users |
| `credits` | Int | Number of research credits |
| `priceInCents` | Int | Price in cents (999 = $9.99) |
| `stripePriceId` | String | Stripe Price ID (must exist in Stripe) |
| `isActive` | Boolean | Whether package is available for purchase |
| `isPopular` | Boolean | Highlights package as "Most Popular" |
| `sortOrder` | Int | Display order (lower = first) |

#### Manage Token Packages

```sql
-- List all packages
SELECT name, credits, "priceInCents", "isActive", "isPopular", "sortOrder"
FROM "TokenPackage" ORDER BY "sortOrder";

-- Deactivate a package (soft delete)
UPDATE "TokenPackage" SET "isActive" = false WHERE name = 'Starter';

-- Update price (remember to update Stripe Price ID too)
UPDATE "TokenPackage"
SET "priceInCents" = 1999, "stripePriceId" = 'price_new_xxx'
WHERE name = 'Starter';

-- Delete a package (only if never purchased)
DELETE FROM "TokenPackage" WHERE name = 'OldPackage';
```

---

### Promo Codes

Promo codes grant free credits to users.

#### Development (Local Database)

```bash
psql postgresql://nicheiq:nicheiq@localhost:5435/nicheiq
```

#### Production (Docker)

```bash
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq
```

#### Create Promo Codes

```sql
-- Single-use promo code (1 user, no expiration)
INSERT INTO "PromoCode" (id, code, "creditAmount", "maxRedemptions", description, "createdBy")
VALUES (gen_random_uuid(), 'WELCOME10', 10, 1, 'Welcome bonus - 10 credits', 'admin');

-- Multi-use promo code (100 users)
INSERT INTO "PromoCode" (id, code, "creditAmount", "maxRedemptions", description, "createdBy")
VALUES (gen_random_uuid(), 'LAUNCH2024', 5, 100, 'Launch promotion - 5 credits', 'admin');

-- Time-limited promo code (expires in 30 days)
INSERT INTO "PromoCode" (id, code, "creditAmount", "maxRedemptions", "expiresAt", description, "createdBy")
VALUES (gen_random_uuid(), 'SUMMER50', 50, 500, NOW() + INTERVAL '30 days', 'Summer sale - 50 credits', 'admin');

-- Unlimited use promo code
INSERT INTO "PromoCode" (id, code, "creditAmount", "maxRedemptions", description, "createdBy")
VALUES (gen_random_uuid(), 'BETA', 3, 999999, 'Beta tester reward', 'admin');
```

#### Promo Code Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Auto-generated with `gen_random_uuid()` |
| `code` | String | Unique code users enter (case-sensitive) |
| `creditAmount` | Int | Credits granted when redeemed |
| `maxRedemptions` | Int | Maximum total uses (default: 1) |
| `currentUses` | Int | Current redemption count (auto-updated) |
| `expiresAt` | DateTime | Optional expiration date |
| `isActive` | Boolean | Whether code can be redeemed |
| `description` | String | Admin notes (not shown to users) |
| `createdBy` | String | Admin who created the code |

#### Manage Promo Codes

```sql
-- List all active promo codes with usage stats
SELECT code, "creditAmount", "currentUses", "maxRedemptions", "expiresAt", "isActive"
FROM "PromoCode"
WHERE "isActive" = true
ORDER BY "createdAt" DESC;

-- Check redemption history for a code
SELECT pc.code, u.email, pr."creditsGranted", pr."redeemedAt"
FROM "PromoRedemption" pr
JOIN "PromoCode" pc ON pr."promoCodeId" = pc.id
JOIN "User" u ON pr."userId" = u.id
WHERE pc.code = 'WELCOME10'
ORDER BY pr."redeemedAt" DESC;

-- Deactivate a promo code
UPDATE "PromoCode" SET "isActive" = false WHERE code = 'OLDCODE';

-- Extend expiration
UPDATE "PromoCode" SET "expiresAt" = NOW() + INTERVAL '60 days' WHERE code = 'SUMMER50';

-- Increase max redemptions
UPDATE "PromoCode" SET "maxRedemptions" = 200 WHERE code = 'LAUNCH2024';
```

#### Quick Reference: Production One-Liners

```bash
# Add a promo code in production
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq -c "INSERT INTO \"PromoCode\" (id, code, \"creditAmount\", \"maxRedemptions\", description) VALUES (gen_random_uuid(), 'NEWCODE', 10, 100, 'New promo');"

# List active promo codes
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq -c "SELECT code, \"creditAmount\", \"currentUses\"/\"maxRedemptions\" as usage FROM \"PromoCode\" WHERE \"isActive\" = true;"

# Add a token package
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq -c "INSERT INTO \"TokenPackage\" (id, name, description, credits, \"priceInCents\", \"stripePriceId\", \"isActive\", \"sortOrder\") VALUES (gen_random_uuid(), 'Basic', '3 credits', 3, 499, 'price_abc123', true, 0);"

# List token packages
docker exec -it nicheiq-postgres psql -U nicheiq nicheiq -c "SELECT name, credits, \"priceInCents\"/100.0 as price_usd, \"isActive\" FROM \"TokenPackage\" ORDER BY \"sortOrder\";"
```

---

## Architecture Reference

```
                    ┌─────────────────────────────────────┐
                    │           Nginx (SSL)               │
                    │         yourdomain.com              │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────┴─────────────────────┐
                    │                                     │
              ┌─────▼─────┐                        ┌──────▼──────┐
              │  Frontend │                        │     API     │
              │  :3000    │                        │    :3001    │
              │ (Svelte)  │                        │  (Node.js)  │
              └───────────┘                        └──────┬──────┘
                                                          │
                                          ┌───────────────┼───────────────┐
                                          │               │               │
                                   ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
                                   │  PostgreSQL │ │    Redis    │ │   Worker    │
                                   │    :5432    │ │    :6379    │ │  (Python)   │
                                   └─────────────┘ └─────────────┘ └─────────────┘
                                          │               │               │
                                          │               │               │
                                   ┌──────▼───────────────▼───────────────▼──────┐
                                   │                 Volumes                      │
                                   │  postgres_data | redis_data | ./output      │
                                   └──────────────────────────────────────────────┘
```

### Service Communication

| From | To | Protocol | Purpose |
|------|----|----------|---------|
| Frontend | API | HTTP | Job submission, status polling |
| API | PostgreSQL | TCP | Job persistence |
| API | Redis | TCP | Job queue, pub/sub |
| Worker | PostgreSQL | TCP | Job updates |
| Worker | Redis | TCP | Job consumption, progress publishing |
| Worker | OpenAI/APIs | HTTPS | AI processing |

---

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/nicheiq/issues)
- **Documentation**: See `docs/` directory
- **Logs**: Check container logs with `docker compose logs`
