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

---

## DigitalOcean Deployment (Recommended)

One-command deployment to DigitalOcean with automatic HTTPS via Caddy.

### Infrastructure

- **Droplet**: 4 GB RAM / 2 vCPUs / Ubuntu 24.04 ($24/mo)
- **Database**: PostgreSQL 16 (Docker)
- **Cache/Queue**: Redis 7 (Docker)
- **Reverse Proxy**: Caddy (automatic HTTPS)
- **Domain**: nicheiq.27n.gg
- **Server IP**: 207.154.199.58

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
Host: nicheiq
Value: 207.154.199.58
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
ssh root@207.154.199.58

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
https://nicheiq.27n.gg/api/auth/callback/google
```

**GitHub** (https://github.com/settings/developers):
```
https://nicheiq.27n.gg/api/auth/callback/github
```

### Deploy Script Commands

```bash
./scripts/deploy.sh              # Deploy/update
./scripts/deploy.sh --build      # Rebuild and deploy
./scripts/deploy.sh --logs       # View logs
./scripts/deploy.sh --status     # Container status
./scripts/deploy.sh --down       # Stop services
./scripts/deploy.sh --restart    # Restart services
./scripts/deploy.sh --migrate    # Run migrations only
```

### Verification Checklist

- [ ] DNS A record pointing to Droplet IP
- [ ] Firewall configured (22, 80, 443)
- [ ] Docker installed on server
- [ ] Repository cloned to `/opt/nicheiq`
- [ ] `.env` configured with all API keys
- [ ] `docker compose up -d` succeeds
- [ ] Database migrations complete
- [ ] https://nicheiq.27n.gg loads
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
# Scale to 3 worker instances
docker compose -f docker/docker-compose.yml --profile production up -d --scale worker=3

# Check worker instances
docker compose -f docker/docker-compose.yml ps worker
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
docker stats nicheiq-api nicheiq-worker nicheiq-frontend nicheiq-postgres nicheiq-redis
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
docker exec nicheiq-worker python -c "import redis; r=redis.from_url('redis://redis:6379'); print(r.ping())"

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
