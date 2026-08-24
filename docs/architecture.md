# Healthcare Appointment & Follow-Up Platform — Architecture Specification

## 1. System Architecture Overview

The platform is designed as a secure, production-grade healthcare appointment and clinical follow-up system with strict medical safety guarantees, atomic concurrency control, and asynchronous failure independence.

```
[ Web Browser (React Vite SPA) ]
            │  HTTPS (Same-Origin)
            ▼
     [ Nginx Proxy ]
      │             │
  (Static UI)    (/api/*)
                    │
                    ▼
       [ FastAPI Application Server ]
         │ (Gunicorn / Uvicorn)
         ├── Auth & RBAC Guard
         ├── Advisory Lock Concurrency Engine
         └── Outbox Dispatcher
         │
         ├───► [ PostgreSQL Database ] (Advisory Locks, Data Isolation, Outbox Table)
         │
         └───► [ Redis Broker & Cache ]
                     │
                     ▼
           [ Celery Worker Pool ]
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     [ AI Clinical] [ SMTP Email ] [ Google Calendar ]
      (Summaries)    (Outbox)       (OAuth Encrypted)
```

---

## 2. Security & Medical Safety Guarantees

### 🔒 2.1 OAuth Token Encryption-at-Rest
- **AES-256 (Fernet) Cryptography**: Google OAuth `access_token` and `refresh_token` are encrypted at rest using AES-256 (`cryptography.fernet`).
- **In-Memory Decryption**: Tokens are decrypted strictly inside `CalendarService` during live Google API calls.
- **Data Privacy Invariant**: Token strings are never exposed in API responses, logs, or frontend code. Calendar event summaries use generic descriptions (`Healthcare Appointment`) to protect patient privacy.

### 🩺 2.2 Medical Safety Boundary
- **Doctor Authority Invariant**:
  - Doctor's clinical notes and diagnosis in `ClinicalNote` are authoritative and immutable by AI.
  - Doctor's structured prescriptions in `Prescription` and `PrescriptionMedication` are immutable by AI.
  - All AI output is isolated in `AISummary`.
- **Pre-Visit AI Engine**: Synthesizes patient-entered raw symptoms into urgency (`High`/`Medium`/`Low`), chief complaint, and 3 suggested diagnostic questions for the doctor.
- **Post-Visit AI Engine**: Translates complex doctor diagnoses and prescription instructions into plain-language, patient-friendly guidance.
- **Controlled Error Handling**: Schema validation, 3-attempt exponential backoff, and non-blocking failure isolation.

---

## 3. Concurrency & Reliability Engine

### ⚡ 3.1 PostgreSQL Transaction Advisory Locking
To prevent double-booking when multiple patients attempt to hold or book the exact same slot simultaneously (even when no row exists yet in the database):

```
1. Hash (doctor_id, start_time_iso) into a 64-bit integer.
2. Execute: SELECT pg_advisory_xact_lock(hashtext('slot:<doctor_id>:<start_time>'))
3. Re-verify availability inside the transaction.
4. Check active overlapping CONFIRMED / HELD appointments.
5. Insert appointment row (status = HELD / CONFIRMED).
6. Commit transaction (automatically releasing the advisory lock).
```

### 🔁 3.2 Idempotency Mechanics
- Unique idempotency keys scoped by user and action (`idempotency_keys` table).
- Duplicate requests return the exact cached HTTP response without re-executing booking logic or generating duplicate side effects.

### 📬 3.3 Transactional Outbox Pattern & Failure Independence
- Appointment state transitions (confirmation, reschedule, cancellation) commit in the database first; notification and sync tasks are queued in `notifications` and `calendar_events` within the same transaction.
- External outages in LLM, SMTP email, or Google Calendar API **never** block or rollback appointment confirmations, cancellations, or reschedules.

---

## 4. HTTPS, Network Isolation & Production Deployment

### 🌐 4.1 HTTPS / TLS Termination Architecture
```
Internet
   │  HTTPS (Port 443)
   ▼
[ Cloud / Platform Load Balancer (TLS Termination) ]
   │  HTTP (Internal Network)
   ▼
[ Nginx Reverse Proxy (Frontend Container) ]
   │
   ├──► Static Web UI (/index.html)
   │
   └──► FastAPI Web API (http://backend:8000/api/)
```

### 🛡️ 4.2 Network Isolation & Non-Root Containers
- **Internal Docker Network**: PostgreSQL (5432) and Redis (6379) are strictly accessible inside the internal Docker bridge network. They are not published to the public host.
- **Non-Root Runtime**: Backend and Celery containers execute as unprivileged user `appuser` (UID 1000).
- **Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
