#!/bin/bash

# NicheIQ Development Startup Script
# This script starts all required services for development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  NicheIQ Development Environment${NC}"
echo -e "${GREEN}========================================${NC}"

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check for required tools
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker is required but not installed.${NC}" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo -e "${RED}Node.js is required but not installed.${NC}" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Python 3 is required but not installed.${NC}" >&2; exit 1; }

echo -e "\n${YELLOW}Starting Docker services (PostgreSQL + Redis)...${NC}"
docker compose -f docker/docker-compose.yml up -d postgres redis

echo -e "\n${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
sleep 5

# Run Prisma migrations
echo -e "\n${YELLOW}Running database migrations...${NC}"
cd backend
npx prisma migrate deploy
cd ..

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Services Started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e ""
echo -e "PostgreSQL: ${YELLOW}localhost:5435${NC}"
echo -e "Redis:      ${YELLOW}localhost:6380${NC}"
echo -e ""
echo -e "${YELLOW}Now start these in separate terminals:${NC}"
echo -e ""
echo -e "1. Backend API:"
echo -e "   ${GREEN}cd backend && npm run dev${NC}"
echo -e ""
echo -e "2. Python Worker:"
echo -e "   ${GREEN}source .venv/bin/activate && python -m worker.queue_consumer${NC}"
echo -e ""
echo -e "3. Frontend (optional):"
echo -e "   ${GREEN}cd frontend && npm run dev${NC}"
echo -e ""
echo -e "4. Open in browser: ${YELLOW}http://localhost:3000${NC}"
echo -e ""
