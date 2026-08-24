import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.records import IdempotencyKey


def _json_serial(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, )):
        return obj.isoformat()
    return str(obj)


def compute_request_hash(data: Any) -> str:
    """Compute a deterministic SHA-256 hash of the request payload/parameters."""
    if data is None:
        data_str = ""
    elif isinstance(data, dict):
        data_str = json.dumps(data, sort_keys=True, default=_json_serial)
    elif isinstance(data, str):
        data_str = data
    else:
        data_str = str(data)
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


def check_idempotency(
    db: Session,
    user_id: int,
    action: str,
    idempotency_key: Optional[str],
    payload: Any,
) -> Optional[Tuple[int, Dict[str, Any]]]:
    """
    Check if an idempotent request was previously processed for (user_id, action, idempotency_key).
    - If found and hash matches: returns cached (response_code, response_body).
    - If found and hash differs: raises 409 Conflict error.
    - If not found or key is None: returns None (caller proceeds to process request).
    """
    if not idempotency_key:
        return None

    request_hash = compute_request_hash(payload)
    now_utc = datetime.now(timezone.utc)

    record = (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.action == action,
            IdempotencyKey.key == idempotency_key,
        )
        .first()
    )

    if record:
        if record.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key already used with a different request payload.",
            )
        # Return cached response
        return record.response_code, record.response_body

    return None


def store_idempotent_response(
    db: Session,
    user_id: int,
    action: str,
    idempotency_key: Optional[str],
    payload: Any,
    response_code: int,
    response_body: Dict[str, Any],
    ttl_hours: int = 24,
):
    """Save response in idempotency_keys table for replay."""
    if not idempotency_key:
        return

    request_hash = compute_request_hash(payload)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(hours=ttl_hours)

    # Ensure response_body is fully JSON serialized to primitive types
    clean_body = json.loads(json.dumps(response_body, default=_json_serial))

    try:
        record = IdempotencyKey(
            key=idempotency_key,
            user_id=user_id,
            action=action,
            request_hash=request_hash,
            response_code=response_code,
            response_body=clean_body,
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
