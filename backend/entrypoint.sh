#!/bin/sh
set -e

# Run Alembic migrations on API container startup
if [ "$SKIP_MIGRATIONS" != "1" ] && [ "$1" != "celery" ]; then
    echo "[ENTRYPOINT] Running Alembic database migrations..."
    alembic upgrade head
    echo "[ENTRYPOINT] Database migrations completed successfully."
fi

# Execute the primary container command
exec "$@"
