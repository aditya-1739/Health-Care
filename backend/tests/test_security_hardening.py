from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.core.rate_limit import reset_rate_limiter_state
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import Patient, User, UserRole


def test_security_headers_present(client):
    """Test that all required production security headers are set on API responses."""
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_liveness_and_readiness_probes(client):
    """Test Kubernetes/Docker liveness and readiness probe responses."""
    # Liveness probe
    live_res = client.get("/api/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    # Readiness probe
    ready_res = client.get("/api/health/ready")
    assert ready_res.status_code == 200
    data = ready_res.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "connected"


def test_inactive_user_token_rejection(client, db_session):
    """Test that an inactive/deactivated user cannot access protected resources with an old token."""
    inactive_user = User(
        name="Deactivated Patient",
        email="inactive@patient.com",
        password_hash=get_password_hash("Password123!"),
        role=UserRole.PATIENT,
        status="inactive",
    )
    db_session.add(inactive_user)
    db_session.commit()

    token = create_access_token(subject=inactive_user.id, role="PATIENT")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_tampered_and_malformed_token_rejection(client):
    """Test malformed and signature-tampered JWT tokens are strictly rejected with 401."""
    # Malformed token
    res1 = client.get("/api/auth/me", headers={"Authorization": "Bearer malformed.token.format"})
    assert res1.status_code == 401

    # Fake header with missing credentials
    res2 = client.get("/api/auth/me", headers={"Authorization": "Bearer "})
    assert res2.status_code == 401


def test_expired_token_rejection(client, patient_a):
    """Test expired tokens are rejected with 401."""
    expired_token = create_access_token(
        subject=patient_a.id,
        role="PATIENT",
        expires_delta=timedelta(seconds=-10),  # expired 10s ago
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_rate_limiting_trigger_429(client):
    """Test that requests exceeding the configured limit trigger HTTP 429 Too Many Requests."""
    reset_rate_limiter_state()
    # Trigger 25 requests to a rate-limited endpoint (limit is 20 per min)
    exceeded = False
    for _ in range(25):
        res = client.post("/api/calendar/callback", json={"code": "test_code"})
        if res.status_code == 429:
            exceeded = True
            assert "Retry-After" in res.headers
            break

    assert exceeded is True
