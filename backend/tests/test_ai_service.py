from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import (
    AIJobStatus,
    AISummary,
    AISummaryType,
    ClinicalNote,
    Prescription,
    PrescriptionMedication,
    SymptomForm,
)
from app.services.ai_service import AIService


def test_ai_previsit_summary_generation_success(client, db_session, doctor_user, patient_a):
    """Test generating a structured pre-visit summary with urgency and 3 suggested questions."""
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
    db_session.flush()

    symptom_form = SymptomForm(
        appointment_id=app.id,
        symptoms="Severe chest pain radiating to left arm and shortness of breath for 2 hours.",
        chief_complaint="Chest pain and shortness of breath",
    )
    db_session.add(symptom_form)
    db_session.commit()

    summary = AIService.generate_previsit_summary(db_session, app.id)

    assert summary.status == AIJobStatus.COMPLETED
    assert summary.summary_type == AISummaryType.PRE_VISIT
    assert summary.urgency_level == "High"
    assert "Chest pain" in summary.chief_complaint or "chest pain" in summary.chief_complaint.lower()
    assert len(summary.suggested_questions) == 3


def test_ai_malformed_json_retry_and_fallback(client, db_session, doctor_user, patient_a):
    """Test malformed LLM response triggers retries and sets FAILED without breaking system."""
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
    db_session.flush()

    symptom_form = SymptomForm(
        appointment_id=app.id,
        symptoms="Mild rash on right forearm.",
    )
    db_session.add(symptom_form)
    db_session.commit()

    # Mock LLM returning invalid JSON string across all attempts
    with patch.object(AIService, "_call_llm_previsit", return_value="INVALID_JSON_NON_PARSEABLE"):
        summary = AIService.generate_previsit_summary(db_session, app.id)

        assert summary.status == AIJobStatus.FAILED
        assert summary.retry_count == AIService.MAX_RETRIES
        assert "failed after" in summary.last_error.lower()

    # Verify original symptoms are unchanged
    db_session.refresh(symptom_form)
    assert symptom_form.symptoms == "Mild rash on right forearm."


def test_ai_postvisit_summary_and_safety_boundary(client, db_session, doctor_user, patient_a):
    """
    Test generating post-visit explanation and verify the AI Safety Boundary:
    AI output MUST NOT overwrite or modify ClinicalNote.diagnosis or PrescriptionMedication.
    """
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
    db_session.flush()

    # Authoritative Doctor Clinical Note
    clinical_note = ClinicalNote(
        appointment_id=app.id,
        doctor_id=doctor.id,
        notes="Patient presented with mild seasonal allergies. Prescribed antihistamines.",
        diagnosis="Allergic Rhinitis (Authoritative)",
    )
    # Authoritative Doctor Prescription
    prescription = Prescription(
        appointment_id=app.id,
        doctor_id=doctor.id,
        patient_id=patient.id,
        version=1,
    )
    db_session.add_all([clinical_note, prescription])
    db_session.flush()

    from datetime import date
    med = PrescriptionMedication(
        prescription_id=prescription.id,
        name="Cetirizine",
        dosage="10 mg",
        frequency="ONCE_DAILY",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=7),
        instructions="Take once at bedtime",
    )
    db_session.add(med)
    db_session.commit()

    # Generate Post-Visit AI Summary
    summary = AIService.generate_postvisit_summary(db_session, app.id)

    assert summary.status == AIJobStatus.COMPLETED
    assert summary.summary_type == AISummaryType.POST_VISIT
    assert "Visit Summary" in summary.content
    assert "Allergic Rhinitis" in summary.content
    assert "Cetirizine" in summary.content

    # MEDICAL SAFETY BOUNDARY VERIFICATION:
    # Doctor's clinical diagnosis and medication record remain identical and untouched
    db_session.refresh(clinical_note)
    db_session.refresh(med)
    assert clinical_note.diagnosis == "Allergic Rhinitis (Authoritative)"
    assert med.name == "Cetirizine"
    assert med.dosage == "10 mg"
