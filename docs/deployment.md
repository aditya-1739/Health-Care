# Healthcare Appointment Manager — Production Deployment Guide

This guide provides step-by-step instructions for deploying the Healthcare Appointment Manager in production environments.

---

## 1. Prerequisites

- **Docker & Docker Compose**: Docker Engine 24.0+ / Docker Compose V2
- **Hardware Requirements**:
  - Minimum: 2 vCPU, 4 GB RAM, 20 GB SSD
  - Recommended: 4 vCPU, 8 GB RAM, 50 GB SSD
- **Network / Domain**:
  - Domain name pointing to the deployment server
  - TLS/SSL termination configured at the platform load balancer or reverse proxy

---

## 2. Environment Configuration

1. Clone the repository:
   ```bash
   git clone https://github.com/aditya-1739/Health-Care.git
   cd Health-Care
   ```

2. Generate your production `.env` configuration from `.env.example`:
   ```bash
   cp .env.example .env
   ```

3. Configure mandatory production environment variables:
   ```ini
   ENVIRONMENT=production
   PROJECT_NAME="Healthcare Appointment Manager"
   API_V1_STR=/api

   # Database Configuration
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_secure_random_postgres_password
   POSTGRES_DB=healthcare_db
   DATABASE_URL=postgresql://postgres:your_secure_random_postgres_password@postgres:5432/healthcare_db

   # Redis Configuration
   REDIS_URL=redis://redis:6379/0
   CELERY_BROKER_URL=redis://redis:6379/0
   CELERY_RESULT_BACKEND=redis://redis:6379/0
   USE_IN_PROCESS_WORKER=false

   # JWT Authentication (generate with: openssl rand -hex 32)
   JWT_SECRET=your_secure_random_32_char_minimum_secret_key
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=1440

   # AES-256 Fernet Encryption Key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   OAUTH_ENCRYPTION_KEY=your_generated_fernet_encryption_key_here=

   # CORS Allowed Origins
   CORS_ORIGINS=["https://yourdomain.com"]

   # AI Provider ("mock" | "gemini" | "openai")
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here

   # Email Service (SMTP / Mock)
   EMAIL_PROVIDER=smtp
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=your_sendgrid_api_key
   EMAILS_FROM_EMAIL=notifications@yourdomain.com
   EMAILS_FROM_NAME="Healthcare Appointments"

   # Google Calendar OAuth Integration
   GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_client_secret
   GOOGLE_REDIRECT_URI=https://yourdomain.com/calendar/callback
   ```

---

## 3. Production Deployment with Docker Compose

Deploy the isolated production stack (PostgreSQL and Redis without host port publication):

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Start services in detached mode
docker compose -f docker-compose.prod.yml up -d
```

### Automatic Migration Execution
The backend container runs database migrations automatically on startup via `backend/entrypoint.sh`:
```bash
alembic upgrade head
```

To manually verify or run migrations:
```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## 4. Verification & Health Probes

Verify that all containers are healthy:

```bash
docker compose -f docker-compose.prod.yml ps
```

Test health endpoints:

- **Liveness Probe**:
  ```bash
  curl -i https://yourdomain.com/api/health/live
  # Response: HTTP/1.1 200 OK {"status": "live"}
  ```

- **Readiness Probe** (checks PostgreSQL and Redis connections):
  ```bash
  curl -i https://yourdomain.com/api/health/ready
  # Response: HTTP/1.1 200 OK {"status": "ready", "database": "connected", "redis": "connected"}
  ```

- **Medicine Information Service**:
  ```bash
  curl -i https://yourdomain.com/api/medicines/search?q=paracetamol
  # Response: HTTP/1.1 200 OK
  ```

---

## 5. Backup and Maintenance

### Database Backup
```bash
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U postgres healthcare_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Database Restore
```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres healthcare_db < backup_file.sql
```

### Viewing Logs
```bash
# Backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# Celery worker logs
docker compose -f docker-compose.prod.yml logs -f worker
```
