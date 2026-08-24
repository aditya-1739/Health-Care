# Healthcare Appointment Manager — Security Specification

This document details the security model, cryptographic safeguards, data isolation policies, and access controls implemented across the Healthcare Appointment Manager.

---

## 1. Authentication & Role-Based Access Control (RBAC)

### 1.1 JWT Session Management
- **Algorithm**: `HS256` signed JSON Web Tokens.
- **Expiration**: 24 hours (`1440` minutes).
- **Token Invalidation**: When a user changes their password via `/api/profile/me/change-password`, their previous authentication token is invalidated, requiring fresh authentication with the new credentials.

### 1.2 Role Boundaries
The system defines 3 distinct user roles:
1. **`PATIENT`**:
   - Can view and edit own personal basic profile.
   - Can view and edit own medical profile (allergies, height, weight, chronic conditions).
   - Cannot view or edit another patient's profile or medical records (`403 Forbidden`).
   - Can book, reschedule, and cancel own appointments.
   - Can submit pre-visit symptom forms.
   - Can view own prescriptions and medication reminders.
2. **`DOCTOR`**:
   - Can view assigned patient appointments and queues.
   - Can access patient medical profiles **only** when an active clinical consultation relationship exists.
   - Can author authoritative clinical notes, diagnoses, and structured digital prescriptions.
   - Can request leaves and manage working hours.
   - Cannot access administrative dashboard or user provisioning APIs (`403 Forbidden`).
3. **`ADMIN`**:
   - Can provision and manage practitioner and staff accounts.
   - Can review and approve/decline doctor leave requests.
   - Can access system-wide audit logs and reliability metrics.
   - Can view user profiles without exposing passwords, password hashes, JWTs, or secrets.

---

## 2. Cryptographic Controls & Data Protection

### 2.1 Passwords & Credentials
- Passwords are encrypted using salted `bcrypt` hashing algorithms.
- Plaintext passwords, password hashes, and tokens are never exposed in any API response, log file, or serialization payload.

### 2.2 OAuth Token Encryption at Rest
- Google Calendar OAuth `access_token` and `refresh_token` are encrypted at rest using AES-256 Fernet authenticated encryption (`cryptography.fernet`).
- Decryption happens strictly in-memory during external Google Calendar sync operations.

---

## 3. Concurrency Protection & Anti-Collusion

### 3.1 PostgreSQL Transactional Advisory Locks
- Double-booking prevention uses `SELECT pg_advisory_xact_lock(hashtext('slot:<doctor_id>:<start_time>'))`.
- Concurrency locks are scoped to specific doctor slots and auto-release on transaction commit/rollback.

### 3.2 Slot Hold Expiration
- Temporary slot holds guarantee that patients have a locked booking window to complete pre-visit details without race conditions.
- Expired holds automatically release slots back to the public pool.

---

## 4. Rate Limiting & Abuse Prevention

- **Auth Endpoints** (`/api/auth/*`): 20 requests per minute per IP.
- **Booking Endpoints** (`/api/appointments/*`): 30 requests per minute per user/IP.
- **Medicine Search** (`/api/medicines/*`): 60 requests per minute per IP.
- **AI Clinical Synthesis**: 10 requests per minute per user/IP.

---

## 5. Security Audit Logging

All security-sensitive operations generate immutable audit records stored in `audit_logs`:
- User registration and authentication events
- Appointment creation, rescheduling, and cancellations
- Doctor leave requests, approvals, and declines
- Profile updates and password changes
- Outbox background dispatches and retries
