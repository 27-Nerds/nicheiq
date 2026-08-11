#!/bin/sh
set -e

echo "Running database migrations..."
npx prisma migrate deploy

if [ "${RUN_COMMERCIAL_COPY_BACKFILL:-false}" = "true" ]; then
  echo "Running authoritative commercial-copy asset migration..."
  /opt/commercial-backfill/bin/python /app/maintenance/backfill_paying_wallet_assets.py \
    --database-url "$DATABASE_URL" \
    --asset-root "${ASSET_ROOT:-/app}"
fi

echo "Starting API server..."
exec "$@"
