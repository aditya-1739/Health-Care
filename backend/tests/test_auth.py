def test_patient_registration_success(client):
    """Test standard patient registration."""
    payload = {
        "name": "Jane Doe",
        "email": "jane.doe@example.com",
        "password": "SecurePassword123!",
        "phone": "+1-555-888-9999",
        "date_of_birth": "1995-06-15",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["email"] == "jane.doe@example.com"
    assert data["role"] == "PATIENT"
    assert data["patient_id"] is not None
    assert "password_hash" not in data


def test_patient_registration_duplicate_email(client, patient_a):
    """Test duplicate registration returns 400 Bad Request."""
    payload = {
        "name": "Duplicate Alice",
        "email": patient_a.email,
        "password": "AnotherPassword123!",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_registration_invalid_data(client):
    """Test validation errors for invalid payload (short password, invalid email)."""
    # Invalid email
    response = client.post(
        "/api/auth/register",
        json={"name": "Invalid", "email": "not-an-email", "password": "Pass12345!"},
    )
    assert response.status_code == 422

    # Short password
    response = client.post(
        "/api/auth/register",
        json={"name": "Invalid", "email": "valid@email.com", "password": "short"},
    )
    assert response.status_code == 422


def test_login_success(client, patient_a):
    """Test valid credentials returns JWT access token."""
    payload = {
        "email": "alice@patient.com",
        "password": "AlicePass123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@patient.com"
    assert data["user"]["role"] == "PATIENT"


def test_login_invalid_password(client, patient_a):
    """Test wrong password returns 401 Unauthorized."""
    payload = {
        "email": "alice@patient.com",
        "password": "WrongPassword123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_nonexistent_user(client):
    """Test non-existent user returns 401 Unauthorized."""
    payload = {
        "email": "nobody@nowhere.com",
        "password": "SomePassword123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401


def test_auth_me_without_token(client):
    """Test accessing /api/auth/me without token returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_auth_me_with_valid_token(client, patient_a, patient_a_token):
    """Test accessing /api/auth/me with valid Bearer token returns profile."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == patient_a.id
    assert data["email"] == patient_a.email
    assert data["role"] == "PATIENT"


def test_logout(client, patient_a_token):
    """Test logout endpoint with valid token."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"
