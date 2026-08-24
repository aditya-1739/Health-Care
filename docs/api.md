# Healthcare Appointment Manager — API Reference

All API routes are prefixed with `/api` and return JSON payloads.

---

## 1. Authentication & Account APIs

### `POST /api/auth/register`
- **Access**: Public
- **Description**: Registers a new patient user.
- **Request Body**: `name`, `email`, `password`, `phone` (optional), `date_of_birth` (optional).
- **Response**: `201 Created` with User object and JWT access token.

### `POST /api/auth/login`
- **Access**: Public
- **Description**: Authenticates user with email and password.
- **Request Body**: `email`, `password`.
- **Response**: `200 OK` with `access_token`, `token_type`, and user profile.

### `GET /api/auth/me`
- **Access**: Authenticated (`PATIENT`, `DOCTOR`, `ADMIN`)
- **Description**: Returns authenticated user identity.

---

## 2. Profile & Account Management APIs

### `GET /api/profile/me`
- **Access**: Authenticated
- **Description**: Returns current user's profile with dynamically calculated `age`.

### `PUT /api/profile/me`
- **Access**: Authenticated
- **Description**: Updates user profile (name, phone, DOB, bio, address). Email and role remain protected.

### `GET /api/profile/me/medical`
- **Access**: `PATIENT` only
- **Description**: Returns patient's medical profile (blood group, height, weight, allergies, chronic conditions, medications, surgeries, notes).

### `PUT /api/profile/me/medical`
- **Access**: `PATIENT` only
- **Description**: Creates or updates patient's medical profile with numeric range validations (Height: 30–300 cm, Weight: 1–500 kg).

### `GET /api/profile/me/appointments`
- **Access**: `PATIENT` or `DOCTOR`
- **Description**: Returns user's categorized appointments (`upcoming`, `past`, `cancelled`).

### `POST /api/profile/me/change-password`
- **Access**: Authenticated
- **Description**: Validates current password, updates to new password, and invalidates active session.

---

## 3. Medicine Knowledge Layer APIs

### `GET /api/medicines/search?q={query}`
- **Access**: Public
- **Description**: Fast, debounced search across RxNorm terminology with Redis caching.

### `GET /api/medicines/{rxcui}`
- **Access**: Public
- **Description**: Retrieves pharmacological properties, brand names, active ingredients, dosage forms, and official DailyMed SPL indications and warnings.

---

## 4. Appointment & Clinical APIs

### `POST /api/appointments/hold`
- **Access**: `PATIENT`
- **Description**: Acquires a PostgreSQL transactional advisory lock to hold an appointment slot.

### `POST /api/appointments/confirm`
- **Access**: `PATIENT`
- **Description**: Confirms an active slot hold into a booked consultation and schedules notifications in the transactional outbox.

### `POST /api/appointments/{id}/reschedule`
- **Access**: `PATIENT`
- **Description**: Atomically transitions appointment to a new available time slot.

### `POST /api/appointments/{id}/cancel`
- **Access**: `PATIENT`, `DOCTOR`, `ADMIN`
- **Description**: Cancels an appointment with required cancellation reason.

### `POST /api/appointments/{id}/clinical-notes`
- **Access**: `DOCTOR` (Assigned practitioner only)
- **Description**: Records doctor's clinical findings, diagnosis, and prescription.

---

## 5. Doctor Schedule & Leave APIs

### `POST /api/doctors/leave-requests`
- **Access**: `DOCTOR`
- **Description**: Submits a clinical absence request for administrator review.

### `GET /api/doctors/leave-requests`
- **Access**: `DOCTOR`
- **Description**: Lists doctor's past and pending leave requests.

---

## 6. Administration APIs

### `GET /api/admin/dashboard`
- **Access**: `ADMIN`
- **Description**: Returns system stats, practitioner counts, and booking statistics.

### `GET /api/admin/users`
- **Access**: `ADMIN`
- **Description**: Searches and lists system users filtered by role.

### `GET /api/admin/users/{user_id}/profile`
- **Access**: `ADMIN`
- **Description**: Returns detailed user profile (including patient medical history or doctor credentials) without exposing passwords or tokens.

### `POST /api/admin/leave-requests/{id}/approve`
- **Access**: `ADMIN`
- **Description**: Approves a practitioner leave request and logs affected appointment notifications.

### `POST /api/admin/leave-requests/{id}/decline`
- **Access**: `ADMIN`
- **Description**: Declines a practitioner leave request with required administrative remarks.

### `GET /api/admin/reliability/metrics`
- **Access**: `ADMIN`
- **Description**: Returns status counts for AI jobs, notification dispatches, and calendar syncs.
