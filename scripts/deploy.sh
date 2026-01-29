#!/bin/bash
# =============================================================================
# NicheIQ Deployment Script
# =============================================================================
# One-command deployment for DigitalOcean
# Usage: ./scripts/deploy.sh [--build] [--scale-workers N] [--down] [--logs] [--migrate]
# =============================================================================

set -e # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_ROOT/.env"

# Docker compose command with env file
DC="docker compose --env-file $ENV_FILE -f $COMPOSE_FILE"

# Change to project root
cd "$PROJECT_ROOT"

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
  echo "NicheIQ Deployment Script"
  echo ""
  echo "Usage: ./scripts/deploy.sh [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  --build              Force rebuild all images"
  echo "  --scale-workers N    Run N worker instances (default: 1)"
  echo "  --down               Stop and remove containers"
  echo "  --logs               Show container logs"
  echo "  --migrate            Run database migrations only"
  echo "  --status             Show container status"
  echo "  --restart            Restart all services"
  echo "  --help               Show this help message"
  echo ""
  echo "Examples:"
  echo "  ./scripts/deploy.sh                          # Deploy/update services"
  echo "  ./scripts/deploy.sh --build                  # Rebuild and deploy"
  echo "  ./scripts/deploy.sh --build --scale-workers 3 # Rebuild with 3 workers"
  echo "  ./scripts/deploy.sh --logs                   # View logs"
  echo "  ./scripts/deploy.sh --down                   # Stop services"
}

check_env() {
  if [ ! -f "$PROJECT_ROOT/.env" ]; then
    log_error ".env file not found!"
    log_info "Create it with: cp .env.production.example .env"
    log_info "Then edit with your API keys: vim .env"
    exit 1
  fi

  # Check for required variables using grep (avoids bash syntax issues in .env)
  local missing_vars=()

  grep -q "^POSTGRES_PASSWORD=.\+" "$PROJECT_ROOT/.env" || missing_vars+=("POSTGRES_PASSWORD")
  grep -q "^AUTH_SECRET=.\+" "$PROJECT_ROOT/.env" || missing_vars+=("AUTH_SECRET")
  grep -q "^OPENAI_API_KEY=.\+" "$PROJECT_ROOT/.env" || missing_vars+=("OPENAI_API_KEY")
  grep -q "^SERPER_API_KEY=.\+" "$PROJECT_ROOT/.env" || missing_vars+=("SERPER_API_KEY")

  if [ ${#missing_vars[@]} -gt 0 ]; then
    log_error "Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
      echo "  - $var"
    done
    exit 1
  fi

  log_success "Environment configuration validated"
}

run_migrations() {
  log_info "Running database migrations..."

  # Wait for postgres to be ready
  $DC exec -T postgres pg_isready -U "${POSTGRES_USER:-nicheiq}" || {
    log_warn "Postgres not ready, waiting..."
    sleep 5
  }

  # Run Prisma migrations
  $DC exec -T api npx prisma migrate deploy

  log_success "Migrations completed"
}

deploy() {
  log_info "Starting deployment..."

  # Pull latest images
  log_info "Pulling base images..."
  $DC pull postgres redis caddy

  # Build and start services
  log_info "Building and starting services..."
  local UP_ARGS="-d"
  [ "$DO_BUILD" = true ] && UP_ARGS="$UP_ARGS --build"
  [ -n "$SCALE_WORKERS" ] && UP_ARGS="$UP_ARGS --scale worker=$SCALE_WORKERS"
  $DC up $UP_ARGS

  # Wait for services to be healthy
  log_info "Waiting for services to be healthy..."
  sleep 10

  # Run migrations
  run_migrations

  # Show status
  $DC ps

  log_success "Deployment complete!"
  echo ""
  log_info "Application should be available at: https://nicheiq.dev"
  log_info "Check logs with: ./scripts/deploy.sh --logs"
}

# =============================================================================
# Main Script
# =============================================================================

# Parse arguments
DO_BUILD=false
SCALE_WORKERS=""
ACTION="deploy"

while [ $# -gt 0 ]; do
  case "$1" in
  --help | -h)
    show_help
    exit 0
    ;;
  --down)
    ACTION="down"
    shift
    ;;
  --logs)
    ACTION="logs"
    shift
    ;;
  --migrate)
    ACTION="migrate"
    shift
    ;;
  --status)
    ACTION="status"
    shift
    ;;
  --restart)
    ACTION="restart"
    shift
    ;;
  --build)
    DO_BUILD=true
    shift
    ;;
  --scale-workers)
    if [ -z "${2:-}" ] || [[ ! "$2" =~ ^[0-9]+$ ]] || [ "$2" -le 0 ]; then
      log_error "--scale-workers requires a positive integer (e.g. --scale-workers 3)"
      exit 1
    fi
    SCALE_WORKERS="$2"
    shift 2
    ;;
  *)
    log_error "Unknown option: $1"
    show_help
    exit 1
    ;;
  esac
done

case "$ACTION" in
  down)
    log_info "Stopping services..."
    $DC down
    log_success "Services stopped"
    ;;
  logs)
    $DC logs -f --tail=100
    ;;
  migrate)
    check_env
    run_migrations
    ;;
  status)
    $DC ps
    echo ""
    log_info "Container health:"
    $DC ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    ;;
  restart)
    log_info "Restarting services..."
    $DC restart
    log_success "Services restarted"
    $DC ps
    ;;
  deploy)
    check_env
    deploy
    ;;
esac
