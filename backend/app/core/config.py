import re
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"  # "development" | "production" | "test"
    PROJECT_NAME: str = "Healthcare Appointment Manager"
    API_V1_STR: str = "/api"

    # Database Configuration (PostgreSQL)
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/healthcare_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # JWT Authentication
    JWT_SECRET: str = "development-secret-key-change-in-production-min-32-chars-long"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # AES-256 Fernet Encryption Key for OAuth tokens at rest
    OAUTH_ENCRYPTION_KEY: str = "x5uX0zG12D3p4J5K6L7M8N9O0P1Q2R3S4T5U6V7W8X9="

    # AI Service Settings
    AI_PROVIDER: str = "mock"  # "mock" | "gemini" | "openai"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Email & Notifications Settings
    EMAIL_PROVIDER: str = "mock"  # "mock" | "smtp" | "console"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: str = "noreply@healthcare-platform.com"
    EMAILS_FROM_NAME: str = "Healthcare Appointment System"

    # Google Calendar OAuth Settings
    GOOGLE_CLIENT_ID: Optional[str] = "mock-google-client-id.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: Optional[str] = "mock-google-client-secret"
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/calendar/callback"

    # Background Worker & Outbox Settings
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    USE_IN_PROCESS_WORKER: bool = True

    # Rate Limiting (Requests / minute)
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    RATE_LIMIT_BOOKING_PER_MINUTE: int = 30
    RATE_LIMIT_AI_PER_MINUTE: int = 10

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return v

    def validate_production_readiness(self):
        """
        Enforce strict validation when running in production mode.
        Fails fast if insecure development placeholder secrets are present.
        """
        if self.ENVIRONMENT == "production":
            if "development-secret" in self.JWT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError(
                    "PRODUCTION ERROR: Insecure JWT_SECRET detected. "
                    "You must provide a secure random secret of at least 32 characters in production."
                )
            if "*" in self.CORS_ORIGINS:
                raise ValueError(
                    "PRODUCTION ERROR: Wildcard '*' in CORS_ORIGINS is prohibited for credentialed APIs in production."
                )
            if not self.OAUTH_ENCRYPTION_KEY or len(self.OAUTH_ENCRYPTION_KEY) < 32:
                raise ValueError(
                    "PRODUCTION ERROR: OAUTH_ENCRYPTION_KEY must be a valid AES-256 Fernet key in production."
                )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
# Execute production validator
try:
    settings.validate_production_readiness()
except ValueError as err:
    if settings.ENVIRONMENT == "production":
        raise err
