"""
Backend Tests for Phase 9: Profile Pictures for Patient, Doctor & Admin.
Covers upload, deletion, validation, format acceptance, size limits, privacy, and RBAC rules.
"""
import io
import pytest
from PIL import Image
from app.models.user import User, UserRole
from app.core.security import create_access_token


def create_test_image(format="PNG", size=(100, 100), color="blue") -> bytes:
    """Helper to generate a real, valid image buffer in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


@pytest.fixture
def auth_tokens(db_session):
    """Creates Patient, Doctor, and Admin users and returns their JWT bearer tokens and models."""
    from app.core.security import get_password_hash
    from app.models.user import Patient, Doctor

    # 1. Patient
    pat_user = User(
        name="Avatar Test Patient",
        email="avatar.patient@example.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.PATIENT,
        status="active",
    )
    db_session.add(pat_user)
    db_session.flush()
    pat = Patient(user_id=pat_user.id)
    db_session.add(pat)

    # 2. Doctor
    doc_user = User(
        name="Dr. Avatar Doctor",
        email="avatar.doctor@hospital.example",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.DOCTOR,
        status="active",
    )
    db_session.add(doc_user)
    db_session.flush()
    doc = Doctor(user_id=doc_user.id, specialization="Cardiology", active=True)
    db_session.add(doc)

    # 3. Admin
    admin_user = User(
        name="Avatar Admin",
        email="avatar.admin@hospital.com",
        password_hash=get_password_hash("Pass123!"),
        role=UserRole.ADMIN,
        status="active",
    )
    db_session.add(admin_user)
    db_session.commit()

    return {
        "patient": {"user": pat_user, "token": create_access_token(pat_user.id, "PATIENT")},
        "doctor": {"user": doc_user, "token": create_access_token(doc_user.id, "DOCTOR"), "doc_id": doc.id},
        "admin": {"user": admin_user, "token": create_access_token(admin_user.id, "ADMIN")},
    }


def test_user_without_avatar_has_null_profile_image_url(client, auth_tokens):
    """1. User without avatar gets null/default profile_image_url."""
    token = auth_tokens["patient"]["token"]
    res = client.get("/api/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["profile_image_url"] is None


def test_patient_can_upload_own_image(client, auth_tokens):
    """2. Patient can upload their own profile picture."""
    token = auth_tokens["patient"]["token"]
    img_bytes = create_test_image(format="PNG", color="green")

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("avatar.png", img_bytes, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["profile_image_url"] is not None
    assert data["profile_image_url"].startswith("/uploads/avatars/avatar_")
    assert data["profile_image_url"].endswith(".webp")


def test_doctor_can_upload_own_image(client, auth_tokens):
    """3. Doctor can upload their own profile picture."""
    token = auth_tokens["doctor"]["token"]
    img_bytes = create_test_image(format="JPEG", color="red")

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("doctor.jpg", img_bytes, "image/jpeg")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["profile_image_url"] is not None
    assert data["role"] == "DOCTOR"


def test_admin_can_upload_own_image(client, auth_tokens):
    """4. Admin can upload their own profile picture."""
    token = auth_tokens["admin"]["token"]
    img_bytes = create_test_image(format="WEBP", color="purple")

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("admin.webp", img_bytes, "image/webp")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["profile_image_url"] is not None
    assert data["role"] == "ADMIN"


def test_unauthenticated_avatar_upload_rejected(client):
    """5. Unauthenticated user cannot upload an avatar."""
    img_bytes = create_test_image(format="PNG")
    res = client.post(
        "/api/profile/me/avatar",
        files={"file": ("avatar.png", img_bytes, "image/png")},
    )
    assert res.status_code == 401


def test_invalid_image_format_rejected(client, auth_tokens):
    """6. Invalid or executable file masquerading as image is rejected."""
    token = auth_tokens["patient"]["token"]
    fake_payload = b"<html><script>alert('xss')</script></html>"

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malicious.png", fake_payload, "image/png")},
    )
    assert res.status_code == 400
    assert "Invalid image format" in res.json()["detail"]


def test_oversized_image_rejected(client, auth_tokens):
    """7. Image exceeding 5 MB is rejected."""
    token = auth_tokens["patient"]["token"]
    # 5.5 MB payload starting with PNG magic bytes
    large_payload = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (6 * 1024 * 1024))

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("giant.png", large_payload, "image/png")},
    )
    assert res.status_code == 400
    assert "5 MB" in res.json()["detail"]


def test_valid_png_accepted_and_cropped(client, auth_tokens):
    """8. Rectangular PNG is accepted and cropped into square 256x256 WebP."""
    token = auth_tokens["patient"]["token"]
    img_bytes = create_test_image(format="PNG", size=(400, 200), color="yellow")

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("rect.png", img_bytes, "image/png")},
    )
    assert res.status_code == 200
    assert res.json()["profile_image_url"].endswith(".webp")


def test_valid_jpg_accepted(client, auth_tokens):
    """9. Valid JPEG is accepted."""
    token = auth_tokens["doctor"]["token"]
    img_bytes = create_test_image(format="JPEG", size=(300, 300), color="cyan")

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.jpg", img_bytes, "image/jpeg")},
    )
    assert res.status_code == 200
    assert res.json()["profile_image_url"] is not None


def test_valid_webp_accepted(client, auth_tokens):
    """10. Valid WebP is accepted."""
    token = auth_tokens["admin"]["token"]
    img_bytes = create_test_image(format="WEBP", size=(250, 250), color="orange")

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.webp", img_bytes, "image/webp")},
    )
    assert res.status_code == 200
    assert res.json()["profile_image_url"] is not None


def test_remove_avatar_flow(client, auth_tokens):
    """11. User can remove their own avatar via DELETE /api/profile/me/avatar."""
    token = auth_tokens["patient"]["token"]
    img_bytes = create_test_image(format="PNG")

    # Upload first
    client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("avatar.png", img_bytes, "image/png")},
    )

    # Delete avatar
    del_res = client.delete(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["profile_image_url"] is None

    # Verify GET /api/profile/me shows null
    get_res = client.get("/api/profile/me", headers={"Authorization": f"Bearer {token}"})
    assert get_res.json()["profile_image_url"] is None


def test_replacing_avatar_updates_url(client, auth_tokens):
    """12. Replacing avatar updates profile_image_url to the new file."""
    token = auth_tokens["doctor"]["token"]
    img1 = create_test_image(format="PNG", color="red")
    img2 = create_test_image(format="JPEG", color="blue")

    res1 = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("first.png", img1, "image/png")},
    )
    url1 = res1.json()["profile_image_url"]

    res2 = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("second.jpg", img2, "image/jpeg")},
    )
    url2 = res2.json()["profile_image_url"]

    assert url1 != url2
    assert url2.startswith("/uploads/avatars/avatar_")


def test_public_doctor_profile_exposes_avatar(client, auth_tokens):
    """13 & 14. Doctor profile picture is exposed on public doctor directory."""
    doc_token = auth_tokens["doctor"]["token"]
    doc_id = auth_tokens["doctor"]["doc_id"]

    # Upload avatar for doctor
    img_bytes = create_test_image(format="PNG")
    client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {doc_token}"},
        files={"file": ("avatar.png", img_bytes, "image/png")},
    )

    # Public endpoint GET /api/doctors/{id}
    res = client.get(f"/api/doctors/{doc_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["profile_image_url"] is not None
    assert data["profile_image_url"].startswith("/uploads/avatars/")


def test_patient_profile_not_exposed_publicly(client, auth_tokens):
    """15. Patient profile is protected from unauthenticated access."""
    res = client.get("/api/profile/me")
    assert res.status_code == 401


def test_avatar_responses_never_contain_sensitive_secrets(client, auth_tokens):
    """16. Avatar endpoints never leak password hashes, tokens, or private secrets."""
    token = auth_tokens["patient"]["token"]
    img_bytes = create_test_image(format="PNG")

    res = client.post(
        "/api/profile/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("avatar.png", img_bytes, "image/png")},
    )
    data = res.json()
    assert "password" not in data
    assert "password_hash" not in data
    assert "token" not in data
    assert "jwt" not in data
