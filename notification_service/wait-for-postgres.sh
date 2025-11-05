#!/bin/sh
# wait-for-postgres.sh
# Usage: wait-for-postgres.sh host:port

set -e

host_and_port="$1"

until pg_isready -d "$DATABASE_URL"; do
  echo "⏳ Waiting for Postgres at $host_and_port..."
  sleep 2
done

echo "✅ Postgres is ready!"
shift
exec "$@"
