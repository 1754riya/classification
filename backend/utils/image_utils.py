import base64
import io
import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

logger = logging.getLogger("satellite-backend")

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/tif",
    "image/tiff",
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "TIFF"}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


def allowed_upload_types_message() -> str:
    return "Unsupported file format. Only JPG/JPEG, PNG, TIF/TIFF allowed."


def validate_upload(file: UploadFile, data: bytes, max_size_bytes: int = MAX_FILE_SIZE_BYTES) -> None:
    """Validate uploaded file with strict format checks.
    
    Issues fixed:
    - Reject if BOTH content_type and filename are missing
    - Verify actual image format after loading with PIL
    - Reject unsupported formats like BMP, GIF
    """
    if not data:
        logger.warning("Validation failed: uploaded file is empty")
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(data) > max_size_bytes:
        logger.warning("Validation failed: file too large (size_bytes=%d)", len(data))
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size_bytes // (1024 * 1024)} MB",
        )

    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    
    # STRICT: Reject if BOTH content_type and filename metadata are missing
    if not content_type and not suffix:
        logger.warning("Validation failed: both content_type and filename are missing")
        raise HTTPException(
            status_code=400, 
            detail=allowed_upload_types_message(),
        )

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        logger.warning("Validation failed: unsupported mime type (content_type=%s)", content_type)
        raise HTTPException(
            status_code=400, 
            detail=allowed_upload_types_message(),
        )

    if suffix and suffix not in ALLOWED_EXTENSIONS:
        logger.warning("Validation failed: unsupported extension (suffix=%s)", suffix)
        raise HTTPException(
            status_code=400, 
            detail=allowed_upload_types_message(),
        )

    try:
        with Image.open(io.BytesIO(data)) as image:
            # NEW: Verify actual image format after loading with PIL
            actual_format = image.format
            if actual_format not in ALLOWED_IMAGE_FORMATS:
                logger.warning(
                    "Validation failed: actual image format not allowed (format=%s)", 
                    actual_format
                )
                raise HTTPException(
                    status_code=400, 
                    detail=allowed_upload_types_message(),
                )
            image.verify()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Validation failed: invalid image file (error=%s)", str(exc))
        raise HTTPException(status_code=400, detail=f"Invalid image file: {exc}") from exc


def image_bytes_to_png_bytes(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()


def encode_bytes_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def decode_base64_to_bytes(data_b64: str) -> bytes:
    try:
        return base64.b64decode(data_b64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 input") from exc
