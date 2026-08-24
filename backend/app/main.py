import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.health import router as health_router
from app.api.v1.admin import router as admin_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.clinical import router as clinical_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.medicines import router as medicines_router
from app.api.v1.patients import router as patients_router
from app.api.v1.profile import router as profile_router
from app.core.config import settings
import app.models  # Ensure all models are registered with Base metadata

logger = logging.getLogger("healthcare_platform")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lifecycle context for FastAPI server (schema migrations are managed via Alembic)
    yield


app = FastAPI(
    title="Healthcare Appointment Manager",
    description="Production-grade healthcare appointment and clinical follow-up platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Production CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key"],
)


# Request validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg")
        errors.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": errors[0] if len(errors) == 1 else errors,
            "error_type": "ValidationError",
        },
    )


# General internal exception handler (Sanitizes stack traces and internal secrets)
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please try again later.",
            "error_type": "InternalServerError",
        },
    )


# Include API Routers
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(patients_router, prefix="/api")
app.include_router(doctors_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(clinical_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")
app.include_router(medicines_router, prefix="/api")
app.include_router(profile_router, prefix="/api")


@app.get("/", tags=["Root"])
def root():
    return {
        "name": "Healthcare Appointment Manager API",
        "version": "1.0.0",
        "docs": "/docs",
    }
