import logging

from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from services.compliance_service import ComplianceService
from dependencies import get_current_admin

router = APIRouter()
logger = logging.getLogger("compliance.documents")

# Format file yang diizinkan
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "image/webp",
}
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/process-document")
async def process_document(
    file: UploadFile = File(...),
    expected_name: str = Form(..., min_length=2),
    jurusan_tujuan: str = Form(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),  # endpoint dilindungi login
):
    # --- Validasi format file ---
    if file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning("Format tidak didukung: %s", file.content_type)
        raise HTTPException(
            status_code=415,
            detail=f"Format file tidak didukung. Gunakan: {', '.join(sorted(ALLOWED_MIME_TYPES))}",
        )

    # --- Baca file sambil cek ukuran ---
    image_bytes = await file.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="File kosong tidak dapat diproses")

    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        logger.warning("Ukuran file terlalu besar: %d bytes", len(image_bytes))
        raise HTTPException(
            status_code=413,
            detail=f"Ukuran file melebihi batas maksimum {MAX_FILE_SIZE_MB}MB",
        )

    # --- Jalankan pipeline ---
    try:
        return await ComplianceService.verify_document(
            image_bytes=image_bytes,
            filename=file.filename,
            content_type=file.content_type,
            target_major=jurusan_tujuan,
            expected_name=expected_name,
            db=db,
        )
    except ValueError as e:
        logger.error("AI pipeline error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error in pipeline")
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan internal saat memproses dokumen",
        ) from e
