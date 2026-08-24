def test_unauthenticated_access_to_protected_routes(client):
    """Ensure unauthenticated access to protected routes returns 401."""
    # Protected patients route
    res1 = client.get("/api/patients/me")
    assert res1.status_code == 401

    # Protected admin route
    res2 = client.get("/api/admin/dashboard")
    assert res2.status_code == 401

    # Protected appointments route
    res3 = client.get("/api/appointments")
    assert res3.status_code == 401


def test_patient_accessing_admin_dashboard_is_forbidden(client, patient_a_token):
    """Ensure patient attempting to access admin dashboard receives 403 Forbidden."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.get("/api/admin/dashboard", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_doctor_accessing_admin_dashboard_is_forbidden(client, doctor_token):
    """Ensure doctor attempting to access admin dashboard receives 403 Forbidden."""
    headers = {"Authorization": f"Bearer {doctor_token}"}
    response = client.get("/api/admin/dashboard", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_admin_accessing_admin_dashboard_succeeds(client, admin_token):
    """Ensure admin successfully accesses admin dashboard with 200 OK."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/dashboard", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "total_patients" in data
    assert "total_doctors" in data


def test_patient_cannot_create_users_via_admin_api(client, patient_a_token):
    """Ensure patient cannot invoke admin user creation."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    payload = {
        "name": "Hacker Doctor",
        "email": "hacker@doc.com",
        "password": "Password123!",
        "role": "DOCTOR",
        "specialization": "Surgery",
    }
    response = client.post("/api/admin/users", json=payload, headers=headers)
    assert response.status_code == 403


def test_doctor_cannot_create_users_via_admin_api(client, doctor_token):
    """Ensure doctor cannot invoke admin user creation."""
    headers = {"Authorization": f"Bearer {doctor_token}"}
    payload = {
        "name": "Sub Doctor",
        "email": "subdoc@hospital.com",
        "password": "Password123!",
        "role": "DOCTOR",
        "specialization": "Pediatrics",
    }
    response = client.post("/api/admin/users", json=payload, headers=headers)
    assert response.status_code == 403


def test_admin_can_create_doctor_user(client, admin_token):
    """Ensure admin can successfully provision new Doctor accounts."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "name": "Dr. Gregory House",
        "email": "house@hospital.com",
        "password": "HousePassword123!",
        "role": "DOCTOR",
        "specialization": "Diagnostics",
        "bio": "Head of Diagnostic Medicine",
        "slot_duration": 45,
    }
    response = client.post("/api/admin/users", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Dr. Gregory House"
    assert data["email"] == "house@hospital.com"
    assert data["role"] == "DOCTOR"
    assert data["doctor_id"] is not None


def test_admin_can_list_patients(client, admin_token, patient_a):
    """Ensure admin can list registered patients."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/admin/patients", headers=headers)
    assert res.status_code == 200
    patients = res.json()
    assert len(patients) >= 1
    assert any(p["email"] == patient_a.email for p in patients)


def test_non_admin_cannot_list_patients(client, patient_a_token):
    """Ensure non-admin cannot access admin patients endpoint."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    res = client.get("/api/admin/patients", headers=headers)
    assert res.status_code == 403
