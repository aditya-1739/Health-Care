import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db

router = APIRouter(prefix="/health", tags=["Health & Readiness"])


@router.get("", summary="General system health status")
def health_overview(db: Session = Depends(get_db)):
    """General health overview endpoint."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "database": "disconnected"},
        )


@router.get("/live", summary="Kubernetes / Docker Liveness probe")
def liveness_probe():
    """
    Liveness probe: verifies the application web process is running.
    Does not depend on external infrastructure to prevent unnecessary container restarts.
    """
    return {"status": "alive"}


@router.get("/ready", summary="Kubernetes / Docker Readiness probe")
def readiness_probe(db: Session = Depends(get_db)):
    """
    Readiness probe: verifies core database and cache availability.
    Clearly distinguishes Redis cache health from background Celery worker state.
    """
    db_connected = False
    redis_connected = False

    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    # 2. Redis check
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
        redis_connected = r.ping()
    except Exception:
        redis_connected = False

    all_ready = db_connected
    response_payload = {
        "status": "ready" if all_ready else "not_ready",
        "checks": {
            "database": "connected" if db_connected else "disconnected",
            "redis_cache": "connected" if redis_connected else "disconnected",
        },
    }

    if not all_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response_payload,
        )

    return response_payload
