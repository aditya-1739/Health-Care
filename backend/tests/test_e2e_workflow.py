from datetime import date, datetime, time, timedelta, timezone
from app.models.records import MedicationReminder, Notification, Prescription, SymptomForm
from app.models.user import DoctorWorkingHours
from app.services.ai_service import AIService
from app.services.medication_service import MedicationService


def test_full_clinical_lifecycle_e2e(client, db_session, doctor_user, doctor_token):
    """
    COMPLETE END-TO-END PATIENT & DOCTOR WORKFLOW TEST:
    1. Patient registers & logs in.
    2. Searches for doctor & fetches availability slots.
    3. Holds a 30-min slot.
    4. Submits pre-visit symptoms.
    5. Confirms appointment (triggering outbox tasks).
    6. Doctor inspects patient symptoms & AI pre-visit summary.
    7. Doctor enters clinical notes and diagnosis.
    8. Doctor creates multi-medication structured prescription.
    9. Doctor completes appointment.
    10. AI generates post-visit plain-language summary.
    11. Medication reminders are scheduled in UTC.
    12. Patient logs in and views completed consultation records & reminder schedule.
    """
    doctor = doctor_user.doctor

    # Configure Doctor Working Hours for upcoming Monday (09:00 - 17:00)
    today = date.today()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_monday = today + timedelta(days=days_ahead)

    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db_session.add(wh)
    db_session.commit()

    # Step 1: Patient Registers
    reg_payload = {
        "name": "E2E Test Patient",
        "email": "e2e_patient@example.com",
        "password": "SecurePassword123!",
        "phone": "555-0999",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # Step 2: Patient Logs In
    login_res = client.post("/api/auth/login", json={"email": "e2e_patient@example.com", "password": "SecurePassword123!"})
    assert login_res.status_code == 200
    pat_token = login_res.json()["access_token"]
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    # Step 3: Patient checks availability
    avail_res = client.get(f"/api/doctors/{doctor.id}/availability?date={target_monday.isoformat()}", headers=pat_headers)
    assert avail_res.status_code == 200
    slots = avail_res.json()["slots"]
    available_slots = [s for s in slots if s["available"]]
    assert len(available_slots) > 0
    selected_slot = available_slots[0]

    # Step 4: Patient holds slot
    hold_res = client.post(
        "/api/appointments/hold",
        json={"doctor_id": doctor.id, "start_time": selected_slot["start_time"]},
        headers=pat_headers,
    )
    assert hold_res.status_code == 201
    appointment_id = hold_res.json()["appointment_id"]

    # Step 5: Patient submits symptoms
    sym_res = client.post(
        f"/api/appointments/{appointment_id}/symptoms",
        json={"symptoms": "High fever, body aches, and persistent dry cough for 3 days.", "chief_complaint": "Flu symptoms"},
        headers=pat_headers,
    )
    assert sym_res.status_code == 201

    # Step 6: Patient confirms appointment
    confirm_res = client.post(f"/api/appointments/{appointment_id}/confirm", headers=pat_headers)
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "CONFIRMED"

    # Step 7: System AI generates Pre-Visit Summary
    previsit_summary = AIService.generate_previsit_summary(db_session, appointment_id)
    assert previsit_summary.status.value == "COMPLETED"
    assert len(previsit_summary.suggested_questions) == 3

    # Step 8: Doctor logs in and inspects consultation details
    doc_headers = {"Authorization": f"Bearer {doctor_token}"}
    doc_sym_res = client.get(f"/api/appointments/{appointment_id}/symptoms", headers=doc_headers)
    assert doc_sym_res.status_code == 200
    assert "High fever" in doc_sym_res.json()["symptoms"]

    # Step 9: Doctor records clinical notes & diagnosis
    notes_res = client.post(
        f"/api/appointments/{appointment_id}/clinical-notes",
        json={"notes": "Throat erythematous, chest sounds clear. Prescribed oral antibiotics.", "diagnosis": "Acute Bronchitis"},
        headers=doc_headers,
    )
    assert notes_res.status_code == 201

    # Step 10: Doctor creates structured multi-medication prescription
    rx_payload = {
        "general_instructions": "Take medications with full glass of water. Rest adequately.",
        "medications": [
            {
                "name": "Azithromycin",
                "dosage": "500 mg",
                "frequency": "ONCE_DAILY",
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=5)).isoformat(),
                "instructions": "Take once daily before food",
            },
            {
                "name": "Paracetamol",
                "dosage": "650 mg",
                "frequency": "TWICE_DAILY",
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=3)).isoformat(),
                "instructions": "Take after food as needed for fever",
            },
        ],
    }
    rx_res = client.post(f"/api/appointments/{appointment_id}/prescription", json=rx_payload, headers=doc_headers)
    assert rx_res.status_code == 201
    assert len(rx_res.json()["medications"]) == 2

    # Step 11: Doctor marks appointment complete
    comp_res = client.post(f"/api/appointments/{appointment_id}/complete", headers=doc_headers)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"

    # Step 12: System AI generates Post-Visit Summary
    postvisit_summary = AIService.generate_postvisit_summary(db_session, appointment_id)
    assert postvisit_summary.status.value == "COMPLETED"
    assert "Acute Bronchitis" in postvisit_summary.content

    # Step 13: Patient retrieves visit outcomes and medication reminders
    pat_rx_res = client.get(f"/api/appointments/{appointment_id}/prescription", headers=pat_headers)
    assert pat_rx_res.status_code == 200
    assert len(pat_rx_res.json()["medications"]) == 2

    pat_rem_res = client.get("/api/patients/me/medication-reminders", headers=pat_headers)
    assert pat_rem_res.status_code == 200
    reminders = pat_rem_res.json()
    assert len(reminders) > 0  # Azithromycin (6 reminders) + Paracetamol (8 reminders)
