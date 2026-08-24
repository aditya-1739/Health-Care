from datetime import date, datetime, timedelta, timezone
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import MedicationStatus, PrescriptionStatus


def test_patient_symptom_submission_and_validation(client, patient_a, patient_a_token, doctor_user, db_session):
    """Test patient submitting symptoms and whitespace/empty rejection."""
    doctor = doctor_user.doctor
    patient = patient_a.patient
    now_utc = datetime.now(timezone.utc)

    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=1),
        end_time=now_utc + timedelta(days=1, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}

    # 1. Whitespace only rejection
    res_err = client.post(
        f"/api/appointments/{app.id}/symptoms",
        json={"symptoms": "   "},
        headers=headers,
    )
    assert res_err.status_code == 422

    # 2. Valid symptom submission
    res_ok = client.post(
        f"/api/appointments/{app.id}/symptoms",
        json={"symptoms": "Persistent dry cough and fatigue for 3 days", "chief_complaint": "Cough"},
        headers=headers,
    )
    assert res_ok.status_code == 201
    data = res_ok.json()
    assert data["symptoms"] == "Persistent dry cough and fatigue for 3 days"
    assert data["chief_complaint"] == "Cough"


def test_doctor_clinical_notes_and_prescription_workflow(
    client, doctor_user, doctor_token, patient_a, patient_a_token, db_session
):
    """Test doctor entering clinical notes and multi-medication prescription."""
    doctor = doctor_user.doctor
    patient = patient_a.patient
    now_utc = datetime.now(timezone.utc)

    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=1),
        end_time=now_utc + timedelta(days=1, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    doc_headers = {"Authorization": f"Bearer {doctor_token}"}

    # 1. Doctor saves clinical notes & diagnosis
    notes_payload = {
        "notes": "Patient lungs clear, throat mildly inflamed. Prescribed oral antibiotic and cough syrup.",
        "diagnosis": "Upper Respiratory Tract Infection",
    }
    res_notes = client.post(
        f"/api/appointments/{app.id}/clinical-notes",
        json=notes_payload,
        headers=doc_headers,
    )
    assert res_notes.status_code == 201
    assert res_notes.json()["diagnosis"] == "Upper Respiratory Tract Infection"

    # 2. Doctor creates structured prescription with multiple medications
    today = date.today()
    rx_payload = {
        "general_instructions": "Drink plenty of water and complete full course.",
        "medications": [
            {
                "name": "Amoxicillin",
                "dosage": "500 mg",
                "frequency": "THREE_TIMES_DAILY",
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=7)).isoformat(),
                "instructions": "Take after meals",
            },
            {
                "name": "Dextromethorphan",
                "dosage": "15 ml",
                "frequency": "TWICE_DAILY",
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=5)).isoformat(),
                "instructions": "Take as needed for cough",
            },
        ],
    }
    res_rx = client.post(
        f"/api/appointments/{app.id}/prescription",
        json=rx_payload,
        headers=doc_headers,
    )
    assert res_rx.status_code == 201
    rx_data = res_rx.json()
    assert len(rx_data["medications"]) == 2
    assert rx_data["version"] == 1
    assert rx_data["status"] == "ACTIVE"

    # 3. Patient can view prescription
    pat_headers = {"Authorization": f"Bearer {patient_a_token}"}
    res_pat_rx = client.get(f"/api/appointments/{app.id}/prescription", headers=pat_headers)
    assert res_pat_rx.status_code == 200
    assert len(res_pat_rx.json()["medications"]) == 2


def test_clinical_data_isolation_between_patients(
    client, doctor_user, patient_a, patient_b, patient_b_token, db_session
):
    """Test Patient B cannot access Patient A's clinical notes or prescription."""
    doctor = doctor_user.doctor
    now_utc = datetime.now(timezone.utc)

    app_a = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=1),
        end_time=now_utc + timedelta(days=1, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app_a)
    db_session.commit()

    headers_b = {"Authorization": f"Bearer {patient_b_token}"}

    res_notes = client.get(f"/api/appointments/{app_a.id}/clinical-notes", headers=headers_b)
    assert res_notes.status_code == 403

    res_rx = client.get(f"/api/appointments/{app_a.id}/prescription", headers=headers_b)
    assert res_rx.status_code == 403
