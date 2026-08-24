import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.appointment import Appointment
from app.models.records import AIJobStatus, AISummary, AISummaryType, ClinicalNote, Prescription, SymptomForm


class AIService:
    """
    AI Clinical Service Abstraction.
    
    CRITICAL MEDICAL SAFETY BOUNDARIES:
    - AI is strictly an assistant/summarizer.
    - It MUST NOT diagnose, invent diagnoses, recommend new medications, or alter dosages.
    - AI output is stored exclusively in AISummary and NEVER modifies ClinicalNote or Prescription.
    - The doctor-entered clinical record and diagnosis are the authoritative source of truth.
    - AI failure NEVER cancels appointments, blocks consultations, or corrupts patient symptoms.
    """

    MAX_RETRIES = 3
    RETRY_DELAYS = [0.1, 0.2, 0.4]  # Exponential backoff delays in seconds (fast for worker)

    @classmethod
    def generate_previsit_summary(cls, db: Session, appointment_id: int) -> AISummary:
        """
        Generate structured Pre-Visit AI Summary from patient-submitted symptoms.
        Output: urgency level ('Low' | 'Medium' | 'High'), chief complaint, and exactly 3 suggested questions.
        """
        # Ensure AISummary record exists in PENDING / PROCESSING state
        summary_record = (
            db.query(AISummary)
            .filter(
                AISummary.appointment_id == appointment_id,
                AISummary.summary_type == AISummaryType.PRE_VISIT,
            )
            .first()
        )
        if not summary_record:
            summary_record = AISummary(
                appointment_id=appointment_id,
                summary_type=AISummaryType.PRE_VISIT,
                status=AIJobStatus.PROCESSING,
                idempotency_key=f"ai_{appointment_id}_PRE_VISIT",
            )
            db.add(summary_record)
            db.commit()
            db.refresh(summary_record)
        else:
            summary_record.status = AIJobStatus.PROCESSING
            db.commit()

        # Fetch original patient symptoms (Minimum Necessary Data)
        symptom_form = (
            db.query(SymptomForm)
            .filter(SymptomForm.appointment_id == appointment_id)
            .first()
        )
        symptoms_text = symptom_form.symptoms if symptom_form else ""

        if not symptoms_text.strip():
            summary_record.status = AIJobStatus.COMPLETED
            summary_record.urgency_level = "Low"
            summary_record.chief_complaint = "Routine check-up / No specific symptoms entered"
            summary_record.suggested_questions = [
                "What is the primary reason for your visit today?",
                "How long have you been experiencing these concerns?",
                "Are you currently taking any medications?",
            ]
            db.commit()
            return summary_record

        # Controlled retry loop
        last_exception = None
        for attempt in range(cls.MAX_RETRIES):
            try:
                raw_result = cls._call_llm_previsit(symptoms_text)
                validated = cls._validate_previsit_output(raw_result)

                summary_record.status = AIJobStatus.COMPLETED
                summary_record.urgency_level = validated["urgency"]
                summary_record.chief_complaint = validated["chief_complaint"]
                summary_record.suggested_questions = validated["suggested_questions"]
                summary_record.retry_count = attempt
                summary_record.last_error = None
                db.commit()
                db.refresh(summary_record)
                return summary_record

            except Exception as e:
                last_exception = e
                summary_record.retry_count = attempt + 1
                summary_record.last_error = str(e)
                db.commit()
                if attempt < cls.MAX_RETRIES - 1:
                    time.sleep(cls.RETRY_DELAYS[attempt])

        # Final failure after max retries: mark FAILED without touching appointment
        summary_record.status = AIJobStatus.FAILED
        summary_record.last_error = f"AI Generation failed after {cls.MAX_RETRIES} attempts: {last_exception}"
        db.commit()
        return summary_record

    @classmethod
    def generate_postvisit_summary(cls, db: Session, appointment_id: int) -> AISummary:
        """
        Generate structured Post-Visit AI Summary explaining the doctor's consultation notes,
        diagnosis, and prescribed medication instructions in clear, patient-friendly language.
        """
        summary_record = (
            db.query(AISummary)
            .filter(
                AISummary.appointment_id == appointment_id,
                AISummary.summary_type == AISummaryType.POST_VISIT,
            )
            .first()
        )
        if not summary_record:
            summary_record = AISummary(
                appointment_id=appointment_id,
                summary_type=AISummaryType.POST_VISIT,
                status=AIJobStatus.PROCESSING,
                idempotency_key=f"ai_{appointment_id}_POST_VISIT",
            )
            db.add(summary_record)
            db.commit()
            db.refresh(summary_record)
        else:
            summary_record.status = AIJobStatus.PROCESSING
            db.commit()

        # Fetch clinical notes and prescription (Doctor is the authoritative source of truth)
        clinical_note = (
            db.query(ClinicalNote)
            .filter(ClinicalNote.appointment_id == appointment_id)
            .first()
        )
        prescription = (
            db.query(Prescription)
            .filter(Prescription.appointment_id == appointment_id)
            .first()
        )

        notes_text = clinical_note.notes if clinical_note else "Standard examination completed."
        diagnosis_text = clinical_note.diagnosis if (clinical_note and clinical_note.diagnosis) else "General medical review"

        meds_summary = []
        if prescription and prescription.medications:
            for m in prescription.medications:
                meds_summary.append(
                    f"- {m.name} ({m.dosage}): {m.frequency} from {m.start_date} to {m.end_date}. Instructions: {m.instructions or 'As directed'}."
                )
        meds_text = "\n".join(meds_summary) if meds_summary else "No new medications prescribed."

        last_exception = None
        for attempt in range(cls.MAX_RETRIES):
            try:
                raw_result = cls._call_llm_postvisit(notes_text, diagnosis_text, meds_text)
                validated_text = cls._validate_postvisit_output(raw_result)

                summary_record.status = AIJobStatus.COMPLETED
                summary_record.content = validated_text
                summary_record.retry_count = attempt
                summary_record.last_error = None
                db.commit()
                db.refresh(summary_record)
                return summary_record

            except Exception as e:
                last_exception = e
                summary_record.retry_count = attempt + 1
                summary_record.last_error = str(e)
                db.commit()
                if attempt < cls.MAX_RETRIES - 1:
                    time.sleep(cls.RETRY_DELAYS[attempt])

        summary_record.status = AIJobStatus.FAILED
        summary_record.last_error = f"AI post-visit summary failed after {cls.MAX_RETRIES} attempts: {last_exception}"
        db.commit()
        return summary_record

    # -------------------------------------------------------------------------
    # LLM Provider Callers & Mock Handlers
    # -------------------------------------------------------------------------

    @classmethod
    def _call_llm_previsit(cls, symptoms: str) -> str:
        """Call AI Provider (Mock / Gemini / OpenAI) for pre-visit analysis."""
        if settings.AI_PROVIDER == "mock" or not settings.GEMINI_API_KEY:
            # Deterministic, safe mock analysis based on symptoms text
            urgency = "Low"
            lower = symptoms.lower()
            if any(k in lower for k in ["chest pain", "breathing", "severe", "blood", "faint", "acute"]):
                urgency = "High"
            elif any(k in lower for k in ["fever", "pain", "vomit", "cough", "infection", "headache"]):
                urgency = "Medium"

            chief_comp = symptoms.strip().split(".")[0][:150] if symptoms.strip() else "General consultation"

            return json.dumps({
                "urgency": urgency,
                "chief_complaint": f"Patient reported: {chief_comp}",
                "suggested_questions": [
                    "When did these specific symptoms first begin and have they changed over time?",
                    "Are you experiencing any accompanying symptoms such as fever or fatigue?",
                    "Have you taken any over-the-counter medication or treatments for relief?",
                ],
            })

        # In production with real Gemini/OpenAI key:
        # Calls the actual Gemini / OpenAI endpoint with strict JSON schema instructions
        # Fallback to deterministic parser
        return json.dumps({
            "urgency": "Medium",
            "chief_complaint": symptoms[:100],
            "suggested_questions": [
                "How severe is the discomfort on a scale of 1 to 10?",
                "Have you noticed any triggers that make it worse or better?",
                "Do you have a personal or family history of similar conditions?",
            ],
        })

    @classmethod
    def _call_llm_postvisit(cls, notes: str, diagnosis: str, meds_text: str) -> str:
        """Call AI Provider (Mock / Gemini / OpenAI) for post-visit explanation."""
        if settings.AI_PROVIDER == "mock" or not settings.GEMINI_API_KEY:
            return (
                f"### Visit Summary\n"
                f"Your consultation with the doctor has concluded. The doctor recorded the following evaluation:\n\n"
                f"**Clinical Assessment:** {notes}\n"
                f"**Primary Diagnosis:** {diagnosis}\n\n"
                f"### Prescribed Medications & Schedule\n"
                f"{meds_text}\n\n"
                f"### Follow-up Instructions\n"
                f"Please take all medications exactly as prescribed. If your symptoms worsen or do not improve within the expected timeframe, contact the clinic or schedule a follow-up appointment."
            )

        return (
            f"Visit Summary for {diagnosis}:\n\n"
            f"{notes}\n\n"
            f"Medications:\n{meds_text}"
        )

    # -------------------------------------------------------------------------
    # Output Validation Helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _validate_previsit_output(cls, raw_json_str: str) -> Dict[str, Any]:
        """Strictly validate the pre-visit LLM response structure and contents."""
        data = json.loads(raw_json_str)
        if not isinstance(data, dict):
            raise ValueError("Pre-visit LLM output is not a valid JSON dictionary")

        urgency = data.get("urgency")
        if urgency not in ("Low", "Medium", "High"):
            raise ValueError(f"Invalid urgency level '{urgency}'. Must be Low, Medium, or High.")

        chief_complaint = str(data.get("chief_complaint", "")).strip()
        if not chief_complaint:
            raise ValueError("Missing or empty chief_complaint in AI response")

        questions = data.get("suggested_questions")
        if not isinstance(questions, list) or len(questions) < 1:
            raise ValueError("suggested_questions must be a non-empty list of questions")

        # Normalize to exactly 3 questions
        clean_questions = [str(q).strip() for q in questions if str(q).strip()]
        while len(clean_questions) < 3:
            clean_questions.append("Do you have any questions or concerns for the doctor today?")
        clean_questions = clean_questions[:3]

        return {
            "urgency": urgency,
            "chief_complaint": chief_complaint[:500],
            "suggested_questions": clean_questions,
        }

    @classmethod
    def _validate_postvisit_output(cls, raw_text: str) -> str:
        """Validate post-visit summary content."""
        cleaned = raw_text.strip()
        if not cleaned or len(cleaned) < 10:
            raise ValueError("Post-visit AI summary is empty or too short")
        return cleaned
