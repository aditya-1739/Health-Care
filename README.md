# Healthcare Appointment Manager

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react&logoColor=black)](https://reactjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg?logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A.svg?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A production-grade, secure healthcare appointment and clinical follow-up platform with atomic PostgreSQL advisory locking, transactional outbox dispatching, clinical symptom intake, structured digital prescriptions, authoritative NIH RxNorm / DailyMed medicine search, and role-based access control.

---

## 1. Key Features

- **Double-Booking Prevention**: PostgreSQL transactional advisory locks prevent race conditions on appointment slots.
- **Pre-Visit Symptom Intake**: Patients submit structured chief complaints and symptoms prior to consultations.
- **Doctor Clinical Workflows**: Practitioners review AI-assisted clinical summaries, record consultation notes, and author structured digital prescriptions.
- **Authoritative Medicine Knowledge**: Public search and doctor prescription autocompletion powered by NIH RxNorm and DailyMed Structured Product Labeling (SPL) with Redis caching.
- **Complete Account & Medical Profile**: Dynamic age calculation from date of birth, blood group tracking, allergies, chronic conditions, and appointment history categorization.
- **Transactional Outbox Engine**: Google Calendar two-way synchronization and email notifications dispatched with retry backoff and failure isolation.
- **Doctor Absence Management**: Clinical leave request and administrative review ledger with patient conflict warnings.
- **Enterprise Security**: AES-256 Fernet encrypted OAuth credentials at rest, JWT sessions, strict RBAC, and immutable audit logs.

---

## 2. Technology Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Gunicorn/Uvicorn.
- **Frontend**: React 18, Vite, Vanilla CSS Design System, Responsive UI with smooth transitions.
- **Database & Cache**: PostgreSQL 16 (Advisory Locks, Outbox Table), Redis 7 (Cache & Celery Broker).
- **Background Tasks**: Celery Worker with retry policies and exponential backoff.
- **Reverse Proxy**: Nginx (Alpine) with security headers and `/api` proxying.

---

## 3. System Architecture

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
         ├───► [ PostgreSQL Database ] (Advisory Locks, Outbox, Medical Profiles)
         │
         └───► [ Redis Broker & Cache ] (Medicine Cache, Celery Queue)
                     │
                     ▼
           [ Celery Worker Pool ]
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     [ AI Clinical] [ SMTP Email ] [ Google Calendar ]
```

---

## 4. User Roles & Capabilities

| Feature | Patient | Doctor | Admin | Public |
| :--- | :---: | :---: | :---: | :---: |
| Browse Doctors & Specialties | ✅ | ✅ | ✅ | ✅ |
| Public Medicine Information Search | ✅ | ✅ | ✅ | ✅ |
| Book & Hold Appointment Slots | ✅ | ❌ | ❌ | ❌ |
| Submit Pre-Visit Symptoms | ✅ | ❌ | ❌ | ❌ |
| View Own Medical Profile | ✅ | ❌ | ❌ | ❌ |
| Author Clinical Notes & Prescriptions | ❌ | ✅ | ❌ | ❌ |
| View Assigned Patient Clinical Records | ❌ | ✅ (Authorized) | ❌ | ❌ |
| Request Leave / Adjust Shifts | ❌ | ✅ | ❌ | ❌ |
| User Provisioning & Staff Directory | ❌ | ❌ | ✅ | ❌ |
| Approve / Decline Doctor Leaves | ❌ | ❌ | ✅ | ❌ |
| Audit Logs & Reliability Metrics | ❌ | ❌ | ✅ | ❌ |

---

## 5. Project Structure

```
.
├── backend/
│   ├── alembic/              # Alembic database migrations (001 -> 006)
│   ├── app/
│   │   ├── api/v1/           # Modular FastAPI route handlers
│   │   ├── core/             # Configuration, Database session, Security
│   │   ├── models/           # SQLAlchemy models (User, Patient, Doctor, Appt, etc.)
│   │   ├── schemas/          # Pydantic v2 schemas and validators
│   │   ├── services/         # Clinical, Medicine (RxNorm/DailyMed), Outbox services
│   │   └── worker/           # Celery application configuration
│   ├── scripts/              # Development seed scripts
│   ├── tests/                # 119 Unit, integration, and security test suites
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── public/images/        # High-resolution, licensed medical consultation imagery
│   ├── src/
│   │   ├── api/client.js     # Unified Axios/Fetch API client with error formatter
│   │   ├── components/       # Navbar, UserMenu, ProtectedRoute
│   │   ├── context/          # AuthContext
│   │   ├── pages/            # LandingPage, ProfilePage, Dashboards, MedicineInfo
│   │   └── styles/index.css  # Unified design system tokens and responsive styles
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docs/                     # Production architecture, security, deployment, and API docs
├── docker-compose.yml        # Local development compose stack
├── docker-compose.prod.yml   # Production deployment compose stack
├── .env.example              # Environment variables template
└── README.md
```

---

## 6. Quick Start (Docker)

1. **Clone repository and set environment**:
   ```bash
   git clone https://github.com/aditya-1739/Health-Care.git
   cd Health-Care
   cp .env.example .env
   ```

2. **Start the complete platform**:
   ```bash
   docker compose up --build -d
   ```

3. **Verify running containers**:
   ```bash
   docker compose ps
   ```
   - **Frontend Web UI**: `http://localhost`
   - **Backend API**: `http://localhost/api`
   - **Interactive API Docs**: `http://localhost:8000/docs`
   - **Health Probe**: `http://localhost/api/health/ready`

---

## 7. Local Development Setup

### Backend (Python 3.13)
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend (Node 20+)
```bash
cd frontend
npm install
npm run dev
```

### Run Backend Tests (119 test cases)
```bash
pytest backend/tests -v
```

---

## 8. Development & Demo Credentials

> **Notice**: The credentials below are for local development and demonstration testing only.

- **Patient Account**: `alice@patient.com` / `AlicePass123!`
- **Doctor Account**: `sarah.connor@hospital.com` / `DoctorPass123!`
- **Administrator Account**: `admin@hospital.com` / `AdminPass123!`

---

## 9. Comprehensive Documentation

- [System Architecture](docs/architecture.md)
- [Production Deployment Guide](docs/deployment.md)
- [API Reference](docs/api.md)
- [Security Specification](docs/security.md)

---

## 10. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
