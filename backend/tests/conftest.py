import threading
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import Doctor, Patient, User, UserRole

# Use an in-memory SQLite database with StaticPool for isolated unit tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=StaticPool,
)

# Protect low-level SQLite C statement execution from concurrent thread contention
_sqlite_exec_lock = threading.RLock()


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    _sqlite_exec_lock.acquire()


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    try:
        _sqlite_exec_lock.release()
    except RuntimeError:
        pass


@event.listens_for(engine, "handle_error")
def handle_cursor_error(exception_context):
    try:
        _sqlite_exec_lock.release()
    except RuntimeError:
        pass


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure every test runs against a fresh, isolated database schema."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provides a database session for test fixture setup."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    """FastAPI TestClient with overridden get_db dependency yielding a session per request."""
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    user = User(
        name="System Admin",
        email="admin@hospital.com",
        password_hash=get_password_hash("AdminPass123!"),
        role=UserRole.ADMIN,
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(subject=admin_user.id, role=admin_user.role.value)


@pytest.fixture
def doctor_user(db_session):
    user = User(
        name="Dr. Sarah Connor",
        email="sarah.connor@hospital.com",
        password_hash=get_password_hash("DoctorPass123!"),
        role=UserRole.DOCTOR,
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    doctor = Doctor(
        user_id=user.id,
        specialization="Cardiology",
        bio="Cardiology specialist with 10 years experience",
        slot_duration=30,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def doctor_token(doctor_user):
    return create_access_token(subject=doctor_user.id, role=doctor_user.role.value)


@pytest.fixture
def patient_a(db_session):
    user = User(
        name="Alice Patient",
        email="alice@patient.com",
        password_hash=get_password_hash("AlicePass123!"),
        role=UserRole.PATIENT,
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    patient = Patient(user_id=user.id, phone="555-0101")
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def patient_a_token(patient_a):
    return create_access_token(subject=patient_a.id, role=patient_a.role.value)


@pytest.fixture
def patient_b(db_session):
    user = User(
        name="Bob Patient",
        email="bob@patient.com",
        password_hash=get_password_hash("BobPass123!"),
        role=UserRole.PATIENT,
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    patient = Patient(user_id=user.id, phone="555-0202")
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def patient_b_token(patient_b):
    return create_access_token(subject=patient_b.id, role=patient_b.role.value)
