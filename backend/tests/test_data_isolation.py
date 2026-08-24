def test_patient_access_own_profile(client, patient_a, patient_a_token):
    """Patient can view their own profile."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.get("/api/patients/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == patient_a.email
    assert data["phone"] == "555-0101"


def test_patient_a_cannot_access_patient_b_data(
    client, patient_a, patient_a_token, patient_b
):
    """Patient A attempting to access Patient B record by ID receives 403 Forbidden."""
    patient_b_id = patient_b.patient.id
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.get(f"/api/patients/{patient_b_id}", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_patient_a_can_access_own_data_by_id(client, patient_a, patient_a_token):
    """Patient A accessing their own record by ID receives 200 OK."""
    patient_a_id = patient_a.patient.id
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.get(f"/api/patients/{patient_a_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == patient_a_id


def test_doctor_cannot_access_unrelated_patient_data(
    client, doctor_user, doctor_token, patient_a
):
    """Doctor with no appointment relationship cannot access patient record."""
    patient_a_id = patient_a.patient.id
    headers = {"Authorization": f"Bearer {doctor_token}"}
    response = client.get(f"/api/patients/{patient_a_id}", headers=headers)
    assert response.status_code == 403
    assert "No clinical relationship" in response.json()["detail"]


def test_admin_can_access_patient_data(client, admin_token, patient_a):
    """Admin can inspect patient data."""
    patient_a_id = patient_a.patient.id
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get(f"/api/patients/{patient_a_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == patient_a_id


def test_public_doctors_listing(client, doctor_user):
    """Public doctor listing exposes safe profile info and no password hashes."""
    response = client.get("/api/doctors")
    assert response.status_code == 200
    doctors = response.json()
    assert len(doctors) >= 1
    doc = doctors[0]
    assert "specialization" in doc
    assert "bio" in doc
    assert "password_hash" not in doc
    assert "password" not in doc


def test_public_single_doctor_profile(client, doctor_user):
    """Single doctor profile query returns doctor info."""
    doctor_id = doctor_user.doctor.id
    response = client.get(f"/api/doctors/{doctor_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doctor_id
    assert data["specialization"] == "Cardiology"
    assert "password_hash" not in data


def test_admin_audit_logs(client, admin_token, patient_a):
    """Admin can query security audit logs."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/audit-logs", headers=headers)
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
