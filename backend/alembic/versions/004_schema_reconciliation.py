"""Schema Reconciliation Migration for Phase 3 Clinical, Reliability, and Idempotency Models

Revision ID: 004
Revises: 003
Create Date: 2026-08-23 23:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Idempotently create PostgreSQL custom ENUM types if they do not already exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'aijobstatus') THEN
                CREATE TYPE aijobstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'prescriptionstatus') THEN
                CREATE TYPE prescriptionstatus AS ENUM ('ACTIVE', 'MODIFIED', 'DISCONTINUED', 'CANCELLED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'medicationstatus') THEN
                CREATE TYPE medicationstatus AS ENUM ('ACTIVE', 'DISCONTINUED', 'COMPLETED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reminderstatus') THEN
                CREATE TYPE reminderstatus AS ENUM ('PENDING', 'SENT', 'FAILED', 'CANCELLED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationstatus') THEN
                CREATE TYPE notificationstatus AS ENUM ('QUEUED', 'SENT', 'FAILED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'calendarsyncstatus') THEN
                CREATE TYPE calendarsyncstatus AS ENUM ('PENDING', 'SYNCED', 'FAILED', 'NOT_CONNECTED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'calendarconnectionstatus') THEN
                CREATE TYPE calendarconnectionstatus AS ENUM ('NOT_CONNECTED', 'CONNECTED', 'TOKEN_EXPIRED', 'REVOKED');
            END IF;
        END$$;
    """)

    # 2. Reconcile symptom_forms table
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'symptom_forms' AND column_name = 'updated_at') THEN
                ALTER TABLE symptom_forms ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
            END IF;
        END$$;
    """)

    # 3. Reconcile clinical_notes table
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'clinical_notes' AND column_name = 'updated_at') THEN
                ALTER TABLE clinical_notes ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
            END IF;
        END$$;
    """)

    # 4. Reconcile ai_summaries table
    op.execute("""
        DO $$
        BEGIN
            -- Ensure chief_complaint column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ai_summaries' AND column_name = 'chief_complaint') THEN
                ALTER TABLE ai_summaries ADD COLUMN chief_complaint TEXT;
            END IF;

            -- Ensure status column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ai_summaries' AND column_name = 'status') THEN
                ALTER TABLE ai_summaries ADD COLUMN status aijobstatus NOT NULL DEFAULT 'PENDING';
                CREATE INDEX IF NOT EXISTS ix_ai_summaries_status ON ai_summaries(status);
            END IF;

            -- Ensure retry_count column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ai_summaries' AND column_name = 'retry_count') THEN
                ALTER TABLE ai_summaries ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
            END IF;

            -- Ensure last_error column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ai_summaries' AND column_name = 'last_error') THEN
                ALTER TABLE ai_summaries ADD COLUMN last_error TEXT;
            END IF;

            -- Ensure idempotency_key column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ai_summaries' AND column_name = 'idempotency_key') THEN
                ALTER TABLE ai_summaries ADD COLUMN idempotency_key VARCHAR(255);
                CREATE INDEX IF NOT EXISTS ix_ai_summaries_idempotency_key ON ai_summaries(idempotency_key);
            END IF;

            -- Ensure updated_at column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ai_summaries' AND column_name = 'updated_at') THEN
                ALTER TABLE ai_summaries ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
            END IF;

            -- Make content column nullable
            ALTER TABLE ai_summaries ALTER COLUMN content DROP NOT NULL;
        END$$;
    """)

    # 5. Reconcile prescriptions table
    op.execute("""
        DO $$
        BEGIN
            -- Ensure patient_id column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'prescriptions' AND column_name = 'patient_id') THEN
                ALTER TABLE prescriptions ADD COLUMN patient_id INTEGER;
                -- Backfill patient_id from appointments
                UPDATE prescriptions p SET patient_id = a.patient_id FROM appointments a WHERE p.appointment_id = a.id;
                ALTER TABLE prescriptions ADD CONSTRAINT fk_prescriptions_patient_id FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;
                CREATE INDEX IF NOT EXISTS ix_prescriptions_patient_id ON prescriptions(patient_id);
            END IF;

            -- Ensure version column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'prescriptions' AND column_name = 'version') THEN
                ALTER TABLE prescriptions ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
            END IF;

            -- Ensure status column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'prescriptions' AND column_name = 'status') THEN
                ALTER TABLE prescriptions ADD COLUMN status prescriptionstatus NOT NULL DEFAULT 'ACTIVE';
                CREATE INDEX IF NOT EXISTS ix_prescriptions_status ON prescriptions(status);
            END IF;

            -- Ensure general_instructions column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'prescriptions' AND column_name = 'general_instructions') THEN
                ALTER TABLE prescriptions ADD COLUMN general_instructions TEXT;
            END IF;

            -- Ensure updated_at column exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'prescriptions' AND column_name = 'updated_at') THEN
                ALTER TABLE prescriptions ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
            END IF;

            -- Make legacy columns nullable if they exist
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'prescriptions' AND column_name = 'medication_details') THEN
                ALTER TABLE prescriptions ALTER COLUMN medication_details DROP NOT NULL;
            END IF;
        END$$;
    """)

    # 6. Reconcile prescription_medications status column
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'prescription_medications' AND column_name = 'status' AND data_type != 'USER-DEFINED') THEN
                ALTER TABLE prescription_medications ALTER COLUMN status DROP DEFAULT;
                ALTER TABLE prescription_medications ALTER COLUMN status TYPE medicationstatus USING status::medicationstatus;
                ALTER TABLE prescription_medications ALTER COLUMN status SET DEFAULT 'ACTIVE';
            END IF;
            CREATE INDEX IF NOT EXISTS ix_prescription_medications_status ON prescription_medications(status);
        END$$;
    """)

    # 7. Reconcile medication_reminders table
    op.execute("""
        DO $$
        BEGIN
            -- If legacy medication_reminders table exists with prescription_id column, drop and recreate with model structure
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'medication_reminders' AND column_name = 'prescription_id') THEN
                DROP TABLE medication_reminders CASCADE;
            END IF;

            -- Create medication_reminders if not exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'medication_reminders') THEN
                CREATE TABLE medication_reminders (
                    id SERIAL PRIMARY KEY,
                    prescription_medication_id INTEGER NOT NULL REFERENCES prescription_medications(id) ON DELETE CASCADE,
                    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                    medication_name VARCHAR(150) NOT NULL,
                    dosage VARCHAR(100) NOT NULL,
                    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    status reminderstatus NOT NULL DEFAULT 'PENDING',
                    sent_at TIMESTAMP WITH TIME ZONE,
                    idempotency_key VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CONSTRAINT uq_med_reminder_sched UNIQUE (prescription_medication_id, scheduled_at)
                );
                CREATE INDEX ix_medication_reminders_id ON medication_reminders(id);
                CREATE INDEX ix_medication_reminders_prescription_medication_id ON medication_reminders(prescription_medication_id);
                CREATE INDEX ix_medication_reminders_patient_id ON medication_reminders(patient_id);
                CREATE INDEX ix_medication_reminders_scheduled_at ON medication_reminders(scheduled_at);
                CREATE INDEX ix_medication_reminders_status ON medication_reminders(status);
                CREATE INDEX ix_medication_reminders_idempotency_key ON medication_reminders(idempotency_key);
            END IF;
        END$$;
    """)

    # 8. Reconcile notifications table
    op.execute("""
        DO $$
        BEGIN
            -- If legacy notifications table has title column instead of recipient_email/subject, drop and recreate with model structure
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'title') THEN
                DROP TABLE notifications CASCADE;
            END IF;

            -- Create notifications if not exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notifications') THEN
                CREATE TABLE notifications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL,
                    type VARCHAR(50) NOT NULL DEFAULT 'EMAIL',
                    event_type VARCHAR(100) NOT NULL,
                    recipient_email VARCHAR(255) NOT NULL,
                    subject VARCHAR(255) NOT NULL,
                    body_html TEXT NOT NULL,
                    status notificationstatus NOT NULL DEFAULT 'QUEUED',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TIMESTAMP WITH TIME ZONE,
                    last_error TEXT,
                    sent_at TIMESTAMP WITH TIME ZONE,
                    idempotency_key VARCHAR(255) UNIQUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
                );
                CREATE INDEX ix_notifications_id ON notifications(id);
                CREATE INDEX ix_notifications_user_id ON notifications(user_id);
                CREATE INDEX ix_notifications_appointment_id ON notifications(appointment_id);
                CREATE INDEX ix_notifications_event_type ON notifications(event_type);
                CREATE INDEX ix_notifications_status ON notifications(status);
                CREATE INDEX ix_notifications_idempotency_key ON notifications(idempotency_key);
            END IF;
        END$$;
    """)

    # 9. Reconcile google_calendar_tokens connection_status column
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'google_calendar_tokens' AND column_name = 'connection_status' AND data_type != 'USER-DEFINED') THEN
                ALTER TABLE google_calendar_tokens ALTER COLUMN connection_status DROP DEFAULT;
                ALTER TABLE google_calendar_tokens ALTER COLUMN connection_status TYPE calendarconnectionstatus USING connection_status::calendarconnectionstatus;
                ALTER TABLE google_calendar_tokens ALTER COLUMN connection_status SET DEFAULT 'NOT_CONNECTED';
            END IF;
            CREATE INDEX IF NOT EXISTS ix_google_calendar_tokens_connection_status ON google_calendar_tokens(connection_status);
        END$$;
    """)

    # 10. Reconcile calendar_events table
    op.execute("""
        DO $$
        BEGIN
            -- If legacy calendar_events table has status varchar instead of sync_status enum, drop and recreate
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'calendar_events' AND column_name = 'event_id') THEN
                DROP TABLE calendar_events CASCADE;
            END IF;

            -- Create calendar_events if not exists
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'calendar_events') THEN
                CREATE TABLE calendar_events (
                    id SERIAL PRIMARY KEY,
                    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider VARCHAR(50) NOT NULL DEFAULT 'google',
                    google_event_id VARCHAR(255),
                    sync_status calendarsyncstatus NOT NULL DEFAULT 'PENDING',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    idempotency_key VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
                );
                CREATE INDEX ix_calendar_events_id ON calendar_events(id);
                CREATE INDEX ix_calendar_events_appointment_id ON calendar_events(appointment_id);
                CREATE INDEX ix_calendar_events_user_id ON calendar_events(user_id);
                CREATE INDEX ix_calendar_events_sync_status ON calendar_events(sync_status);
                CREATE INDEX ix_calendar_events_idempotency_key ON calendar_events(idempotency_key);
            END IF;
        END$$;
    """)

    # 11. Create idempotency_keys table if not exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'idempotency_keys') THEN
                CREATE TABLE idempotency_keys (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(255) NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    action VARCHAR(100) NOT NULL,
                    request_hash VARCHAR(64) NOT NULL,
                    response_code INTEGER NOT NULL,
                    response_body JSON NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    CONSTRAINT uq_user_action_idempotency_key UNIQUE (user_id, action, key)
                );
                CREATE INDEX ix_idempotency_keys_id ON idempotency_keys(id);
                CREATE INDEX ix_idempotency_keys_key ON idempotency_keys(key);
                CREATE INDEX ix_idempotency_keys_user_id ON idempotency_keys(user_id);
            END IF;
        END$$;
    """)


def downgrade() -> None:
    pass
