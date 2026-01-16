#!/bin/bash
# =============================================================================
# NicheIQ Deployment Script
# =============================================================================
# One-command deployment for DigitalOcean
# Usage: ./scripts/deploy.sh [--build] [--down] [--logs] [--migrate]
# =============================================================================

set -e  # Exit on error

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
    echo "  --build      Force rebuild all images"
    echo "  --down       Stop and remove containers"
    echo "  --logs       Show container logs"
    echo "  --migrate    Run database migrations only"
    echo "  --status     Show container status"
    echo "  --restart    Restart all services"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/deploy.sh              # Deploy/update services"
    echo "  ./scripts/deploy.sh --build      # Rebuild and deploy"
    echo "  ./scripts/deploy.sh --logs       # View logs"
    echo "  ./scripts/deploy.sh --down       # Stop services"
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

build_frontend() {
    log_info "Building frontend assets..."

    # Build frontend with production API URL
    cd "$PROJECT_ROOT/frontend"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        log_info "Installing frontend dependencies..."
        npm ci
    fi

    # Build with production environment
    PUBLIC_API_URL="${PUBLIC_API_URL:-https://nicheiq.27n.gg}" npm run build

    cd "$PROJECT_ROOT"
    log_success "Frontend built successfully"
}

build_backend() {
    log_info "Building backend..."

    cd "$PROJECT_ROOT/backend"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        log_info "Installing backend dependencies..."
        npm ci
    fi

    # Build TypeScript
    npm run build

    cd "$PROJECT_ROOT"
    log_success "Backend built successfully"
}

run_migrations() {
    log_info "Running database migrations..."

    # Wait for postgres to be ready
    docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-nicheiq}" || {
        log_warn "Postgres not ready, waiting..."
        sleep 5
    }

    # Run Prisma migrations
    docker compose -f "$COMPOSE_FILE" exec -T api npx prisma migrate deploy

    log_success "Migrations completed"
}

deploy() {
    local BUILD_FLAG=""
    if [ "$1" == "--build" ]; then
        BUILD_FLAG="--build"
    fi

    log_info "Starting deployment..."

    # Pull latest images
    log_info "Pulling base images..."
    docker compose -f "$COMPOSE_FILE" pull postgres redis caddy

    # Build and start services
    log_info "Building and starting services..."
    docker compose -f "$COMPOSE_FILE" up -d $BUILD_FLAG

    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10

    # Run migrations
    run_migrations

    # Show status
    docker compose -f "$COMPOSE_FILE" ps

    log_success "Deployment complete!"
    echo ""
    log_info "Application should be available at: https://nicheiq.27n.gg"
    log_info "Check logs with: ./scripts/deploy.sh --logs"
}

# =============================================================================
# Main Script
# =============================================================================

case "${1:-}" in
    --help|-h)
        show_help
        ;;
    --down)
        log_info "Stopping services..."
        docker compose -f "$COMPOSE_FILE" down
        log_success "Services stopped"
        ;;
    --logs)
        docker compose -f "$COMPOSE_FILE" logs -f --tail=100
        ;;
    --migrate)
        check_env
        run_migrations
        ;;
    --status)
        docker compose -f "$COMPOSE_FILE" ps
        echo ""
        log_info "Container health:"
        docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
        ;;
    --restart)
        log_info "Restarting services..."
        docker compose -f "$COMPOSE_FILE" restart
        log_success "Services restarted"
        docker compose -f "$COMPOSE_FILE" ps
        ;;
    --build)
        check_env
        build_backend
        build_frontend
        deploy --build
        ;;
    "")
        check_env
        deploy
        ;;
    *)
        log_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac
