def test_health_check(client):
    """Verify health check endpoint returns 200 and connected status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_root_endpoint(client):
    """Verify root documentation entry endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Healthcare Appointment Manager API"
    assert "docs" in data
