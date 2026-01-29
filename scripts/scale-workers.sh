#!/bin/bash
# =============================================================================
# NicheIQ Worker Scaling Script
# =============================================================================
# Scale worker instances up or down without disrupting running jobs.
#
# Usage:
#   ./scripts/scale-workers.sh 3         # Scale to 3 workers
#   ./scripts/scale-workers.sh 1         # Scale back to 1
#   ./scripts/scale-workers.sh           # Show current worker count
#   ./scripts/scale-workers.sh --status  # Show current worker count
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Soft limit based on 4 GB droplet (~2 GB per worker)
MAX_WORKERS=4

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_ROOT/.env"

DC="docker compose --env-file $ENV_FILE -f $COMPOSE_FILE"

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

show_status() {
  local count
  count=$($DC ps --format '{{.Name}}' worker 2>/dev/null | wc -l)
  echo ""
  log_info "Current worker instances: $count"
  echo ""
  $DC ps worker
  echo ""
}

show_help() {
  echo "NicheIQ Worker Scaling"
  echo ""
  echo "Usage: ./scripts/scale-workers.sh [COUNT | --status | --help]"
  echo ""
  echo "Arguments:"
  echo "  COUNT      Number of worker instances (1-$MAX_WORKERS recommended)"
  echo "  --status   Show current worker count (default when no args)"
  echo "  --help     Show this help message"
  echo ""
  echo "Examples:"
  echo "  ./scripts/scale-workers.sh 3         # Scale to 3 workers"
  echo "  ./scripts/scale-workers.sh 1         # Scale back to 1"
  echo "  ./scripts/scale-workers.sh           # Show current count"
}

# --- Main ---

case "${1:-}" in
  --help|-h)
    show_help
    exit 0
    ;;
  --status|"")
    show_status
    exit 0
    ;;
esac

COUNT="$1"

# Validate: must be a positive integer
if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [ "$COUNT" -le 0 ]; then
  log_error "Worker count must be a positive integer, got: '$COUNT'"
  exit 1
fi

# Warn above soft limit
if [ "$COUNT" -gt "$MAX_WORKERS" ]; then
  log_warn "Scaling to $COUNT workers exceeds the recommended max of $MAX_WORKERS."
  log_warn "Each worker uses ~2 GB RAM. Make sure your server has enough memory."
  read -r -p "Continue? [y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    log_info "Aborted."
    exit 0
  fi
fi

log_info "Scaling workers to $COUNT..."
$DC up -d --no-recreate --scale worker="$COUNT"

show_status
log_success "Workers scaled to $COUNT."
