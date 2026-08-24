"""
Profile Image Service.
Handles safe validation, square cropping, metadata stripping, WebP normalization, and storage for user profile avatars.
"""
import io
import os
import uuid
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.models.user import User


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_image_magic_bytes(data: bytes) -> Optional[str]:
    """
    Validates magic bytes of uploaded image buffer.
    Returns format ('JPEG', 'PNG', 'WEBP') if valid, else None.
    """
    if len(data) < 12:
        return None
    # JPEG
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    # WebP (RIFF....WEBP)
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "WEBP"
    return None


class ProfileImageService:
    @staticmethod
    def get_upload_directory() -> str:
        """Ensures avatar storage directory exists and returns absolute path."""
        upload_dir = os.path.abspath(settings.AVATAR_UPLOAD_DIR)
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    @classmethod
    async def process_and_save_avatar(cls, user: User, file: UploadFile) -> str:
        """
        Validates, crops, resizes (256x256), compresses (WebP), and stores a profile avatar.
        Returns the public relative URL (e.g. /uploads/avatars/avatar_1_abc123.webp).
        """
        # 1. Read buffer
        contents = await file.read()
        if len(contents) > settings.MAX_AVATAR_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image file size exceeds maximum limit of 5 MB.",
            )

        if len(contents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # 2. Magic byte validation
        detected_fmt = validate_image_magic_bytes(contents)
        if not detected_fmt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Supported formats are JPG, PNG, and WebP.",
            )

        # 3. Image processing via Pillow (center-crop square & resize 256x256)
        try:
            image = Image.open(io.BytesIO(contents))
            # Verify file integrity
            image.verify()
            # Reopen for transformation after verify
            image = Image.open(io.BytesIO(contents))
        except (UnidentifiedImageError, Exception) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not process image file. The image may be corrupted.",
            )

        # Convert palette/CMYK to RGB/RGBA
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.mode else "RGB")

        # Center-crop to 1:1 square aspect ratio
        width, height = image.size
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        cropped_image = image.crop((left, top, right, bottom))

        # Resize to standard avatar dimension (256x256) with high-quality resampling
        resized_image = cropped_image.resize((256, 256), Image.Resampling.LANCZOS)

        # 4. Save to secure storage with UUID filename
        storage_dir = cls.get_upload_directory()
        # Clean up existing avatar file for this user if present
        cls.delete_avatar_file(user.profile_image_url)

        safe_filename = f"avatar_{user.id}_{uuid.uuid4().hex[:12]}.webp"
        file_path = os.path.join(storage_dir, safe_filename)

        # Save as WebP (stripping EXIF metadata for privacy)
        resized_image.save(file_path, "WEBP", quality=85, method=6)

        public_url = f"/uploads/avatars/{safe_filename}"
        return public_url

    @classmethod
    def delete_avatar_file(cls, profile_image_url: Optional[str]) -> bool:
        """
        Safely removes physical avatar file from storage disk if exists.
        """
        if not profile_image_url or not profile_image_url.startswith("/uploads/avatars/"):
            return False

        filename = os.path.basename(profile_image_url)
        # Path traversal guard
        if ".." in filename or "/" in filename or "\\" in filename:
            return False

        storage_dir = cls.get_upload_directory()
        file_path = os.path.join(storage_dir, filename)

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except OSError:
                return False
        return False
